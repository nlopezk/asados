# Asados App

A Flask + SQLite web app to track "asado" (BBQ) events among a group of
friends: who was there, what was cooked and how, and a points system per
participant.

**Live deployment**: https://asados.pythonanywhere.com

> **Using an AI assistant (Claude Code, etc.) on this project?** See
> [`CLAUDE.md`](./CLAUDE.md) first — it explains the *reasoning* behind
> the design decisions (the points formula, the map choice, the login
> setup, why weights are "frozen") that aren't obvious from the code
> alone. [`CHANGELOG.md`](./CHANGELOG.md) says what changed and when.

## How to run it locally

1. **Install Python 3** if you don't have it (python.org).
2. **Open a terminal** in this folder.
3. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```
4. **Create the database** (WIPES any existing data — `schema.sql` runs
   `DROP TABLE` + `CREATE TABLE`, there is no migration system):
   ```
   python -c "from app import init_db; init_db()"
   ```
5. **Create at least one user account** (there's no public sign-up page —
   you create the first account, an admin, yourself with this script):
   ```
   python create_user.py nico "nico" "Don Nicola" admin
   ```
   `role` (`admin` or `normal`) is optional and defaults to `normal`.
   Once you have an admin account, you can create the rest of the
   group's accounts either by running this script again or from the
   app's **Configuración** page after logging in as that admin.
6. *(Optional)* **Fill it with random test data** instead of typing
   entries by hand, so you have something to click around and filter:
   ```
   python seed_random_asados.py 150
   ```
7. **Run the app:**
   ```
   python app.py
   ```
8. **Open your browser** to http://127.0.0.1:5000 — you'll hit a login
   page first. Use a username/password from step 5.

## Other useful commands

```bash
# Make an on-demand backup of asados.db right now (this also happens
# automatically every time a new asado is added).
python backup_db.py [retention_days]
```

## Project structure

```
As_app/
├── app.py                  <- Flask routes, login/session logic (the "brain")
├── config.py               <- Point weights + the points formula (EDIT HERE to tweak scoring)
├── activity_log.py         <- Writes the "who changed what" log + builds edit diffs
├── backup_db.py            <- Safe SQLite snapshot helper (used automatically + manually)
├── create_user.py          <- Terminal script to create login accounts
├── seed_random_asados.py   <- Fills the DB with random test data
├── schema.sql              <- Database table definitions + indexes
├── requirements.txt        <- Python packages needed
├── CLAUDE.md               <- Context/decisions notes (the "why") — see above
├── CHANGELOG.md            <- What changed, per version
├── Phases                  <- The original roadmap this was built against
├── secret_key.txt          <- Auto-generated on first run. NEVER commit (gitignored)
├── export_token.txt        <- Auto-generated. Guards /export/base-asados.csv. NEVER commit (gitignored)
├── asados.db               <- The database itself (gitignored)
├── backups/                <- Automatic + manual DB snapshots (gitignored)
├── templates/              <- HTML pages (Jinja2)
│   ├── base.html               (shared layout: navbar, footer)
│   ├── login.html              (login form)
│   ├── index.html              (home: list of asados, with filters)
│   ├── new_asado.html          (create-asado page)
│   ├── view_asado.html         (asado detail; edit in place; admin sees delete)
│   ├── _asado_form.html        (shared create/edit form fields + live points preview)
│   ├── _location_picker.html   (shared address autocomplete + Leaflet map modal)
│   ├── resumen.html            (standings table, sortable + filterable)
│   ├── base_asados.html        (flat spreadsheet view + CSV export)
│   ├── ubicaciones.html        (reusable saved-locations pool)
│   ├── activity_log.html       (who created/edited/deleted what, and when)
│   └── config.html             (profile settings + admin user management)
└── static/
    └── style.css           (all the visual styling)
```

## Features

- **Login** — session-based username/password. No public sign-up: accounts
  are created by an admin (in-app) or via `create_user.py`. Roles are
  `admin` or `normal`.
- **Asados** — date, name, description, one or more meat types, cooking
  method, surface, venue, an optional address/map pin, headcount and total
  weight. Any logged-in user can add or edit any asado; **deleting is
  admin-only**.
- **Points** — calculated per participant from the formula in `config.py`,
  then **frozen**: changing a weight later never rewrites history.
- **Resumen** (`/resumen`) — the standings table, one row per user, with
  filters (year, semester) and sortable columns.
- **Base de Asados** (`/base-asados`) — flat spreadsheet view (one row per
  participation) with a full CSV export, plus a token-gated version of
  that same export (`/export/base-asados.csv?token=...`) meant for
  Google Sheets `IMPORTDATA()` → Looker Studio dashboards. See
  `CLAUDE.md`'s "Looker Studio / Google Sheets export" section for
  setup steps and why it's token-gated instead of login-gated.
- **Ubicaciones** (`/ubicaciones`) — a reusable pool of saved places to
  quick-fill the asado form, so a recurring spot doesn't need retyping.
- **Registro de Actividad** (`/actividad`) — who created, edited, or deleted
  each asado, with a field-by-field diff of every edit.
- **Automatic backups** — every new asado triggers a safe SQLite snapshot
  into `backups/`.
- **Mobile-friendly** — responsive layout; the navbar collapses to a ☰ menu
  on narrow screens.

## Deploying an update

There's no CI/CD — deploying is a manual two-step on PythonAnywhere:

```bash
# In a PythonAnywhere Bash console:
cd ~/asados && git pull
```
Then click **Reload** on the Web tab.

**Never run `init_db()` on the server** — it would wipe the live database.
See `CLAUDE.md`'s Phase 6 section for how the deployment is wired up.

## Git release workflow

```bash
git add .
git commit -m "what changed"
git tag -a v1.0.0 -m "what changed"
git push
git push origin v1.0.0
```

Bump the version in **three** places when cutting a release — nothing keeps
them in sync automatically: `VERSION` in `app.py` (shown in the page
footer), `CHANGELOG.md`, and the git tag.
