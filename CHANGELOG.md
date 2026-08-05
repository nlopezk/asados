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
- Activity log: who added/edited/deleted what, and when.
- Recurring locations: a customizable, reusable pool of saved places to
  pick from, instead of typing an address or dropping a map pin every
  single time.
- Simple leaderboard (Phase 4).
- Dashboard mockup with a KPI (Phase 4).

## [Unreleased]

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
