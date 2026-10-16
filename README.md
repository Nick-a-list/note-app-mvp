# Notes MVP

A secure, aesthetic note-taking web app with folders, todo lists, bookmarks, and client-side encryption.

**Live demo:** https://note-app-mvp.vercel.app

Built for CS 4800 (Software Engineering with AI) by Nicholas Barkero.

## Features

- **Folders with types:** regular, todo, and quick-notes folders, plus smart views (All Notes, Quick Notes, Bookmarked, All Todo Lists, Top 20 Most Used)
- **Per-folder wallpapers:** pick a different background for each folder
- **Todo lists with rules:** a configurable item cap (default 10), and tap an item to make it disappear
- **Bookmarks:** color-coded bookmarks that pin notes to the top, with filtering by color
- **Global notes:** mark a note as global so it appears in every folder
- **Search:** find notes by title or content
- **Client-side encryption:** note content can be encrypted in the browser (AES-GCM, key derived from your passphrase with PBKDF2). The server only stores ciphertext, and the key never leaves the client.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, SQLAlchemy, Pydantic |
| Database | PostgreSQL on Neon (SQLite for local development) |
| Frontend | HTML, vanilla JavaScript, Tailwind CSS (CDN) |
| Hosting | Vercel (serverless Python) |
| CI | GitHub Actions (runs pytest on every push and pull request) |

## Project Structure

```
.
├── api/
│   ├── index.py        # FastAPI app and routes (Vercel entrypoint)
│   ├── database.py     # Database engine and session setup
│   ├── models.py       # SQLAlchemy models (Folder, Note)
│   ├── schemas.py      # Pydantic request/response schemas
│   └── test_api.py     # API tests
├── static/
│   └── index.html      # Frontend
├── .github/workflows/
│   └── ci.yml          # Continuous integration
├── requirements.txt
└── vercel.json         # Vercel routing config
```

## Run Locally

```bash
# 1. Clone and enter the repo
git clone <your-repo-url>
cd note-app-mvp

# 2. Create a virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Start the server
uvicorn api.index:app --reload
```

Open http://localhost:8000. With no configuration, the app uses a local SQLite file (`notes.db`), and three default folders are created on first launch.

To use PostgreSQL instead, set the `DATABASE_URL` environment variable to your connection string before starting the server.

## Run the Tests

```bash
pytest api/test_api.py -v
```

Tests use an in-memory SQLite database, so they don't touch any real data.

## API Overview

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Health check |
| GET, POST | `/api/folders` | List or create folders |
| PATCH, DELETE | `/api/folders/{id}` | Update or delete a folder |
| GET, POST | `/api/notes` | List (with filters and search) or create notes |
| GET, PUT, DELETE | `/api/notes/{id}` | Read, update, or delete a note |
| POST | `/api/notes/{id}/todos` | Add a todo item (enforces the item cap) |
| DELETE | `/api/notes/{id}/todos/{index}` | Complete a todo item (it disappears) |

Interactive API docs are available at `/docs` when running locally.

## Deployment

The app deploys automatically to Vercel on every push to `main`. Set `DATABASE_URL` (or `POSTGRES_URL`) in the Vercel project's environment variables to point at a PostgreSQL database. A pooled connection string is recommended for serverless.

## Planned Features

- Reminders for notes
- Choose a default folder, or reopen the last-used folder
- Additional note types, such as grocery lists
- User accounts and authentication
