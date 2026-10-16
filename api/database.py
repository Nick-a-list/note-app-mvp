import os
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

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
    # Filter out libpq-specific query params (like sslmode/channel_binding) that break pg8000
    query_params = dict(parse_qsl(parsed.query))
    if "sslmode" in query_params or "channel_binding" in query_params:
        query_params.pop("sslmode", None)
        query_params.pop("channel_binding", None)
        connect_args["ssl_context"] = True
    clean_query = urlencode(query_params)
    DATABASE_URL = urlunparse((scheme, parsed.netloc, parsed.path, parsed.params, clean_query, parsed.fragment))

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()