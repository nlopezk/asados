# Asados App — Phase 3

A Flask + SQLite web app to track "asado" events, participants, and points — now with login.

**Live (testing) deployment**: https://asados.pythonanywhere.com —
currently running with a fresh/empty test database, not the real
history from local dev yet. See `CLAUDE.md`'s "Phase 6" section for
how the deployment is wired up and how to ship an update
(`git pull` + Reload on PythonAnywhere's Web tab).

> **Using an AI assistant (Claude Code, etc.) on this project?** See
> [`CLAUDE.md`](./CLAUDE.md) first — it explains the reasoning behind
> several design decisions (the points formula, the map choice, the
> login setup) that aren't obvious from the code alone.

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
   you create the first account, an admin, yourself with this script):
   ```
   python create_user.py nico "nico" "Don Nicola" admin

   ```
   `role` (`admin` or `normal`) is optional and defaults to `normal` if
   omitted. Once you have an admin account, you can create the rest of
   the group's accounts either by running this script again or from the
   app's **Configuración** page after logging in as that admin.
6. *(Optional)* **Fill it with random test data** instead of typing entries
   by hand, so you have something to click around and filter/export:
   ```
   python seed_random_asados.py 150
   ```
7. **Run the app:**
   ```
   python app.py
   ```
8. **Open your browser** to: http://127.0.0.1:5000 — you'll be sent to
   a login page first. Log in with a username/password you created in step 5.

## Project structure

```
asado_app/
├── app.py             <- Flask routes, login/session logic (the "brain")
├── config.py          <- Point weights + points formula (EDIT HERE to tweak scoring)
├── create_user.py      <- Run this from the terminal to create login accounts
├── seed_random_asados.py <- Run this to fill the DB with random test data
├── schema.sql          <- Database table definitions
├── CLAUDE.md            <- Context/decisions notes for AI assistants (see above)
├── secret_key.txt       <- Auto-generated on first run. NEVER commit this (.gitignore already excludes it)
├── requirements.txt     <- Python packages needed
├── templates/            <- HTML pages (Jinja2 templates)
│   ├── base.html           (shared layout: navbar, login status)
│   ├── login.html           (login form)
│   ├── index.html            (home page: list of all asados, with filters)
│   ├── new_asado.html         (create-asado page)
│   ├── view_asado.html         (edit-asado page; admin sees a delete button)
│   ├── _asado_form.html         (the shared form fields used by both of the above)
│   ├── config.html             (profile settings + admin user management)
│   └── base_asados.html         (flat spreadsheet view + CSV export)
└── static/
    └── style.css              (all the visual styling)
```

## What Phase 2 added
- Username/password login using Flask sessions (no OAuth/Google yet)
- Accounts have a `name` (display name) and `role` (`admin`/`normal`) alongside username/password
- Accounts are created via `create_user.py` (terminal script) or, once an admin
  exists, from the **Configuración** page — still no public sign-up page
- The whole app now requires login — you're redirected to `/login` if you're not signed in
- Participants in an asado are now chosen from a dropdown of **registered accounts only**
  (no more free-typed guest names)
- A "Salir" (logout) link and your display name appear in the navbar once logged in
- **Configuración page** (`/config`): any user can change their own name/password;
  admins can additionally create or delete accounts

## What Phase 3 adds
- Clicking into an asado now opens an **editable form**, prefilled with its
  current values — any logged-in user can change any asado's details or
  participant list and save
- Editing recalculates that asado's points/weights from the current formula
  in `config.py`, the same way creating a new one does
- **Deleting an asado is admin-only**, with a confirmation prompt (removes the
  asado and all its participants' points for that event — no undo)

## What's NOT included yet (coming in later phases)
- Aggregated statistics / leaderboards
- Deployment to a public URL

## Git workflow
```
git add .
git commit -m "changes in version"
git tag -a v0.11.0 -m "changes in version"
git push
git push origin v0.10.0 v0.11.0

```

## Init quick

python -c "from app import init_db; init_db()"
python create_user.py nico "nico" "Don Nicola" admin
python create_user.py augusto "augusto" "augusto" admin
python create_user.py cristian "cristian" "cristian" admin
python create_user.py raul "raul" "raul" admin
python create_user.py nicog "nicog" "nicog" admin
python seed_random_asados.py 150