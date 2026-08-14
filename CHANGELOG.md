# Changelog

Notable changes to this project, newest first. This is a hobby project
(not a published package), so version numbers are informal — mainly a
way to answer "what's actually live right now, and what changed since
last time?" now that deploying is a manual `git pull` + Reload step on
PythonAnywhere, not automatic. For the *reasoning* behind any specific
decision below, see `CLAUDE.md` — this file just says what happened
and when.

## Next Features (ideas, not yet built)
Roughly in the order they came up, not necessarily the order they'll
ship. "Simple leaderboard" and "Dashboard mockup with a KPI" are both
Phase 4 (Summary & stats) from the `Phases` roadmap file.
- Simple leaderboard (Phase 4).
- Dashboard mockup with a KPI (Phase 4).

## [0.11.1] - 2026-08-13
### Fixed
- Silenced 6 false-positive VSCode warnings in `_location_picker.html`
  caused by its embedded-JS checker misreading a Jinja `{% if %}`/
  `{% endif %}` pair inside a `<script>` block as broken JavaScript —
  purely cosmetic, never affected the running app. (A similar set of
  4 warnings remains in `_asado_form.html`'s `{{ weights|tojson }}`
  line — left as-is on purpose, since "fixing" it would mean adding
  real complexity to Flask's own recommended pattern for injecting
  server data into a `<script>` tag, just to quiet an editor-only
  false positive.)
### Changed
- The navigation bar collapses into a "☰" dropdown menu on screens
  narrower than 1025px, instead of wrapping its links into a multi-row
  clump. On a phone the navbar now takes 63px instead of 216px — it
  had been eating ~31% of the visible screen (~38% at 320px) before
  you scrolled at all. Desktop is untouched: above 1024px it's the
  same single row of links as always.
- Desktop pages use noticeably more of the screen's width — the main
  content area went from a flat 700px cap to 900px, and Base de
  Asados/Ubicaciones (the two spreadsheet-style pages) opt into an
  even wider 1500px cap. Mobile is untouched either way, since these
  are just upper caps.
- Base de Asados/Ubicaciones' tables now scroll VERTICALLY with the
  page itself, instead of inside their own small, separately-scrolling
  box. Horizontal scroll (for the widest tables) stays contained to
  the table itself, same as before. Trade-off: the column header no
  longer stays pinned in place while scrolling through a long table —
  CSS can't do both a page-scrolling table AND a sticky header AND
  horizontal scroll at once; that would need a JS-driven header.

## [0.11.0] - 2026-08-04
### Added
- "Registro de Actividad" (`/actividad`): a log of who created, edited,
  or deleted each asado, and when — visible to every logged-in user,
  not just admins. Edits show a field-by-field diff (old → new) for
  whatever actually changed; creates/deletes just show the action
  itself. New `activity_log`/`activity_log_changes` tables — requires
  re-running `init_db()` (wipes local data) before this version will run.
- "Ubicaciones Guardadas" (`/ubicaciones`): a reusable pool of saved
  locations. A new "💾 Guardar esta ubicación" checkbox on the asado
  form optionally adds whatever address/pin you just used to the pool
  (unchecked by default — a one-off, never-saved location still works
  exactly as before); a new "Ubicación guardada" dropdown then quick-
  fills from that pool next time instead of retyping an address or
  dropping a map pin. Any logged-in user can add/edit a saved location;
  deleting one is admin-only. New `locations` table — also requires
  re-running `init_db()`.
- `/ubicaciones`' "Nueva Ubicación" form now uses the same address-
  autocomplete + map picker as the asado form (extracted into a shared
  `_location_picker.html` partial), and Nombre/Dirección/coordinates
  are all required there — a saved location needs a real address and
  coordinates to be useful as a future quick-fill.
- The address/map picker (both `/ubicaciones` and the asado form) now
  shows the picked coordinates as a read-only reference line under the
  address field, instead of only storing them invisibly.
- "Ubicaciones Existentes" redesigned as a compact spreadsheet-style
  table (one row per saved location, editable cells, a 💾 per row)
  instead of a stacked card per location.
- Both spreadsheet tables (Ubicaciones Existentes, Base de Asados) made
  noticeably more compact horizontally: tighter cell padding, Latitud/
  Longitud merged into one narrow "Coordenadas" column (Ubicaciones),
  "Agregada por" moved from its own column to a tooltip, and Base de
  Asados' longest headers abbreviated on-screen (CSV export headers
  unchanged). The number-spinner arrows on Latitud/Longitud were also
  removed — not useful on a coordinate field.
- Base de Asados' Tipo Carne/Ubicación columns now truncate long values
  with an ellipsis (full text on hover) instead of wrapping onto
  multiple lines — keeps every row a single, consistent height.
- A small version tracker + personal dedication in the footer of every
  page ("v0.11.0 — 'Soñás la hoguera donde siempre sos la leña'
  (Indio, 1949-2026)").
### Changed
- **Schema change**: two new tables, `activity_log`/`activity_log_changes`
  and `locations` — requires re-running `init_db()` (wipes local data)
  before this version will run.

## [0.10.0] - 2026-08-04
### Added
- Deployed to PythonAnywhere: **https://asados.pythonanywhere.com**
  (Phase 6). Hosted under a dedicated `asados` PythonAnywhere account
  rather than a personal one, for a clean project URL.
- Live site currently runs a fresh/empty database for testing — the
  195 real local asados haven't been migrated over yet.
- Home page: Fecha filter is now a proper date-range calendar (pick a
  start/end day, range highlights like an airline site), plus new Año
  and Mes filters (Mes alone matches that calendar month across every
  year).
- An asado can now have more than one Tipo de Carne (minimum one) —
  only the highest-weight selection counts toward points, but every
  selected type is saved and shown (Base de Asados/CSV join them with
  "; ").
### Changed
- **Schema change**: `asados.tipo_carne` column removed, replaced by a
  new `asado_tipo_carne` table — requires re-running `init_db()` (wipes
  local data) before this version will run.

## [0.9.0] - 2026-08-02 — "v0.9 beta"
### Added
- Automatic database backups: every new asado now triggers a safe,
  consistent snapshot of `asados.db` into `backups/` (`backup_db.py`,
  using SQLite's own online-backup API, not a plain file copy).
### Changed
- Mobile responsiveness pass (Phase 5): larger touch targets on nav
  links, a bigger/more usable map picker on small screens.
- Removed the 86MB reference PDF from git tracking (kept locally in
  `extras/`, no longer bloating the repo).

## [0.8.0] - 2026-07-31 — "Old Money Texas Classic"
### Changed
- Full visual redesign: dark walnut-wood/leather color palette with a
  burgundy/scarlet accent, replacing the original light theme — informed
  by a direct study of *The Designer's Dictionary of Color* (Sean Adams).
- Headings switched to 'EB Garamond'; tightened spacing across cards,
  forms, and tables that had been relying on browser-default margins.

## [0.7.0] - 2026-07-31 — "Editar Asados"
### Added
- Edit and delete for existing asados (Phase 3): any logged-in user can
  edit any asado; deleting is admin-only, with confirmation.
- `_asado_form.html`: the create and edit forms now share one partial
  instead of two copies that could drift apart.
- CSRF protection on every POST route (hand-rolled token check).
- Pagination on the home page and Base de Asados.
- `seed_random_asados.py` — fills the DB with random test data for
  trying out filters/exports without typing real entries by hand.

## [0.6.0] - 2026-07-31 — "Base de Datos descargable"
### Added
- "Base de Asados": a flat, spreadsheet-style view (one row per
  participation) with CSV export.
- The individual weights behind each participation's points are now
  frozen and stored (not just the final points total), so a later
  change to `config.py`'s weights can't retroactively make old numbers
  unexplainable.

## [0.5.0] - 2026-07-31 — "Login with config"
### Added
- User accounts now have a `role` (`admin`/`normal`) and a display
  `name`, separate from the login `username`.
- `/config` "Configuración" page: everyone can edit their own
  name/password; admins can create or delete accounts from the browser
  instead of only via `create_user.py`.

## [0.4.0] - 2026-07-31 — "Login v1"
### Added
- Phase 2: session-based username/password login. The whole app now
  requires signing in.

## [0.3.0] - 2026-07-30/31 — "Formula literal"
### Changed
- The points formula became a single literal, evaluable string in
  `config.py`, read by both the real calculation and the live on-screen
  preview — closing a "formula lives in two places" drift risk that had
  bitten the project once already.

## [0.2.0] - 2026-07-30 — "Mapa"
### Added
- Location picker: address autocomplete + an interactive map (Leaflet +
  OpenStreetMap/Nominatim) for setting an asado's coordinates.

## [0.1.0] - 2026-07-30 — "Phase 1: initial working app"
### Added
- Initial working app: the core `asados` data model, a Flask backend,
  and plain HTML pages to add and list entries.
### Fixed
- A `.gitignore` whitespace bug that had let `asados.db` and
  `__pycache__` get committed despite being "excluded."
