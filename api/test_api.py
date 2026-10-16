import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from .database import Base, get_db
from .index import app, seed_default_folders

# In-memory SQLite database for fast isolated CI testing
SQLALCHEMY_DATABASE_URL = "sqlite://"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    seed_default_folders(db)
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


def test_default_folders_and_wallpaper_update():
    res = client.get("/api/folders")
    assert res.status_code == 200
    folders = res.json()
    assert len(folders) >= 3

    # Update wallpaper for a specific folder
    folder_id = folders[0]["id"]
    patch_res = client.patch(f"/api/folders/{folder_id}", json={"wallpaper": "pastel-clouds"})
    assert patch_res.status_code == 200
    assert patch_res.json()["wallpaper"] == "pastel-clouds"


def test_encrypted_note_persistence():
    folders = client.get("/api/folders").json()
    folder_id = folders[0]["id"]

    payload = {
        "folder_id": folder_id,
        "title": "Secret Journal",
        "content": "U2FsdGVkX1+ciphertext_only_server_cannot_read",
        "is_encrypted": True,
        "encryption_iv": "a1b2c3d4e5f6",
        "encryption_salt": "998877665544",
    }
    res = client.post("/api/notes", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["is_encrypted"] is True
    assert data["content"] == "U2FsdGVkX1+ciphertext_only_server_cannot_read"


def test_todo_max_10_constraint_and_tap_to_disappear():
    folders = client.get("/api/folders").json()
    folder_id = folders[0]["id"]

    # Creating a todo note with 10 items succeeds
    ten_items = [f"Task {i}" for i in range(1, 11)]
    res = client.post(
        "/api/notes",
        json={
            "folder_id": folder_id,
            "title": "Capped Todo List",
            "note_type": "todo",
            "todo_items": ten_items,
            "max_items_rule": 10,
        },
    )
    assert res.status_code == 201
    note_id = res.json()["id"]

    # Attempting to add an 11th item is rejected by the rule constraint
    overflow_res = client.post(f"/api/notes/{note_id}/todos", json={"text": "Task 11"})
    assert overflow_res.status_code == 422

    # Tapping an item makes it disappear immediately
    tap_res = client.delete(f"/api/notes/{note_id}/todos/0")
    assert tap_res.status_code == 200
    assert len(tap_res.json()["todo_items"]) == 9
    assert "Task 1" not in tap_res.json()["todo_items"]


def test_bookmarks_pin_to_top_and_filter_by_color():
    folders = client.get("/api/folders").json()
    folder_id = folders[0]["id"]

    # Regular note created first
    client.post("/api/notes", json={"folder_id": folder_id, "title": "Normal Note"})
    # Bookmarked note created second
    client.post(
        "/api/notes",
        json={
            "folder_id": folder_id,
            "title": "Pinned Note",
            "is_bookmarked": True,
            "bookmark_color": "red",
        },
    )

    notes = client.get(f"/api/notes?folder_id={folder_id}").json()
    assert notes[0]["title"] == "Pinned Note"

    red_bookmarks = client.get("/api/notes?bookmark_color=red").json()
    assert len(red_bookmarks) == 1
    assert red_bookmarks[0]["title"] == "Pinned Note"