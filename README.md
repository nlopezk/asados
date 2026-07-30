# Asados App — Phase 1

A simple Flask + SQLite web app to track "asado" events, participants, and points.

## How to run it locally

1. **Install Python 3** if you don't have it (python.org).
2. **Open a terminal** in this folder.
3. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```
4. **Create the database** (only needs to be done once, or whenever you
   want to wipe all data and start fresh):
   ```
   python3 -c "from app import init_db; init_db()"
   ```
5. **Run the app:**
   ```
   python3 app.py
   ```
6. **Open your browser** to: http://127.0.0.1:5000

## Project structure

```
asado_app/
├── app.py            <- Flask routes and logic (the "brain")
├── config.py         <- Point weights + points calculation formula (EDIT HERE to tweak scoring)
├── schema.sql         <- Database table definitions
├── requirements.txt   <- Python packages needed
├── templates/          <- HTML pages (Jinja2 templates)
│   ├── base.html        (shared layout: navbar, CSS link)
│   ├── index.html        (home page: list of all asados)
│   ├── new_asado.html     (form to add a new asado)
│   └── view_asado.html     (detail page for one asado)
└── static/
    └── style.css         (all the visual styling)
```

## What Phase 1 includes
- Add a new asado (with its shared details: meat, cooking method, location, etc.)
- Add multiple participants per asado, each with their own Rol
- Automatic Points calculation per participant, using the formula in `config.py`
- View a list of all asados, and a detail page for each one
- Basic responsive styling (works on mobile browsers too)

## What's NOT included yet (coming in later phases)
- Login / authentication (right now, usernames are just typed in freely)
- Editing or deleting existing entries
- Aggregated statistics / leaderboards
- Deployment to a public URL
