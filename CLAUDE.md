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

**Currently at the end of Phase 3 + Phase 5** (login + edit/delete +
mobile responsiveness exist; Phase 4's stats/leaderboard is still
outstanding, not deployed yet — Phase 5 was deliberately done out of
order, before Phase 4, at the user's request). Phase 3 deliberately
deviated from its own description above: editing is open to **every**
logged-in user (not "only your own entries"), while deleting is
**admin-only** — see the "Edit/delete permissions" note below.

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

**Phase 6 (deploy) hosting decision: PythonAnywhere free tier, not
Render/Railway/Fly.io.** The deciding factor was SQLite: this app
stores its whole database as a single `asados.db` file, and Render's
and Railway's free tiers wipe their filesystem on every redeploy —
that would silently delete the database the first time you pushed a
code update. PythonAnywhere's free tier has genuine persistent
storage (SQLite just works, no volume/mount config needed) and stays
always-on (no Render-style cold-start sleep). Trade-off accepted
knowingly: the URL is `yourname.pythonanywhere.com`, not a custom
domain — a non-issue for sharing a link with 5-10 friends. A Synology
NAS (self-hosted via Docker + a volume mount + Cloudflare Tunnel) was
seriously considered and would also work well, but was set aside for
now in favor of PythonAnywhere's lower setup effort; revisit if full
data ownership or avoiding a third-party platform ever becomes a
priority. Deployment itself (turning off `debug=True`, the actual
PythonAnywhere WSGI config, etc.) hasn't been done yet as of this
writing — only the backup story above has been built in preparation.
using that pattern rather than fixed widths.

## Architecture

Everything routes through `app.py` — there's no blueprint/package split
yet, just one Flask app with a handful of routes:

- `/login`, `/logout` — session-based auth (see below)
- `/` (`index`) — lists all asados, newest first, with each one's
  participants and points joined in. Accepts optional `?date=` and
  `?user_id=` query params to filter the list (a plain GET form in
  `index.html` auto-submits on change — no JS fetch needed), and
  `?page=` to paginate (`INDEX_PAGE_SIZE` = 30/page, filters and page
  compose together — page count is computed AFTER filtering)
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
  keep exporting everything
- `/base-asados/csv` (`base_asados_csv`) — same rows as above, streamed
  back as a downloadable CSV (UTF-8 with a BOM prefix, so accented
  characters open correctly in Excel on Windows)
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
