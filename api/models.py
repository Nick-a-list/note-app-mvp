from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

try:
    from .database import Base
except ImportError:
    from database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Folder(Base):
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    folder_type = Column(String(30), default="regular", nullable=False)  # "regular", "todo", "quick"
    wallpaper = Column(String(255), default="default-paper", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    notes = relationship("Note", back_populates="folder", cascade="all, delete-orphan")


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    folder_id = Column(Integer, ForeignKey("folders.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=False, default="Untitled Note")

    # Stores plaintext or client-side AES-GCM encrypted ciphertext
    content = Column(Text, default="", nullable=False)
    note_type = Column(String(30), default="regular", nullable=False)  # "regular" or "todo"

    # Todo list items and configurable rule constraint (defaults to max 10 items)
    todo_items = Column(JSON, default=list, nullable=False)
    max_items_rule = Column(Integer, default=10, nullable=False)

    # Client-side encryption metadata (key stays strictly on client)
    is_encrypted = Column(Boolean, default=False, nullable=False)
    encryption_iv = Column(String(128), nullable=True)
    encryption_salt = Column(String(128), nullable=True)

    # Organization: Bookmarks, Global priority, and Most Used counter
    is_bookmarked = Column(Boolean, default=False, nullable=False)
    bookmark_color = Column(String(30), nullable=True)  # e.g., "red", "yellow", "blue", "green"
    is_global = Column(Boolean, default=False, nullable=False)
    view_count = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    folder = relationship("Folder", back_populates="notes")