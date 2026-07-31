# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Context for Claude Code (or any AI assistant) working on this project.
This captures the REASONING behind decisions — the "why," not just the
"what" — since that's usually lost when only reading code.

## What this project is

A Flask + SQLite web app for tracking "asado" (BBQ) events among a
group of friends: who attended, what/how it was cooked, and a points
system per participant. Built incrementally, phase by phase, by a
beginner Python coder learning as they go — **please keep comments
detailed and explanatory in any code you write or edit**, the same way
the existing code is commented. Prefer explaining WHY, not just WHAT.

## Commands

There's no build step, package manifest beyond `requirements.txt`, or
test runner configured — this is a single-process Flask app run
directly with Python.

```bash
# Install dependencies
pip install -r requirements.txt

# Create/reset the database (WIPES existing data — schema.sql runs
# DROP TABLE + CREATE TABLE, there is no migration system)
python -c "from app import init_db; init_db()"

# Create a login account (required at least once — no public sign-up page).
# <name> is a display name; [role] is "admin" or "normal" (default "normal").
# You need at least one admin to manage further accounts from /config.
python create_user.py <username> <password> <name> [role]

# Run the dev server (debug=True: auto-reloads, verbose error pages)
python app.py
# -> http://127.0.0.1:5000
```

There is no formal test suite file. Changes have historically been
verified with ad-hoc scripts using Flask's `test_client()` (login flow,
form submission, API responses, DB state after submission) rather than
manual browser clicking. If you make a change, a similar quick
`test_client()` check before considering the change "done" matches the
project's existing habits, especially for anything touching
`calculate_points()`, `/api/points`, or the auth routes.

## Roadmap / phase status

(Source of truth: the `Phases` file at the repo root.)

Phase 1 – Core data model. Define what an "asado" entry looks like (date, host, meat types, quantity, guests, your point system variables, etc.) and get it stored/retrieved from SQLite via a Flask app with plain HTML pages (add entry, list entries).
Phase 2 – Simple login. Add basic username/password authentication so each person can log in before adding/editing entries. Start with Flask's session-based auth (no need for OAuth/Google login yet).
Phase 3 – Edit/delete + permissions. Let users modify only their own entries (or all entries, your call), with basic validation.
Phase 4 – Summary & stats. Aggregate queries (averages, totals, "best asador" leaderboard from your point system) — great intro to SQL aggregation and maybe a charting library like Chart.js.
Phase 5 – Make it responsive. Improve CSS/layout so it works well on phones, since that's your eventual mobile goal.
Phase 6 – Deploy. Put it online (e.g. Render, Railway, Fly.io — all have free tiers) so others can actually use it from their phones.
Phase 7+ – Advanced. Photo uploads, notifications, a proper mobile app wrapper (e.g. Capacitor) or React Native, richer stats/dashboards, etc.

**Currently at the end of Phase 2** (login exists; no edit/delete, no
stats, not deployed yet).

## Architecture

Everything routes through `app.py` — there's no blueprint/package split
yet, just one Flask app with a handful of routes:

- `/login`, `/logout` — session-based auth (see below)
- `/` (`index`) — lists all asados, newest first, with each one's
  participants and points joined in
- `/asado/new` (`new_asado`) — GET shows the form, POST inserts an
  `asados` row plus one `participations` row per selected participant
- `/asado/<id>` (`view_asado`) — detail page for one asado
- `/api/points` — JSON endpoint used only by the live points preview
  in `new_asado.html`'s JavaScript
- `/config` (`config_page`) — "Configuración" page; every logged-in
  user can edit their own `name`/password here (`POST /config/profile`)
- `/config/users/create`, `/config/users/<id>/delete` — admin-only
  (see `admin_required` in `app.py`), lets an admin manage accounts
  from the browser instead of only via `create_user.py`

Data model (`schema.sql`): `users` ← `participations` → `asados`, a
classic many-to-many junction table. `users` has a `role` column
(`admin`/`normal`) gating the `/config/users/*` routes, and a `name`
column (display name, e.g. "Don Nicola") separate from the login
`username`. `participations.points` is calculated once at insert time
and frozen — it is never recalculated if weights/formula change later,
so historical entries keep whatever points they were awarded under the
rules at the time.

Deleting a user from `/config` is blocked if they have any
`participations` rows — `schema.sql` has no `ON DELETE CASCADE`, so an
allowed delete would silently orphan those rows (they'd just vanish
from that asado's participant list via the `INNER JOIN`, not error).
An admin is also blocked from deleting their own account, to avoid a
UI-only lockout.

### The points formula is literal, evaluable text — not code
`config.py`'s `FORMULA` variable (e.g.
`"(0.6 * carne + 0.4 * coccion) * superficie * local * rol"`) IS the
formula, evaluated at runtime with Python's `eval()` inside
`calculate_points()`. This was a deliberate end-point after several
earlier iterations that each had a "formula lives in two places" bug
risk (Python for real calculation, hand-written JS for the live
preview — they drifted out of sync at least once in practice).

**If the points formula/weights ever need to change, `config.py` is
the ONLY file that should need editing.** The browser's live preview
(in `new_asado.html`) asks the server for real numbers via
`/api/points`, and builds its on-screen equation text by substituting
`VARIABLE_LABELS` (also in `config.py`) into the same `FORMULA` string
— so the display can never show a different shape than what's actually
calculated. Do not reintroduce a second, hand-written copy of the
formula's math or shape in JavaScript.

`eval()` is safe here specifically because `FORMULA` only ever comes
from this source file (edited by the developer), never from user
input submitted through a web form.

### Maps: OpenStreetMap + Leaflet, not Google Maps
Chosen specifically to avoid requiring a Google Cloud billing account
for a hobby project. Address autocomplete and reverse geocoding use
Nominatim's free public API (debounced client-side to be respectful of
rate limits), both called directly from the browser in
`new_asado.html`. Don't swap this for Google Maps without discussing it
— it changes the setup burden for the user significantly.

### Login: session-based, accounts created manually, no public sign-up
- No OAuth yet — Flask's built-in `session` (signed cookie) only.
- There is **no public registration page by design**. The first
  (admin) account is created by running
  `create_user.py <username> <password> <name> admin` from the
  terminal; that admin can then create everyone else's accounts from
  `/config` in the browser, or you can keep using the script. Don't add
  a `/register` route without checking first.
- `users.role` is either `"admin"` or `"normal"` (see the `CHECK`
  constraint in `schema.sql`). Only admins can create/delete accounts;
  normal users can only edit their own name/password.
- Participants in an asado **must be existing registered users**,
  selected from a dropdown (`participant_user_id`) — this was a
  deliberate choice (not the original Phase 1 design, which allowed
  free-typed guest names) made in anticipation of Phase 3's "edit your
  own entries" feature needing real accounts to check ownership
  against.
- `secret_key.txt` is auto-generated on first run and is
  gitignored — it must never be committed (it signs session cookies;
  committing it would let anyone forge login sessions).

## Gotchas already hit once (avoid repeating)

- **`.gitignore` leading whitespace**: a previous edit accidentally had
  leading spaces on each line (e.g. `"   asados.db"` instead of
  `"asados.db"`), which silently broke pattern matching and let
  `asados.db` get committed repeatedly. If `.gitignore` seems not to be
  working, verify with `git check-ignore -v <file>` before assuming
  anything else is wrong.
- **`__pycache__/*.pyc` files are already committed** in this repo,
  despite `__pycache__/` being in `.gitignore` — the ignore rule was
  added after those files were first tracked, and gitignore never
  retroactively untracks files already known to git. If you notice
  them, `git rm --cached` is the fix, not editing `.gitignore` again.
- **Schema changes wipe the local database.** `init_db()` runs
  `DROP TABLE` + `CREATE TABLE` from `schema.sql` — there's no
  migration system yet. Any schema change requires recreating the DB
  and, since Phase 2, recreating user accounts via `create_user.py`.
- **Stray empty files/folders** (e.g. `download`, `next fix`) have
  appeared in the repo a few times, likely from drag-and-drop actions
  on the GitHub web UI rather than local Git commands. Harmless, but
  clean up with `git rm` when noticed rather than assuming they're
  intentional. (`Phases` at the repo root is NOT one of these — it's a
  real, tracked file that's the source of the roadmap above.)

## Language conventions

- Code, comments, and this file: English.
- User-facing UI text and form labels: Spanish (`Nombre Asado`,
  `Fecha`, `Ubicación`, etc.) — the app's actual users are
  Spanish-speaking, so keep new UI text consistent with that.
