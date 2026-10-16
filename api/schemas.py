from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator


# --- Folder Schemas ---
class FolderBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    folder_type: str = Field(default="regular", pattern="^(regular|todo|quick)$")
    wallpaper: str = Field(default="default-paper", max_length=255)


class FolderCreate(FolderBase):
    pass


class FolderUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    wallpaper: Optional[str] = Field(None, max_length=255)


class FolderResponse(FolderBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Note Schemas ---
class NoteBase(BaseModel):
    folder_id: int
    title: str = Field(default="Untitled Note", max_length=200)
    content: str = Field(default="")
    note_type: str = Field(default="regular", pattern="^(regular|todo)$")
    todo_items: List[str] = Field(default_factory=list)
    max_items_rule: int = Field(default=10, ge=1, le=50)
    is_encrypted: bool = False
    encryption_iv: Optional[str] = None
    encryption_salt: Optional[str] = None
    is_bookmarked: bool = False
    bookmark_color: Optional[str] = None
    is_global: bool = False

    @model_validator(mode="after")
    def check_todo_limit(self):
        if self.note_type == "todo" and len(self.todo_items) > self.max_items_rule:
            raise ValueError(
                f"Todo list exceeds the rule limit of {self.max_items_rule} items."
            )
        return self


class NoteCreate(NoteBase):
    pass


class NoteUpdate(BaseModel):
    folder_id: Optional[int] = None
    title: Optional[str] = Field(None, max_length=200)
    content: Optional[str] = None
    note_type: Optional[str] = Field(None, pattern="^(regular|todo)$")
    todo_items: Optional[List[str]] = None
    max_items_rule: Optional[int] = Field(None, ge=1, le=50)
    is_encrypted: Optional[bool] = None
    encryption_iv: Optional[str] = None
    encryption_salt: Optional[str] = None
    is_bookmarked: Optional[bool] = None
    bookmark_color: Optional[str] = None
    is_global: Optional[bool] = None


class TodoItemAdd(BaseModel):
    text: str = Field(..., min_length=1, max_length=300)


class NoteResponse(NoteBase):
    id: int
    view_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}