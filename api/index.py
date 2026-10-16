import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session
from urllib.parse import parse_qs, urlencode
from fastapi import Request

# Ensure the api/ directory is on sys.path for Vercel serverless execution
CURRENT_DIR = Path(__file__).resolve().parent
BASE_DIR = CURRENT_DIR.parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

try:
    from . import models, schemas
    from .database import SessionLocal, engine, get_db
except ImportError:
    import models
    import schemas
    from database import SessionLocal, engine, get_db


def seed_default_folders(db: Session):
    """Ensure built-in default folders exist on first launch."""
    defaults = [
        {"name": "Quick Notes", "folder_type": "quick", "wallpaper": "warm-grid"},
        {"name": "General Notes", "folder_type": "regular", "wallpaper": "default-paper"},
        {"name": "Daily Todos", "folder_type": "todo", "wallpaper": "minimal-dots"},
    ]
    for folder_data in defaults:
        exists = db.query(models.Folder).filter(models.Folder.name == folder_data["name"]).first()
        if not exists:
            db.add(models.Folder(**folder_data))
    db.commit()


def init_db_safe():
    """Create tables and seed default folders without crashing serverless cold start."""
    try:
        models.Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            seed_default_folders(db)
    except Exception as e:
        print(f"Database init warning: {e}")


init_db_safe()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db_safe()
    yield


app = FastAPI(
    title="Secure & Aesthetic Notes MVP API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def restore_vercel_original_path(request: Request, call_next):
    """Restore the original browser URL path when Vercel rewrites to /api/index."""
    if request.scope.get("path") in ("/api/index", "/api/index.py"):
        raw_qs = request.scope.get("query_string", b"").decode("utf-8")
        params = parse_qs(raw_qs, keep_blank_values=True)
        if "__path" in params:
            real_path = params.pop("__path")[0]
            if not real_path.startswith("/"):
                real_path = "/" + real_path
            request.scope["path"] = real_path
            request.scope["raw_path"] = real_path.encode("utf-8")
            request.scope["query_string"] = urlencode(params, doseq=True).encode("utf-8")
    return await call_next(request)

@app.get("/", include_in_schema=False)
@app.get("/api/index", include_in_schema=False)
@app.get("/api/index.py", include_in_schema=False)
def serve_frontend():
    index_file = BASE_DIR / "static" / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h1>Frontend not found</h1>", status_code=404)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


# ==================== FOLDER ENDPOINTS ====================

@app.get("/api/folders", response_model=List[schemas.FolderResponse])
def list_folders(db: Session = Depends(get_db)):
    return db.query(models.Folder).order_by(models.Folder.id.asc()).all()


@app.post("/api/folders", response_model=schemas.FolderResponse, status_code=status.HTTP_201_CREATED)
def create_folder(folder_in: schemas.FolderCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Folder).filter(models.Folder.name == folder_in.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="A folder with this name already exists.")
    folder = models.Folder(**folder_in.model_dump())
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return folder


@app.patch("/api/folders/{folder_id}", response_model=schemas.FolderResponse)
def update_folder(
    folder_id: int,
    folder_in: schemas.FolderUpdate,
    db: Session = Depends(get_db),
):
    folder = db.query(models.Folder).filter(models.Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found.")

    update_data = folder_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(folder, key, value)

    db.commit()
    db.refresh(folder)
    return folder


@app.delete("/api/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(folder_id: int, db: Session = Depends(get_db)):
    folder = db.query(models.Folder).filter(models.Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found.")
    db.delete(folder)
    db.commit()
    return None


# ==================== NOTE ENDPOINTS ====================

@app.get("/api/notes", response_model=List[schemas.NoteResponse])
def list_notes(
    folder_id: Optional[int] = Query(None, description="Filter by specific folder ID"),
    smart_folder: Optional[str] = Query(
        None,
        pattern="^(all|quick|bookmarks|most_used|todos)$",
        description="Built-in smart views: all, quick, bookmarks, most_used (top 20), todos",
    ),
    search: Optional[str] = Query(None, description="Search notes by title or plaintext content"),
    bookmark_color: Optional[str] = Query(None, description="Filter by bookmark color"),
    db: Session = Depends(get_db),
):
    query = db.query(models.Note)

    if smart_folder == "bookmarks":
        query = query.filter(models.Note.is_bookmarked.is_(True))
    elif smart_folder == "todos":
        query = query.filter(models.Note.note_type == "todo")
    elif smart_folder == "quick":
        quick_folder = db.query(models.Folder).filter(models.Folder.folder_type == "quick").first()
        if quick_folder:
            query = query.filter(
                or_(models.Note.folder_id == quick_folder.id, models.Note.is_global.is_(True))
            )
    elif smart_folder == "most_used":
        return (
            query.order_by(desc(models.Note.view_count), desc(models.Note.updated_at))
            .limit(20)
            .all()
        )
    elif folder_id is not None:
        query = query.filter(
            or_(models.Note.folder_id == folder_id, models.Note.is_global.is_(True))
        )

    if bookmark_color:
        query = query.filter(
            models.Note.is_bookmarked.is_(True),
            models.Note.bookmark_color == bookmark_color,
        )

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                models.Note.title.ilike(pattern),
                (models.Note.is_encrypted.is_(False) & models.Note.content.ilike(pattern)),
            )
        )

    return query.order_by(
        desc(models.Note.is_global),
        desc(models.Note.is_bookmarked),
        desc(models.Note.updated_at),
    ).all()


@app.get("/api/notes/{note_id}", response_model=schemas.NoteResponse)
def get_note(note_id: int, db: Session = Depends(get_db)):
    note = db.query(models.Note).filter(models.Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")

    note.view_count += 1
    db.commit()
    db.refresh(note)
    return note


@app.post("/api/notes", response_model=schemas.NoteResponse, status_code=status.HTTP_201_CREATED)
def create_note(note_in: schemas.NoteCreate, db: Session = Depends(get_db)):
    folder = db.query(models.Folder).filter(models.Folder.id == note_in.folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Target folder does not exist.")

    note = models.Note(**note_in.model_dump())
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@app.put("/api/notes/{note_id}", response_model=schemas.NoteResponse)
def update_note(note_id: int, note_in: schemas.NoteUpdate, db: Session = Depends(get_db)):
    note = db.query(models.Note).filter(models.Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")

    update_data = note_in.model_dump(exclude_unset=True)

    new_type = update_data.get("note_type", note.note_type)
    new_todos = update_data.get("todo_items", note.todo_items)
    new_max = update_data.get("max_items_rule", note.max_items_rule)

    if new_type == "todo" and len(new_todos) > new_max:
        raise HTTPException(
            status_code=422,
            detail=f"Todo list cannot exceed the rule limit of {new_max} items.",
        )

    for key, value in update_data.items():
        setattr(note, key, value)

    db.commit()
    db.refresh(note)
    return note


@app.delete("/api/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: int, db: Session = Depends(get_db)):
    note = db.query(models.Note).filter(models.Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")
    db.delete(note)
    db.commit()
    return None


# ==================== TAP-TO-DISAPPEAR TODO ENDPOINTS ====================

@app.post("/api/notes/{note_id}/todos", response_model=schemas.NoteResponse)
def add_todo_item(
    note_id: int,
    item: schemas.TodoItemAdd,
    db: Session = Depends(get_db),
):
    note = db.query(models.Note).filter(models.Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")
    if note.note_type != "todo":
        raise HTTPException(status_code=400, detail="This note is not a todo list note.")

    current_items = list(note.todo_items or [])
    if len(current_items) >= note.max_items_rule:
        raise HTTPException(
            status_code=422,
            detail=f"Rule constraint reached: maximum of {note.max_items_rule} todo items allowed.",
        )

    current_items.append(item.text)
    note.todo_items = current_items
    db.commit()
    db.refresh(note)
    return note


@app.delete("/api/notes/{note_id}/todos/{item_index}", response_model=schemas.NoteResponse)
def complete_and_disappear_todo_item(
    note_id: int,
    item_index: int,
    db: Session = Depends(get_db),
):
    """Makes a todo item disappear immediately when tapped."""
    note = db.query(models.Note).filter(models.Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")
    if note.note_type != "todo":
        raise HTTPException(status_code=400, detail="This note is not a todo list note.")

    current_items = list(note.todo_items or [])
    if item_index < 0 or item_index >= len(current_items):
        raise HTTPException(status_code=404, detail="Todo item index out of range.")

    current_items.pop(item_index)
    note.todo_items = current_items
    db.commit()
    db.refresh(note)
    return note