# Asados App

A Flask + SQLite web app to track "asado" (BBQ) events among groups of
friends: who was there, what was cooked and how, and a points system per
participant. Since v2.0 one site hosts **several groups**, each with its
own members, asados and standings, completely separate from the others.

**Live deployment**: https://asados.pythonanywhere.com

> **Working on the app day to day?** [`WORKFLOW.md`](./WORKFLOW.md) is
> the step-by-step guide, organised by "I want to...": the to-do list,
> making a change, testing, releasing and deploying, data chores, and
> what to do when something goes wrong, with every command ready to copy.

> **Using an AI assistant (Claude Code, etc.) on this project?** See
> [`CLAUDE.md`](./CLAUDE.md) first — it explains the *reasoning* behind
> the design decisions (the points formula, the map choice, the login
> setup, why weights are "frozen", why each group has its own database
> file) that aren't obvious from the code alone.
> [`CHANGELOG.md`](./CHANGELOG.md) says what changed and when.

## How the data is stored (v2.0+)

```
accounts.db                  <- logins, the list of groups, who's in which group
groups/parrilla-y-alma.db    <- one file per group: its asados, members, points...
groups/<another-group>.db
```

Everyone logs in on the same page; the app opens **only** the logged-in
person's group file, so one group can never see another's data. For now
each login belongs to exactly one group. Groups are created by the site
owner from the terminal (`manage_groups.py`); each group's admins then
add their own members from the app's **Configuración** page.

## How to run it locally

1. **Install Python 3** if you don't have it (python.org).
2. **Open a terminal** in this folder.
3. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```
4. **Set up the data.** Pick the one that matches your situation:
   - **You have an `asados.db` from before v2.0** (e.g. one downloaded
     from the live site) — convert it. This only COPIES it into the new
     layout; `asados.db` itself is never modified:
     ```
     python migrate_to_groups.py
     ```
   - **Brand-new, empty install** — create the first group together
     with its first admin:
     ```
     python manage_groups.py create parrilla-y-alma "Parrilla y Alma" nico "nico" "Don Nicola"
     ```
5. **Run every migration** (safe to run any time — each one says
   "already present" if there's nothing to do, and runs on every
   group). This is the same list, in the same order, as the deploy's
   step 3 below; keep the two in step:
   ```
   python migrate_add_cortes.py
   python migrate_fix_schema_drift.py
   python migrate_to_groups.py
   python migrate_locations_unique_name.py
   ```
6. *(Optional)* **Fill a test group with random data**, so you have
   something to click around and filter. ⚠️ It writes into the group
   you name — use a throwaway one, never a group whose standings matter:
   ```
   python manage_groups.py create prueba "Prueba" prueba "prueba" "Prueba Admin"
   python seed_random_asados.py prueba 150
   ```
7. **Run the app:**
   ```
   python app.py
   ```
8. **Open your browser** to http://127.0.0.1:5000 — you'll hit a login
   page first.

### Refreshing your local copy with the live data

The live site is always ahead of your machine (the group adds asados
there). To test against current data:

1. Download `groups/parrilla-y-alma.db` **and** `accounts.db` from
   PythonAnywhere's **Files** tab. Download them together — a group
   file without the matching `accounts.db` has nobody who can log in.
2. Locally, move your current `accounts.db` and `groups/` folder aside
   (rename them; don't delete until you're sure).
3. Put the downloaded files in their place, then run the migrations
   (step 5 above).

Never upload a local file over a live one: the live files are the
real, authoritative copy.

## Other useful commands

```bash
# Groups (site owner only — anyone with this terminal)
python manage_groups.py list                       # every group, its member count and export token
python manage_groups.py rename <slug> "<New name>" # the slug and file never change, only the name
python manage_groups.py create <slug> "<Name>" <admin_user> <admin_password> "<Admin display name>"

# Add one person to a group from the terminal (group admins can also
# do this from Configuración). Usernames are unique across the whole site.
python create_user.py <group-slug> <username> <password> "<Name>" [admin|normal]

# On-demand backup of accounts.db + every group, into backups/
# (each group's file is ALSO backed up automatically on every new asado).
python backup_db.py [retention_days]

# After editing the cow diagram (vaca_svg.svg) in Inkscape: check that
# every cut still has exactly one correctly-named region, then
# regenerate the partial the app actually renders. Never edit
# templates/_cow_svg.html by hand — this overwrites it.
python check_cow_svg.py vaca_svg.svg
python build_cow_partial.py
```

## Project structure

```
As_app/
├── WORKFLOW.md             <- Step-by-step guide: what to do, and the commands for it
├── app.py                  <- Flask routes, login/session logic (the "brain")
├── accounts.py             <- Logins, groups and memberships: the ONE place "which group?" is decided
├── accounts_schema.sql     <- Tables of accounts.db (never drops anything)
├── schema.sql              <- Tables of a group's database (only ever for a NEW, empty group)
├── config.py               <- Point weights + the points formula (EDIT HERE to tweak scoring)
├── asado_record.py         <- THE place an asado is saved/edited/deleted (validation, frozen weights, child rows)
├── activity_log.py         <- Writes the "who changed what" log + builds edit diffs
├── backup_db.py            <- Safe SQLite snapshot helper (used automatically + manually)
├── manage_groups.py        <- Terminal tool: create / list / rename groups
├── create_user.py          <- Terminal script to add a login to a group
├── migrate_add_cortes.py   <- Additive schema migration (the pattern for future ones)
├── migrate_fix_schema_drift.py <- Adds 3 missing FK indexes + the locations NOT NULL constraints
├── migrate_to_groups.py    <- v2.0: converts the old single asados.db into the groups layout
├── migrate_locations_unique_name.py <- v2.0.1: locations.name UNIQUE for groups created since 2.0
├── vaca_svg.svg            <- SOURCE artwork for the cow diagram (edit this in Inkscape)
├── build_cow_partial.py    <- Turns vaca_svg.svg into templates/_cow_svg.html
├── check_cow_svg.py        <- Validates the drawing against config.py's cut list
├── seed_random_asados.py   <- Fills a (test!) group with random data
├── requirements.txt        <- Python packages needed
├── CLAUDE.md               <- Context/decisions notes (the "why") — see above
├── CHANGELOG.md            <- What changed, per version
├── Phases                  <- The original roadmap this was built against
├── secret_key.txt          <- Auto-generated on first run. NEVER commit (gitignored)
├── accounts.db             <- Logins + groups (gitignored)
├── groups/                 <- One database per group (gitignored)
├── asados.db               <- The pre-v2.0 database; kept untouched as a fallback (gitignored)
├── export_token.txt        <- Pre-v2.0 export token; copied into accounts.db, no longer read (gitignored)
├── backups/                <- Snapshots: backups/<group-slug>/ and backups/accounts/ (gitignored)
├── templates/              <- HTML pages (Jinja2)
│   ├── base.html               (shared layout: navbar, footer)
│   ├── login.html              (login form)
│   ├── index.html              (home: list of asados, with filters)
│   ├── new_asado.html          (create-asado page)
│   ├── view_asado.html         (asado detail; edit in place; admin sees delete)
│   ├── _asado_form.html        (shared create/edit form fields + live points preview)
│   ├── _location_picker.html   (shared address autocomplete + Leaflet map modal)
│   ├── _icons.html             (the app's line icons: icon("name") macro, Lucide, ISC)
│   ├── _brand.html             (the flame brand mark; same drawing as static/favicon.svg)
│   ├── _cow_diagram.html       (interactive cow: caption + hover/click behaviour)
│   ├── _cow_svg.html           (GENERATED from vaca_svg.svg — do not edit by hand)
│   ├── cortes.html             (beef-cut reference page)
│   ├── user_profile.html       (one person's stats, chart and history)
│   ├── resumen.html            (standings table, sortable + filterable)
│   ├── base_asados.html        (flat spreadsheet view + CSV export)
│   ├── ubicaciones.html        (reusable saved-locations pool)
│   ├── activity_log.html       (who created/edited/deleted what, and when)
│   └── config.html             (profile settings + admin user management)
├── static/
│   ├── style.css           (all the visual styling)
│   └── favicon.svg         (browser-tab icon: the brand flame)
└── .claude/skills/         <- Claude Code skills (development only, never served)
    ├── smoke-test/             (smoke_test.py: checks the whole app on throwaway data)
    ├── new-migration/          (schema-change procedure, template, compare_schema.py)
    └── release/                (release checklist + release_check.py)
```

## Features

- **Groups** — one site, many separate competitions. Each group has its
  own database file, members, asados, points, saved locations and
  activity log; nothing is shared between groups. The footer shows
  which group you're in.
- **Login** — session-based username/password, one login page for
  everyone. No public sign-up: accounts are created by a group's admin
  (in-app) or via `create_user.py`. Roles are `admin` or `normal`, **per
  group**. Usernames are unique across the whole site.
- **Asados** — date, name, description, one or more meat types, cooking
  method, surface, venue, an optional address/map pin, headcount and total
  weight. Any member can add or edit any of their group's asados;
  **deleting is admin-only**.
- **Points** — calculated per participant from the formula in `config.py`
  (the same rules for every group, for now), then **frozen**: changing a
  weight later never rewrites history.
- **Resumen** (`/resumen`) — the standings table, one row per member, with
  filters (year, semester) and sortable columns.
- **Base de Asados** (`/base-asados`) — flat spreadsheet view (one row per
  participation) with a full CSV export, plus a token-gated version of
  that same export (`/export/base-asados.csv?token=...`) meant for
  Google Sheets `IMPORTDATA()` → Looker Studio dashboards. Each group
  has its own token (`manage_groups.py list`). See `CLAUDE.md`'s
  "Looker Studio / Google Sheets export" section for why it's
  token-gated instead of login-gated.
- **Cortes de Vacuno** — an interactive, hand-drawn Chilean beef-cuts
  diagram. Pick "Corte de Vacuno" on the asado form and the cow
  appears: hover or tap a region to see the cut's name, click to
  record it. `/cortes` shows the same diagram as a read-only
  reference, plus the icon legend for the other meat types. The cuts
  are descriptive only — **they never affect points**.
- **Ubicaciones** (`/ubicaciones`) — a reusable pool of saved places to
  quick-fill the asado form, so a recurring spot doesn't need retyping.
- **Registro de Actividad** (`/actividad`) — who created, edited, or deleted
  each asado, with a field-by-field diff of every edit.
- **Automatic backups** — every new asado triggers a safe SQLite snapshot
  of that group into `backups/<group-slug>/`.
- **Mobile-friendly** — responsive layout; the navbar collapses to a ☰ menu
  on narrow screens.

## Deploying an update

There's no CI/CD. Deploying is a short manual checklist in a
PythonAnywhere **Bash console**, plus one button on the **Web** tab.

> **Upgrading the live site from 1.x to 2.0?** That one deploy is
> different — follow [the one-time v2.0 upgrade](#one-time-upgrade-from-1x-to-20)
> below instead, then use this checklist from then on.

The live site runs against its own `accounts.db` and `groups/` on
PythonAnywhere's disk — **completely separate files** from your local
ones, holding the real entries. Nothing below ever overwrites them;
they're gitignored, so `git pull` cannot touch them.

### The four steps

```bash
# 1. Go to the code and take a backup before anything else (accounts.db
#    and every group). The migrations back up too, but this one is
#    yours: it costs a second and it is the thing you will want if a
#    deploy ever goes sideways.
cd ~/asados
python3 backup_db.py

# 2. Pull the new code. This does NOT restart the site — the old code
#    keeps serving visitors while you finish the remaining steps.
git pull

# 3. Apply any schema changes. ALWAYS run EVERY migration, oldest
#    first, on every deploy. Each is additive and idempotent: one
#    that has already been applied prints "already present" and
#    changes nothing — and each runs on EVERY group's database.
#    That is the point - there is then nothing to work out about
#    whether this particular release "needs" it.
python3 migrate_add_cortes.py
python3 migrate_fix_schema_drift.py
python3 migrate_to_groups.py
python3 migrate_locations_unique_name.py
```

**4. Click "Reload" on the Web tab.** The new code goes live here, and
only here.

### Why the order matters

**Reload last.** Reloading before step 3 would put new code live
against databases that don't have the new table yet — every asado
page would throw `no such table` until the migration caught up. Pulling
and migrating while the *old* code is still serving means visitors
never see a broken page.

### What step 3 prints, and what to look for

Each migration reports every table's row count before and after, once
per group, so you can see with your own eyes that nothing was lost:

```
asado_cortes was ALREADY present — this run changed nothing.

table                      before    after   status
------------------------------------------------------------
users                           6        6   ok
asados                        312      312   ok
participations                348      348   ok
...
------------------------------------------------------------
Migration OK: asado_cortes present, every existing table untouched.
```

`migrate_to_groups.py` just says `ALREADY migrated` after the v2.0
upgrade. Your live numbers will be **bigger than your local ones** —
that's expected; the scripts compare before against after, not
against any fixed number.

If any group's last line says anything other than `Migration OK`,
**stop and do not Reload.** Restore from the backup path it printed.

### Checking it worked

1. Open https://asados.pythonanywhere.com — the small version number in
   the page footer should match `VERSION` in `app.py`.
2. If it shows the *old* version, the Reload didn't take. Reload again.
3. If a style change looks missing, hard refresh (Ctrl/Cmd+Shift+R).
   The stylesheet is cache-busted by that same version number, so this
   is rare, but a browser can still hold an old copy.

### Adding a new group on the live site

No deploy needed — just a Bash console:

```bash
cd ~/asados
python3 manage_groups.py create los-del-sur "Los del Sur" pedro "a-real-password" "Don Pedro"
```

Give Pedro his username and password; he logs in at the same address
as everyone else and adds his group from **Configuración**. No Reload
needed — the app finds new groups on its own. `python3 manage_groups.py
list` shows the group's export token if they want the Google Sheets
link.

### Things not to do on the server

- **Never delete or replace `accounts.db` or anything in `groups/`.**
  They ARE the live data. `accounts.db` alone is every login on the
  site; a group's file is that group's whole history.
- **Never run `schema.sql` by hand against an existing file.** It
  starts with `DROP TABLE`. `manage_groups.py create` is the only thing
  that should ever run it, and it refuses to touch a file that exists.
  (The old `init_db()` one-liner is gone for exactly this reason.)
- **Don't run `seed_random_asados.py` against a real group.** Random
  asados count in the standings like real ones.
- **Don't run `build_cow_partial.py`.** The file it generates
  (`templates/_cow_svg.html`) is committed, so the server already has
  it. That script is for your machine, after editing the drawing.
- **Don't `pip install` unless `requirements.txt` actually changed.**
  It normally doesn't — the app needs only Flask plus the Python
  standard library.

See `CLAUDE.md`'s Phase 6 section for how the deployment is wired up
(paths, virtualenv, the WSGI file's `chdir`).

## One-time upgrade from 1.x to 2.0

v2.0 converts the single `asados.db` into the groups layout. The live
site's data becomes the group **"Parrilla y Alma"**. Do this once, in
one sitting — steps 4 and 5 should be seconds apart.

```bash
# 0. In the browser first: PythonAnywhere -> Files -> download
#    asados.db to your computer, under a dated name
#    (e.g. asados_live_2026-10-20.db). Your offsite copy.

# 1. Backup (this runs the OLD backup script - still the right one).
cd ~/asados
python3 backup_db.py

# 2. Pull v2.0.
git pull

# 3. The existing migrations. Before the conversion they run on
#    asados.db, as always - expect "already present".
python3 migrate_add_cortes.py
python3 migrate_fix_schema_drift.py

# 4. The conversion. Read the table it prints: every row must say "ok",
#    and the last line must say "Migration OK". If not, STOP - don't
#    Reload; nothing has changed for visitors yet.
python3 migrate_to_groups.py
```

**5. Reload on the Web tab — straight away.** Until you do, the old
code is still running and still writing to `asados.db`; an asado saved
in that gap would land in the old file, not in the group.

```bash
# 6. Check nothing slipped into the old file during that gap.
python3 migrate_to_groups.py --verify
```

**7. Log in on the live site** with your usual username and password.
**Everyone has to log in once again** after this upgrade (old login
cookies aren't recognised); their passwords are unchanged. The footer
should read "Parrilla y Alma · v2.0.0", and the Google Sheets link
keeps working with no change — its token was carried over.

**If something goes wrong:** `asados.db` was never modified, so going
back to 1.x is `git checkout v1.7.4` + Reload, and the site picks it up
exactly as it was. The one catch: anything entered *after* the upgrade
lives only in `groups/parrilla-y-alma.db` and would need re-entering.

**Afterwards:** leave `asados.db` and `export_token.txt` where they
are for a few weeks, as the fallback. Nothing reads them any more. Once
you're confident, they can be deleted (`asados.db` still contains the
old password hashes, so don't move it anywhere shared).

## Git release workflow

Use **`/release`** in Claude Code. It runs the safety checks and the
smoke test, bumps the version in all four places (`VERSION` in `app.py`,
`CHANGELOG.md`, the "Currently at" line in `CLAUDE.md`, and the git
tag), and asks before committing, tagging and pushing. The full
walkthrough, including the PythonAnywhere half, is
[`WORKFLOW.md` section 7](./WORKFLOW.md#7-release-and-deploy).

By hand, the shape is below. **Stage files by name, never `git add .`**:
this repo is public, and `git add .` is how the group's real data
nearly got published twice.

```bash
python .claude/skills/release/release_check.py 2.1.1   # all four places agree, no data files staged
git add -- app.py CHANGELOG.md CLAUDE.md <the files you changed>
git commit -m "v2.1.1: what changed"
git tag -a v2.1.1 -m "v2.1.1: what changed"
git push
git push origin v2.1.1
```
