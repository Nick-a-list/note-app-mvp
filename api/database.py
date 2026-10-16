import os
import ssl
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

# On Vercel (or AWS Lambda), only /tmp is writable for SQLite
is_serverless = bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
default_db = "sqlite:////tmp/notes.db" if is_serverless else "sqlite:///./notes.db"

DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or os.getenv("POSTGRES_URL")
    or default_db
)

connect_args = {}

if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
elif DATABASE_URL.startswith(("postgres://", "postgresql://")):
    # Route through pure-Python pg8000 driver
    parsed = urlparse(DATABASE_URL)
    scheme = "postgresql+pg8000"
    # Strip libpq-specific params that pg8000 doesn't understand
    query_params = dict(parse_qsl(parsed.query))
    query_params.pop("sslmode", None)
    query_params.pop("channel_binding", None)
    # Always use SSL for remote hosts (Neon requires it)
    if parsed.hostname not in ("localhost", "127.0.0.1"):
        connect_args["ssl_context"] = ssl.create_default_context()
    clean_query = urlencode(query_params)
    DATABASE_URL = urlunparse((scheme, parsed.netloc, parsed.path, parsed.params, clean_query, parsed.fragment))

# --- Engine ---
engine_kwargs = {"connect_args": connect_args}

if not DATABASE_URL.startswith("sqlite"):
    engine_kwargs["pool_pre_ping"] = True          # test the connection before using it
    if is_serverless:
        engine_kwargs["poolclass"] = NullPool      # no reuse, so no dead sockets after a freeze
    else:
        engine_kwargs["pool_recycle"] = 300        # local dev: refresh connections every 5 min

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()