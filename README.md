# Asados App — Phase 2

A Flask + SQLite web app to track "asado" events, participants, and points — now with login.

## How to run it locally

1. **Install Python 3** if you don't have it (python.org).
2. **Open a terminal** in this folder.
3. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```
4. **Create the database** (wipes any existing data — only run this once,
   or when you deliberately want a fresh start):
   ```
   python -c "from app import init_db; init_db()"
   ```
5. **Create at least one user account** (there's no public sign-up page —
   you create accounts yourself with this script):
   ```
   python create_user.py nico "myPassword123"
   ```
   Run it again for each person in your group, with their own username/password.
6. **Run the app:**
   ```
   python app.py
   ```
7. **Open your browser** to: http://127.0.0.1:5000 — you'll be sent to
   a login page first. Log in with a username/password you created in step 5.

## Project structure

```
asado_app/
├── app.py             <- Flask routes, login/session logic (the "brain")
├── config.py          <- Point weights + points formula (EDIT HERE to tweak scoring)
├── create_user.py      <- Run this from the terminal to create login accounts
├── schema.sql          <- Database table definitions
├── secret_key.txt       <- Auto-generated on first run. NEVER commit this (.gitignore already excludes it)
├── requirements.txt     <- Python packages needed
├── templates/            <- HTML pages (Jinja2 templates)
│   ├── base.html           (shared layout: navbar, login status)
│   ├── login.html           (login form)
│   ├── index.html            (home page: list of all asados)
│   ├── new_asado.html         (form to add a new asado)
│   └── view_asado.html         (detail page for one asado)
└── static/
    └── style.css              (all the visual styling)
```

## What Phase 2 adds
- Username/password login using Flask sessions (no OAuth/Google yet)
- Accounts are created via `create_user.py` (terminal script), not a public sign-up page
- The whole app now requires login — you're redirected to `/login` if you're not signed in
- Participants in an asado are now chosen from a dropdown of **registered accounts only**
  (no more free-typed guest names)
- A "Salir" (logout) link and your username appear in the navbar once logged in

## What's NOT included yet (coming in later phases)
- Editing or deleting existing entries
- Restricting edits to "your own" entries specifically
- Aggregated statistics / leaderboards
- Deployment to a public URL

## Git workflow
```
git add .
git commit -m "describe what you changed"
git push
```
