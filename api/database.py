import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# On Vercel serverless, only /tmp is writable if no external DATABASE_URL is configured yet
default_sqlite = "sqlite:////tmp/notes.db" if os.getenv("VERCEL") else "sqlite:///./notes.db"
DATABASE_URL = os.getenv("DATABASE_URL", default_sqlite)

# Handle Heroku/Vercel postgres:// prefix if present
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()