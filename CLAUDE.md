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

# Fill the DB with <count> randomly-generated asados/participations, for
# trying out filters/Base de Asados/CSV export without typing real data.
# Uses your EXISTING users as participants; adds on top, doesn't wipe.
python seed_random_asados.py <count>

# Make an on-demand backup of asados.db right now (also happens
# automatically on every new asado — see "Automatic backups" below).
python backup_db.py [retention_days]

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

**Currently at the end of Phase 3 + Phase 5 + Phase 6** (login +
edit/delete + mobile responsiveness + deployment all exist; Phase 4's
stats/leaderboard is the only thing still outstanding — Phases 5 and 6
were deliberately done out of order, ahead of Phase 4, at the user's
request). Phase 3 deliberately deviated from its own description
above: editing is open to **every** logged-in user (not "only your own
entries"), while deleting is **admin-only** — see the "Edit/delete
permissions" note below.

**Phase 5 (mobile responsiveness) turned out to need very little new
work** — the app was already close to fully responsive as a side
effect of earlier passes (flexbox layouts with `flex-wrap`,
percentage-based widths, the dedicated `.spreadsheet-wrapper` scroll
container for Base de Asados). Verified at 375px and a stress-test
320px viewport with Playwright screenshots + a horizontal-overflow
check script; found and fixed two real issues rather than a broad
rewrite:
- `.nav-link` tap targets measured ~36px tall — under the ~44px
  minimum recommended for touch. Bumped padding, but ONLY inside the
  existing `@media (max-width: 480px)` block — the desktop navbar
  didn't need the extra height.
- The Leaflet map picker in the location modal (`.map-modal-content`/
  `.map-picker`) was cramped on a phone screen (previously ~300px of
  usable map width) — now widens the modal and uses `60vh` for the map
  height on small screens, giving real room to tap a precise spot.

If you add a new page or component, check it at both breakpoints
before considering it done — this app's whole layout language (flex +
`flex-wrap` + percentage widths, no fixed pixel widths on containers)
is what made the rest of the app responsive almost for free; keep
using that pattern rather than fixed widths.

**Phase 6 (deploy): live on PythonAnywhere's free tier**, not
Render/Railway/Fly.io. The deciding factor was SQLite: this app stores
its whole database as a single `asados.db` file, and Render's and
Railway's free tiers wipe their filesystem on every redeploy — that
would silently delete the database the first time you pushed a code
update. PythonAnywhere's free tier has genuine persistent storage
(SQLite just works, no volume/mount config needed) and stays always-on
(no Render-style cold-start sleep). A Synology NAS (self-hosted via
Docker + a volume mount + Cloudflare Tunnel) was seriously considered
and would also work well, but was set aside in favor of
PythonAnywhere's lower setup effort; revisit if full data ownership or
avoiding a third-party platform ever becomes a priority.

**Canonical live URL: `https://asados.pythonanywhere.com`** — hosted
under a dedicated PythonAnywhere account with username `asados`
(created specifically for this project), not tied to any one person's
own account. An earlier attempt was deployed under a personal account
(`nicolasalk.pythonanywhere.com`) first, then re-deployed from scratch
under the `asados` account for a cleaner, project-branded URL — that
personal-account deployment is retired; don't reference
`nicolasalk.pythonanywhere.com` anywhere going forward, and feel free
to delete that account/deployment whenever convenient (not urgent,
just no longer used).

**How the live deployment is actually wired up** (so a future update
doesn't require rediscovering this):
- Code lives at `/home/asados/asados` on PythonAnywhere (home dir
  `asados` containing a git-cloned folder also named `asados` — a bit
  confusing to read, but harmless), cloned from the same GitHub repo
  (`nlopezk/asados`) this local copy pushes to — deploying an update
  is `git pull` in a PythonAnywhere Bash console, then clicking
  **Reload** on the Web tab. There is no CI/CD; this manual two-step
  is the whole "deploy" workflow for now.
- Dependencies live in a virtualenv at
  `/home/asados/.virtualenvs/asados-venv` (created with
  `mkvirtualenv --python=/usr/bin/python3.10 asados-venv`), referenced
  from the Web tab's "Virtualenv" field.
- The Web app is configured as **Manual configuration**, not
  PythonAnywhere's Flask quick-start wizard (which would have
  generated its own app skeleton and fought with this one).
- The WSGI file PythonAnywhere generates (edited via the Web tab, not
  a file in this repo) does two things beyond the usual
  `sys.path.insert()`: it calls **`os.chdir('/home/asados/asados')`
  before importing `app`**. This matters because `app.py` finds
  `asados.db`/`secret_key.txt`/`schema.sql` via bare relative paths
  (`"asados.db"`, not an absolute path) — without the `chdir`,
  PythonAnywhere's WSGI process could run from some other working
  directory (e.g. the home directory) and the live site would silently
  look for, or even create, `asados.db` in the wrong place.
- `app.run(debug=True, ...)` at the bottom of `app.py` was **not**
  changed for deployment, and doesn't need to be: PythonAnywhere's
  WSGI server imports the `app` object directly and never calls
  `app.run()` at all, so that line only ever affects local
  `python app.py` runs.
- `secret_key.txt` and `asados.db` are separate files on the
  PythonAnywhere filesystem from the ones on any local dev machine —
  expected and correct; never try to sync/share a secret key between
  environments.
- The live site was deliberately started with a **fresh, empty
  database** (`init_db()` + one throwaway `testadmin` account) rather
  than the ~195 asados that exist in the local dev DB — the user's
  explicit call, to use the live deploy for testing first. Bringing
  the real data over later means uploading the local `asados.db` file
  directly via PythonAnywhere's Files tab (**not** running `init_db()`
  again on the server, which would wipe it) — still pending as of this
  writing.
- The automatic per-asado backup (`backup_database()`, called from
  `new_asado()` — see "Automatic backups" above) works identically in
  production: backups land in `/home/asados/asados/backups/` on
  PythonAnywhere's own persistent disk, no extra deployment config
  needed for it.

## Architecture

Everything routes through `app.py` — there's no blueprint/package split
yet, just one Flask app with a handful of routes:

- `/login`, `/logout` — session-based auth (see below)
- `/` (`index`) — lists all asados, newest first, with each one's
  participants and points joined in. Accepts optional `?date_from=`/
  `?date_to=` (inclusive date range), `?year=`/`?month=` (match on just
  that PART of the date via SQLite's `strftime`, independent of each
  other — `month` alone means "that calendar month across every year"),
  and `?user_id=` to filter the list (a plain GET form in `index.html`
  auto-submits on change — no JS fetch needed for the dropdowns; the
  date range uses Flatpickr, see below), and `?page=` to paginate
  (`INDEX_PAGE_SIZE` = 30/page, filters and page compose together —
  page count is computed AFTER filtering)
- `/asado/new` (`new_asado`) — GET shows the form, POST inserts an
  `asados` row plus one `participations` row per selected participant
- `/asado/<id>` (`view_asado`) — read-only detail page by default, with
  a hidden copy of the edit form revealed in place by an "Editar"
  button (pure client-side toggle, no reload/route) — see "Edit/delete
  permissions" below
- `/asado/<id>/edit` (`edit_asado`, POST) — saves changes; any
  logged-in user
- `/asado/<id>/delete` (`delete_asado`, POST) — deletes the asado and
  all its participations; admin-only
- `/api/points` — JSON endpoint used only by the live points preview
  in `new_asado.html`'s JavaScript
- `/base-asados` (`base_asados`) — "Base de Asados": a flat,
  spreadsheet-style view built from `BASE_ASADOS_QUERY` in `app.py`, a
  `participations LEFT JOIN asados LEFT JOIN users`. **One row per
  participation, not per asado** — an asado with 5 participants
  produces 5 rows here, repeating that asado's shared columns each
  time. This is the shape you want for a spreadsheet/CSV export (one
  line per person-at-an-asado); don't confuse it with `index`'s
  one-card-per-asado view or try to reuse one query for both. Includes
  both IDs (`participation_id`, `asado_id`), the coordinates, and every
  frozen weight alongside its category name — it's meant to be the
  complete, auditable export of everything a participation's `points`
  was derived from. Paginated on-screen (`?page=`, `BASE_ASADOS_PAGE_SIZE`
  = 100/page) — but `/base-asados/csv` deliberately ignores pagination
  and always exports every row; if you ever add filters to this page,
  remember to decide explicitly whether the CSV should respect them or
  keep exporting everything. **On-screen `<th>` labels are abbreviated**
  ("Peso Tipo Carne" → "Peso T.Carne", "Latitud" → "Lat.", etc., in
  `base_asados.html`) purely to cut how much this 21-column table has
  to scroll sideways — completely independent from
  `base_asados_csv()`'s own header row, which keeps the full,
  unabbreviated names; if you add a column, decide the on-screen label
  and the CSV header separately, they're two different lists on
  purpose. **Tipo Carne and Ubicación TRUNCATE with an ellipsis
  (`.truncate-cell`/`.truncate-cell-wide` in style.css), they never
  wrap** — these are the two columns that can genuinely run long
  (multiple selected meat types; a full Nominatim address), and an
  earlier version let them wrap onto multiple lines instead, which made
  whichever row had a long value visibly TALLER than every other row —
  breaking the "one row = one line" spreadsheet look this table already
  relies on everywhere else (`white-space: nowrap` on every other
  column, sticky `overflow-y` header, etc.). The truncation lives on an
  inner `<span>` with its own `title="..."` (the full value, shown on
  hover — a plain browser tooltip, no JS), not on the `<td>` itself:
  `max-width`/`text-overflow: ellipsis` on a bare table cell only
  reliably truncates under `table-layout: fixed` (which would need
  every OTHER column to also get an explicit width to look right);
  wrapping the text in its own `display: inline-block` span sidesteps
  that and works regardless of the table's layout algorithm.
- `/base-asados/csv` (`base_asados_csv`) — same rows as above, streamed
  back as a downloadable CSV (UTF-8 with a BOM prefix, so accented
  characters open correctly in Excel on Windows)
- `/config` (`config_page`) — "Configuración" page; every logged-in
  user can edit their own `name`/password here (`POST /config/profile`)
- `/config/users/create`, `/config/users/<id>/delete` — admin-only
  (see `admin_required` in `app.py`), lets an admin manage accounts
  from the browser instead of only via `create_user.py`
- `/actividad` (`activity_log_page`) — "Registro de Actividad": who
  created/edited/deleted which asado, and when. Visible to every
  logged-in user, not admin-only — see the "Activity log" section below
- `/ubicaciones` (`locations_page`), `/ubicaciones/create`,
  `/ubicaciones/<id>/edit` (any logged-in user), `/ubicaciones/<id>/delete`
  (admin-only) — manage the reusable pool of saved locations; see the
  "Recurring locations" section below

Data model (`schema.sql`): `users` ← `participations` → `asados` ←
`asado_tipo_carne`, all classic many-to-many junction tables. `users`
has a `role` column (`admin`/`normal`) gating the `/config/users/*`
routes, and a `name` column (display name, e.g. "Don Nicola") separate
from the login `username`. `participations.points` is calculated once
at insert time and frozen — it is never recalculated if weights/formula
change later, so historical entries keep whatever points they were
awarded under the rules at the time.

### Tipo de Carne is multi-select — a junction table, not a CSV string
An asado can have more than one Tipo de Carne (minimum one) — e.g. both
"Cordero" and "Pollo" at the same event — via `asado_tipo_carne`
(`asado_id`, `tipo_carne`, `tipo_carne_weight`), the same many-to-many
pattern `participations` already uses for users, not a comma-joined
string crammed into `asados.tipo_carne` (that column doesn't exist
anymore). This was a deliberate choice over string concatenation: it
lets each selected type's own weight be FROZEN individually (see the
frozen-weights note above), so Base de Asados can show the complete
picture of what was chosen, not just the final number.

**Only the highest-weight selected type counts toward points — multiple
types never stack or average.** `config.py`'s `get_shared_weights()`
takes a LIST of Tipo de Carne now (not a single string) and returns
`max()` of their weights as `"carne"`; the FORMULA itself is completely
unchanged, still just one `carne` variable. `asados.tipo_carne_weight`
stores that single winning max (parallel to `coccion_weight`/etc.,
still one column, still what actually feeds the formula) — while
`asado_tipo_carne` stores every selected type's OWN individual frozen
weight, so a later look at an old asado can show e.g. "Cordero (1.0),
Pollo (0.3)" and it's obvious *why* Cordero won, not just that it did.

**Participants replace wholesale on edit, same as before — now Tipo de
Carne does too.** `edit_asado()` deletes all of an asado's
`asado_tipo_carne` rows and re-inserts fresh ones from the submitted
form, exactly mirroring how it already handles `participations`. The
`_asado_form.html` UI enforces a MINIMUM of one selected type (the ✕
remove button hides itself once only one row is left — see
`updateTipoCarneRemoveButtons()`), unlike participants, which are
allowed to go down to zero.

**Base de Asados / CSV concatenate multiple types with `"; "`
(semicolon), not a comma.** `BASE_ASADOS_QUERY` does the joining AT THE
SQL LEVEL, via a `GROUP_CONCAT` subquery aggregated per `asado_id` and
then LEFT JOINed onto the per-participation rows — so `base_asados.html`
and the CSV export both just print `row["tipo_carne"]` with zero Python
string-joining logic of their own, automatically staying in sync. A
comma was deliberately avoided even though `csv.writer` would quote it
correctly (RFC 4180) — a comma sitting inside one CSV field still reads
ambiguously to a human just glancing at the raw text, and semicolon
avoids that entirely. `index.html`'s cards and `view_asado.html`'s
read-only summary do their own equivalent "; ".join(...) in Python,
since those aren't reading from `BASE_ASADOS_QUERY`.

**The individual weights that fed into `points` are frozen too, not
just the final number.** `asados.tipo_carne_weight`/`coccion_weight`/
`superficie_weight`/`local_weight` (shared by every participant of that
asado) and `participations.rol_weight` (per participant) are looked up
from `config.py` and stored at creation time via `get_shared_weights()`
and `get_rol_weight()` — two small helpers `calculate_points()` itself
also calls internally, so the lookup logic exists in exactly one place.
Without this, a later edit to a weight in `config.py` would leave old
entries' stored `points` correct but with no record of *what weight*
produced them (the category names stored on `asados`/`participations`
alone aren't enough once `config.py` has moved on). If you add a new
scored variable to the formula, freeze its weight the same way.

Deleting a user from `/config` is blocked if they have any
`participations` rows — `schema.sql` has no `ON DELETE CASCADE`, so an
allowed delete would silently orphan those rows (they'd just vanish
from that asado's participant list via the `INNER JOIN`, not error).
An admin is also blocked from deleting their own account, to avoid a
UI-only lockout. `get_db()` also runs `PRAGMA foreign_keys = ON` on
every connection (SQLite doesn't enforce declared `FOREIGN KEY`
constraints unless told to) as a backstop behind that manual check —
don't remove this pragma, it's the only thing making the `FOREIGN KEY`
lines in `schema.sql` do anything at all.

**Display name vs. login username**: every user-facing view (home page
participant list, `view_asado.html`, the participant picker in
`new_asado.html`, the navbar) shows `users.name` (e.g. "Don Nicola"),
never `users.username` (e.g. "nico") — `username` is only shown on the
admin user-management table in `/config`, where the login handle
itself is the relevant piece of information. Keep this split when
adding new views: `name` for anything a group member reads, `username`
only where you're specifically talking about the login credential.

### Edit/delete permissions, and the shared create/edit form
Any logged-in user can edit any asado (not just their own) — this was
an explicit product decision for a small trusted friend group, not an
oversight; don't add an "only your own entries" restriction to
`edit_asado()` without checking first. **Deleting is admin-only**
(`delete_asado()` is `@admin_required`), since it's destructive
(removes the asado AND every participant's points for it) and
irreversible — the asymmetry (open edit, gated delete) is deliberate.

`view_asado.html` shows a **read-only summary by default**, not the
edit form directly — an "Editar" button reveals the (already rendered,
just `.hidden`-classed) edit form in place via plain JS, no separate
route or page reload. This was a deliberate revision after first
building "the whole page is always an editable form": since editing is
open to every user, landing straight in an editable form on every
click-through risked turning a casual "let me check this asado" visit
into an accidental change. "Cancelar" inside the edit form is a plain
link back to the same `view_asado` URL (not a JS "hide" toggle) —
reloading is the simplest way to guarantee any unsaved, un-submitted
edits are discarded rather than lingering in the hidden DOM.

`templates/_asado_form.html` is the ONE place the create/edit form's
fields and live-points-preview JS exist — `new_asado.html` and
`view_asado.html` both `{% include %}` it, passing `asado`
(`None` for create, the existing row for edit) and
`existing_participants` (a list of `{user_id, rol}` dicts, empty for
create) to control prefilling. `app.py`'s `asado_form_context(db)`
builds the rest of the shared context (dropdown options, the `weights`
dict, `registered_users`) so both routes can't drift apart on that
either. **If you add a field to the asado form, add it to this one
partial** — don't hand-copy it into both templates.

**Editing recalculates and re-freezes weights/points from CURRENT
config.py values**, exactly like creating a new asado does — an edit
is treated as a new "freezing moment" (see the frozen-weights note
above). This means editing an old asado whose category text hasn't
changed can still change its stored points, if `config.py`'s weights
were tweaked since it was created — that's intentional: the numbers
shown right after a save should always match what the form says now.

**Participants are replaced wholesale on every edit**: `edit_asado()`
deletes ALL of that asado's `participations` rows, then re-inserts
fresh ones from the submitted form, rather than diffing which rows
changed. `participation_id` is therefore NOT a stable reference across
edits of the same asado's participant list — don't build a feature
(e.g. a permalink, or a comment thread) that assumes a `participation_id`
survives an edit.

### Automatic backups — currently only on new_asado(), not edit/delete
`backup_db.py`'s `backup_database()` is called from `new_asado()`
right after `db.commit()`, so every new asado triggers a fresh, safe
copy of the whole database into `backups/` (gitignored, next to
`app.py`, never served by Flask since it isn't under `static/`). This
was a deliberate choice to mirror "autosaves whenever something
changes" (the user's own framing: "like Google Sheets") rather than a
scheduled/cron backup — cheaper in practice too, since it never backs
up when nothing changed.

**It uses `sqlite3.Connection.backup()`, not a plain file copy.** A
naive `shutil.copy()` of a SQLite file has no way to know if it's
mid-write; `backup()` is SQLite's own mechanism for taking a
consistent snapshot of a *live* database safely. Don't swap this for a
plain file copy to "simplify" it — that would reintroduce exactly the
corruption risk this was built to avoid.

**The backup call is wrapped in try/except** — a failed backup (full
disk, permissions, ...) must never prevent the user's asado from
saving or make the request look like it failed when it didn't. If you
add backup calls elsewhere, keep them non-fatal the same way.

**Scope gap, on purpose for now**: `edit_asado()` and `delete_asado()`
do NOT trigger a backup, only `new_asado()` does — the user's request
was specifically "every time a new asado is added." If this ever
matters (e.g. someone wants a backup right before a risky edit), the
same `try: backup_database(database=DATABASE) except Exception: ...`
snippet can be dropped into those routes' `db.commit()` too.

**What this does and doesn't protect against**: rolling local backups
guard against bad data — an accidental edit, a bug, wanting to roll
back a day. They do NOT protect against losing the whole hosting
account/server, since backups live on the same disk as the live
database. Offsite copies (e.g. periodically pulling `backups/` down to
the user's Synology NAS) were discussed and intentionally deferred —
a manual step for now, not automated.

### Activity log — who created/edited/deleted which asado, and when
`activity_log.py` holds three write functions (`log_create`,
`log_edit`, `log_delete`) and one diff builder (`diff_asado`), called
from `new_asado()`/`edit_asado()`/`delete_asado()` in `app.py` **before**
each route's own `db.commit()`, never after — a log entry and the
asado change it describes are written in the same transaction on
purpose, so one can never be saved without the other (unlike the
backup call in `new_asado()`, which deliberately runs AFTER commit —
see "Automatic backups" above for why that one's different).

**Scope, deliberately narrow for now**: only asado create/edit/delete
is logged. User-account management (`/config/users/*`) and profile
edits are NOT — this was an explicit scope call, not an oversight; ask
before extending it there.

**Every field that changed on an edit is recorded, not just the fact
that an edit happened** — `diff_asado()` compares the asado's row
*before* the update (fetched at the very top of `edit_asado()`, before
anything else runs) against what was just submitted, plus the
before/after Tipo de Carne list and before/after participant list
(each resolved to `"Nombre (Rol)"` strings), and returns only the
fields that actually differ. An edit that resubmits the form with
nothing really changed still gets ONE `activity_log` row (proof the
save happened) but zero `activity_log_changes` rows — don't read "no
changes listed" as "nothing was logged." `latitude`/`longitude` are
deliberately NOT diffed as their own fields (a pixel-level pin nudge
with the same typed address would just add noise); `location`'s text
already covers the meaningful case. Create/delete actions never get
diff rows at all — comparing a brand-new asado against "nothing", or
vice versa, isn't useful; the single `activity_log` row already says
who/what/when for those two.

**A separate `activity_log_changes` table, one row per changed field —
not a JSON blob column.** Same reasoning as `asado_tipo_carne` over a
concatenated string (see below): keeps every individual diff queryable
and consistent with how this app already avoids blob/string-packed
data.

**`user_id`/`asado_id` are real FOREIGN KEYs with `ON DELETE SET
NULL`, not `ON DELETE CASCADE` or a manual pre-delete block.** Deleting
a user account or an asado must NEVER be blocked just because old log
entries reference it — that would be a foot-gun no one would expect
("why can't I delete this asado, it doesn't even exist anymore?").
Unlike `delete_user_route`'s existing check (blocked if the user has
`participations`), a user or asado with ONLY activity-log history is
freely deletable; the FK just nulls the reference out automatically.
This is exactly why `activity_log` ALSO stores `actor_name`/
`asado_nombre`/`asado_date` as FROZEN plain text at write time (same
"freeze it" pattern as weights/points elsewhere in this app) — the log
entry stays fully readable ("Nico eliminó el asado 'Épico Junte'")
even after the user or asado it names is long gone.

**Visible to every logged-in user, not admin-gated** — `/actividad`
uses `@login_required`, not `@admin_required`. Deliberate: since ANY
user can already edit ANY asado (see "Edit/delete permissions" below),
this log is what makes that openness accountable to the group, not
something that itself needs restricting on top of it.

### Recurring locations — a quick-fill pool, deliberately NOT linked to asados
`locations` (schema.sql) holds a small, user-curated pool of named
places ("Casa de Nico", "Quincho El Bosque") — managed at `/ubicaciones`
and exposed on the asado form (`_asado_form.html`) as an "Ubicación
guardada" `<select>` above the existing address/map picker.

**`name`/`address`/`latitude`/`longitude` are all NOT NULL on this
table** — unlike `asados.location` (which stays free/optional, see its
own comment in schema.sql), a location saved to the reusable pool is
useless as a future quick-fill without a real address AND coordinates.
Enforced three ways at once, deliberately redundant: (1) the HTML
`required` attribute, (2) friendly `?error=` checks at the top of
`create_location()`/`edit_location()` in `app.py`, (3) `NOT NULL` in
`schema.sql` as the last-resort DB-level backstop — same "form-required
= DB NOT NULL" pattern `asados.nombre`/`coccion`/etc. already use.
`maybe_save_location()` (called from the asado form's "Guardar esta
ubicación" checkbox) mirrors the same check but SILENTLY no-ops instead
of erroring if address/lat/lon are missing — very possible there, since
the asado form's own location can be freely typed without ever being
geocoded (no suggestion/map point picked); the asado itself must still
save fine either way, it just won't be added to the pool.

**`_location_picker.html` is the ONE place the address-autocomplete +
Leaflet map-modal component exists** — extracted out of
`_asado_form.html` specifically so `/ubicaciones`' own "Nueva Ubicación"
form could reuse the exact same picker (same reasoning CLAUDE.md
already gives for why `_asado_form.html` itself is a shared partial:
two hand-copied map pickers would eventually drift). It takes
`location_value`/`latitude_value`/`longitude_value` (prefill),
`location_field_name` (which `name=` the address input submits under —
`"location"` for the asado form, `"address"` for `/ubicaciones`, since
that's each route's own column name), and `location_required` (adds
HTML `required` on the address input, AND blocks that `<form>`'s submit
via JS until latitude/longitude actually have values — `/ubicaciones`
sets this, the asado form doesn't, since its own location stays
optional). **Only ever include this partial ONCE per page** — its
`<script>` declares top-level `const`s and fixed element ids
(`#location`, `#map-modal`, ...) that would collide if included twice.
This is exactly why, on `/ubicaciones`, only the "Nueva Ubicación" form
got the full picker — each EXISTING saved location's own inline edit
row deliberately kept plain required text/number fields instead of a
second picker instance (a real product/scope decision, not a
last-minute cut corner: making N simultaneous map-picker instances
safe on one page needs a per-instance id-prefix refactor this
component doesn't have yet — revisit if that's ever actually wanted).

**Coordinates are shown, but never directly editable, on the picker
itself.** `_location_picker.html` renders a read-only "📍 Coordenadas:
lat, lon" line under the address field (`#coordinates-display`),
kept in sync by `updateCoordinatesDisplay()` — called from
`selectAddress()` (covers both the autocomplete-click and map-click
paths) and, cross-`<script>`-tag, from `_asado_form.html`'s "Ubicación
guardada" dropdown handler too (same "top-level `const`/function
declared in one `<script>` tag stays visible to a later one on the
same page" mechanism the shared `locationInput`/`latInput`/`lonInput`
already rely on). It's deliberately NOT an editable field: latitude/
longitude only ever come from picking a real suggestion or map point,
never free-typed, so there'd be nothing meaningful to type into a
coordinates input directly — this is purely a "here's what got
captured" confirmation.

**"Ubicaciones Existentes" is a compact spreadsheet-style TABLE**
(`ubicaciones.html`, reusing the same `.spreadsheet-table`/
`.spreadsheet-wrapper` classes Base de Asados already uses), not one
big stacked card per location — one row per saved place, editable
cells, a 💾 button per row applies just that row's changes. Each row's
`<form>` is declared SEPARATELY, right before the table (not nested
inside `<table>`/`<tbody>` — a `<form>` isn't valid table-model
content there; browsers silently hoist it out and break the layout),
and every cell's input/button is tied to its row's form via the
standard HTML5 `form="location-form-<id>"` attribute rather than DOM
nesting. The delete button reuses the same `formaction` trick as
before (same form, different target URL for that one button).

**Compacted horizontally on request** (it was noticeably wide with 4
separately-boxed fields per row): Latitud/Longitud share ONE
"Coordenadas" `<th>`/`<td>` — still two independently-submitted
`name="latitude"`/`name="longitude"` inputs, just laid out side by
side (`.loc-coord-pair`) instead of two full columns each with their
own header/border/padding overhead. "Agregada por" isn't its own
column at all anymore — it's a `title` tooltip on the Nombre cell,
since it's nice-to-know info, not something worth a whole column's
width. Purpose-specific width classes (`.loc-name-input`,
`.loc-address-input`, `.loc-coord-input`) replace one generic
`input[type=text]`/`input[type=number]` rule, since Nombre/Dirección
need real room to read a value and a coordinate never does. The
browser's default up/down spinner arrows on Latitud/Longitud are
removed too (`.spreadsheet-table input[type="number"]` in style.css) —
they don't add anything on a coordinate field (nobody increments a
latitude by 1 with a click); this is scoped to `.spreadsheet-table`
only, not applied globally, since spinners ARE genuinely useful on
fields like "Cantidad de personas" elsewhere.

**Picking a saved location is a one-time PREFILL, not a live link.**
Choosing one just copies its `address`/`latitude`/`longitude` into the
SAME `location`/`latitude`/`longitude` fields the free-typed/map-picked
flow already fills (see the dropdown's `onchange` handler in
`_asado_form.html`) — `asados` has no `location_id` foreign key to
`locations` at all, on purpose. This means later renaming or deleting a
saved location on `/ubicaciones` can NEVER retroactively change any
asado that already used it; each asado's `location` text is a plain,
independent snapshot from the moment it was saved — same "frozen at
the moment of use" philosophy as weights/points elsewhere in this app,
just applied to convenience data instead of scoring data. If you ever
need to know which saved location (if any) a past asado's address
corresponds to, that's a manual/fuzzy lookup by text, not a join —
there's no stored relationship to query.

**Using a one-off, never-saved location (the app's original behavior,
before this feature existed) still works exactly as before, with zero
extra clicks.** The "💾 Guardar esta ubicación para reutilizarla más
adelante" checkbox next to the location fields defaults UNCHECKED —
only ticking it (and giving it a short name in the field that then
reveals itself) adds the just-used address/pin to the pool via
`maybe_save_location()` in `app.py`, called from `new_asado()`/
`edit_asado()` right before their own `db.commit()`. Leaving it
unchecked is a complete no-op as far as `locations` is concerned.

**Duplicate names are silently skipped, not an error.** If the
submitted `location_name` (case-insensitive) already matches an
existing saved location, `maybe_save_location()` just returns without
inserting — the asado itself still saves normally either way. Fixing
or renaming an already-saved location is what the `/ubicaciones` page's
own edit form is for, not something a same-named checkbox submission
should silently overwrite.

**Permissions mirror the exact asado create/edit/delete asymmetry**:
any logged-in user can add a new saved location or edit an existing
one's name/address/coordinates (`create_location`/`edit_location`, both
`@login_required`); only an admin can remove one from the pool
(`delete_location`, `@admin_required`) — same reasoning as
`delete_asado`: removing a shared resource other people may be relying
on is the one genuinely destructive action here, editing/adding isn't.

**`created_by` is a real FOREIGN KEY with `ON DELETE SET NULL`, not a
frozen name column** — unlike `activity_log`'s `actor_name`, this isn't
an audit trail (nobody needs to prove who added a location after the
fact the way they'd need to prove who edited an asado), so a live
`LEFT JOIN` to `users.name` for display is enough; if that user account
is later deleted, the "Agregada por ..." line just stops showing a
name instead of needing its own frozen copy.

### CSRF protection
Every POST route (`login`, `/config/profile`, `/config/users/create`,
`/config/users/<id>/delete`, `/asado/new`, `/asado/<id>/edit`,
`/asado/<id>/delete`) is protected by a
hand-rolled token check in `app.py`, not a library like Flask-WTF —
kept dependency-free like the rest of the project (`requirements.txt`
is just `Flask`). The mechanism: `ensure_csrf_token()` (a
`before_request` hook) puts one random token in `session["csrf_token"]`
the first time a browser shows up; `csrf_token()` is injected into
every template via `@app.context_processor` so forms can embed it as
`<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`;
`validate_csrf_token()` (another `before_request` hook, checked on
every POST regardless of route) rejects the request with 400 if the
submitted token doesn't match the session's. **Any new POST form must
include that hidden input, or it will always 400.**

### CSV export sanitizes formula-injection payloads
`sanitize_csv_cell()` in `app.py` prefixes any exported string starting
with `=`, `+`, `-`, or `@` with a `'`, so a value like `=HYPERLINK(...)`
placed in an asado's `nombre`/`location` or a user's own `name` (both
editable by any logged-in user) can't turn into a live formula when
someone opens `base_asados.csv` in Excel/Sheets. Applied generically by
type (only `str` values are touched — numeric columns pass through
untouched), so new columns added to `BASE_ASADOS_QUERY` are covered
automatically as long as they're written out via the same
`sanitize_csv_cell(value) for value in (...)` pattern in
`base_asados_csv()`.

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

### Visual design: "old money Texas classic", informed by a real book
`static/style.css` targets a specific look — walnut-wood browns and
leather tones for backgrounds/surfaces, a burgundy/scarlet red as the
accent, a muted brass/gold used sparingly for trim. This wasn't
invented from a mood board: it was revised after actually studying
`extras/The Designer's Dictionary of Color` (Sean Adams) — a real PDF
in this repo, no text layer (image-only pages), opened by rendering
pages to PNG with PyMuPDF and reading them directly. Specific pages
that drove decisions, if this direction ever needs revisiting:
- **Brown chapter** (p.209): "a palette of shades of brown... can read
  as sophisticated and solid" — validated the wood-brown backgrounds.
- **Scarlet chapter** (p.93): other names include Burgundy and Brick;
  cultural meanings cite Catholic cardinals' robes and the benches of
  the British House of Lords — i.e. prestige and power, not fire. This
  is why the accent is a burgundy/scarlet, not the brighter orange-red
  it started as.
- **Metallic chapter** (p.245): "gold... can add elegance and
  richness," but the book also warns overuse cheapens it — this is why
  `--color-gold` appears in exactly ONE place (the navbar's
  bottom-border "brass rail"), not scattered around as a general
  accent.
- **The book's own heading AND body text** (photographed and zoomed
  into directly) turned out to be a single classic, moderate-contrast
  serif in the Garamond/Caslon tradition — not the softer, quirkier
  'Fraunces' this app used before. That's why headings now use 'EB
  Garamond', the closest Google Fonts match.
- The book's own section labels ("CULTURAL MEANINGS", "SUCCESSFUL
  APPLICATIONS") are small, uppercase, and letter-spaced rather than
  plain bold text — copied into this app's form labels, filter labels,
  and table headers (`text-transform: uppercase; letter-spacing: ...`).

CSS custom properties are still defined once at `:root` (`--color-bg`,
`--color-surface`, `--color-accent`, etc.) — change the palette by
editing those variables, not by hunting down individual hex codes.
Headings (and prose-like text) use 'EB Garamond'; compact UI chrome
(buttons, table cells, form inputs) stays on 'Inter' for small-size
legibility — both loaded from Google Fonts in `base.html` (same CDN
pattern as Leaflet), with system-font fallbacks if that CDN is
unreachable.

**Two different reds, on purpose**: `--color-accent` (deep burgundy)
is for FILLS — navbar, primary/secondary button backgrounds — where
white/cream text sits on top of it, so the fill itself can be dark.
`--color-accent-text` (a brighter brick-red, closer to the book's
actual Scarlet swatch) is for TEXT ON a wood-toned surface — links,
card titles, `.weight-hint` — because the darker burgundy is nearly
illegible as text against the similarly dark `--color-surface`/
`--color-bg`. If you add a new red usage, pick whichever variable
matches which side of that contrast pair you're on; don't just reach
for `--color-accent` by habit.

Buttons and button-like links (including `<a>` tags styled as
buttons!) are filled, never bare outlines, and never keep the
browser's default underline — `.secondary-button`/`.primary-button`
both set `text-decoration: none` explicitly for exactly this reason
(an `<a class="secondary-button">` like "Exportar CSV" or "Cancelar"
kept an underline for a while before this was caught — the class
alone doesn't remove link styling, you have to say so). A fully
transparent button also read as unfinished/broken against the textured
wood background, especially ones not sitting directly next to a filled
`.primary-button` for contrast — keep new secondary actions filled the
same way, with an explicit `text-decoration: none` if it's ever an `<a>`.

`h1`–`h4`/`p`/`ul`/`ol` all get small explicit margins near the top of
`style.css`, instead of relying on the browser's default UA-stylesheet
margins (~1em top+bottom on every heading/paragraph) — that default
was the actual cause of the home page's asado cards once looking too
spaced out around the title/meta/description/"Participantes:". If a
new component still looks loosely spaced, check whether it's an
unstyled native element (a plain `<p>`/`<hr>`/`<button>` with no class)
before adding margin overrides — `hr` and the bare `button` element
both needed their own explicit dark-theme styling for the same reason
(their browser defaults are designed for a light background and
render badly, or invisibly, on a dark one). Similarly, `a` has an
explicit global color — without it, any link missing a more specific
class (like a couple were, before this pass) falls back to the
browser's default blue and clashes with the whole palette.

**Gotcha that caused real, live spacing bugs**: `.asado-card h2`
existed in the CSS for a while but `index.html`'s card markup actually
uses `<h3>` — the selector silently matched nothing, so that margin
override never applied. If a CSS rule targeting a specific tag/class
seems to have no effect, verify the selector actually matches the
current template markup before assuming the value itself needs
tweaking.

### Maps: OpenStreetMap + Leaflet, not Google Maps
Chosen specifically to avoid requiring a Google Cloud billing account
for a hobby project. Address autocomplete and reverse geocoding use
Nominatim's free public API (debounced client-side to be respectful of
rate limits), both called directly from the browser in
`new_asado.html`. Don't swap this for Google Maps without discussing it
— it changes the setup burden for the user significantly.

### Home page date filter: Flatpickr, not two plain date inputs
`index.html`'s "Fecha" filter is a single calendar with a highlighted
range (click a start day, click an end day — like an airline booking
site), via Flatpickr loaded from CDN (same per-page-scoped pattern as
Leaflet). `monthSelectorType: "static"` is set deliberately — Flatpickr's
default month picker is a native `<select>`, and that dropdown's OPEN
popup is drawn by the OS in a context that doesn't reliably pick up our
dark theme (rendered white-on-white regardless of CSS given to its
`<option>`s, and native select popups can't even be screenshotted for
testing — Playwright can't capture them, they're outside the page's
rendered layer). `"static"` shows the month as plain text navigated by
the `<` `>` arrows only (same as the year already works via a plain
number input), sidestepping the whole problem instead of fighting it.
Several other real gotchas were hit building this, worth knowing before
touching it again:

- **Theme overrides must live in `index.html`, not `static/style.css`.**
  `style.css` loads in `<head>`, before Flatpickr's own CDN stylesheet
  (which loads inside `{% block content %}`, later in the document) —
  at equal CSS specificity, whichever rule appears LATER in the
  document wins, so an override in `style.css` would silently lose to
  Flatpickr's own default (light) theme. The fix was to put the
  override `<style>` block directly in `index.html`, right after
  Flatpickr's `<link>`, guaranteeing it loads after.
- **The range-highlight colors need `!important`.** Flatpickr's own
  CSS bundles `.selected`/`.startRange`/`.endRange`/`.inRange` (plus
  `:hover`/`:focus`/edge-of-month variants) into one long
  equal-specificity rule per state. Even loaded after it, a plain
  override kept losing to it in testing — `!important` is the correct,
  standard tool here (overriding a vendored library's bundled theme),
  not a hack.
- **`dateFormat` is BOTH the display format AND what Flatpickr uses to
  *parse* `defaultDate`.** Setting `dateFormat: "d/m/Y"` for a nicer
  display, while also feeding it ISO `"YYYY-MM-DD"` strings (from the
  hidden inputs, to prefill the picker when a filter is already
  active) made Flatpickr misparse its own prefill values into garbage
  dates. The fix: keep `dateFormat: "Y-m-d"` (ISO, matching what's
  actually read/written to the hidden `date_from`/`date_to` inputs),
  and use `altInput: true` + `altFormat: "d/m/Y"` for the pretty
  display instead — Flatpickr's own documented mechanism for exactly
  this "internal format ≠ display format" split.
- One side effect of `altInput`: Flatpickr turns the original
  `#filter_date_range` into `type="hidden"` and creates a NEW element
  for what's actually visible/clickable, which the `<label for=...>`
  no longer points at. Fixed by renaming the new element's id and
  repointing the label's `for` attribute right after initialization —
  without this, clicking the "Fecha" label text wouldn't open the
  calendar the way every other filter field's label opens its own input.

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
- **`VERSION` (`app.py`) is a THIRD manually-bumped place, alongside
  `CHANGELOG.md` and the git tag.** It's shown in the small footer on
  every page (see below) via `inject_version()`. Nothing automatically
  keeps these three in sync — check `VERSION` specifically before
  tagging a release, or the footer will silently show a stale number
  even after `CHANGELOG.md`/the tag have moved on.
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
