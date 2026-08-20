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
ship.
- A KPI/dashboard row above or beside Resumen's chart (Phase 4's
  leaderboard shipped in 1.0.0 as the standings table; the trend chart
  shipped in 1.2.0 — a small set of headline stat tiles is what's left).
- Offsite backups (e.g. periodically pulling `backups/` down to a NAS)
  — the current backups protect against bad data, not against losing
  the hosting account.
Potential bugs:
- Verificar punto y coma.
- one role per user per asado
Social:
- User statistics.
- Calendar view
Improvements:
- Cow View
- Favourite cuts (less priority)
- Asado weight calculator

Groups (much later): Creación de grupos, invitaciones y posibilidad de que el usuario pertenezca a distintos grupos.


## [1.2.0] - 2026-08-20
### Added
- **Resumen chart**: a Plotly line graph below the standings table,
  one step-line per user showing their cumulative points over their
  whole history — pannable (drag, or the mini-overview strip), zoomable
  (scroll/pinch, or box-zoom), and filterable by period (3m/6m/1a/Todo
  preset buttons), all built into Plotly's own date axis. Deliberately
  independent of the table's Año/Semestre filters — the chart always
  shows full history, with its own interactive range as the way to
  focus on a period. Colors are the `dataviz` skill's own validated
  categorical palette, checked against this app's actual walnut card
  surface, not eyeballed — see `CLAUDE.md`'s "Resumen's chart" section
  for the full reasoning.
- **The same per-user color now shows up everywhere**, not just the
  chart: a small dot next to each name in Resumen's table, and next to
  every participant on the home page's asado cards. One shared
  function (`get_user_color()`) decides it, exposed to every template
  as `user_color()` — see CLAUDE.md's "One color per user, everywhere"
  section.
### Fixed
- The chart's legend genuinely overlapped the rangeslider beneath it
  at every screen width (a real ~14px DOM overlap, not just a
  narrow-screen issue) — moved to sit above the plot instead, where
  nothing else competes for the same space, and re-verified across an
  18-point width sweep from 320px to 1600px rather than the 2–3 sample
  breakpoints the first pass shipped with. See CLAUDE.md for what
  actually broke (twice) and why a narrow spot-check missed it.

## [1.1.0] - 2026-08-20
### Added
- **Looker Studio / Google Sheets export** (`/export/base-asados.csv`):
  the same data as the existing "Exportar CSV" button, but reachable
  without logging in — gated by a long random token in the URL instead
  (`export_token.txt`, auto-generated on first run, gitignored exactly
  like `secret_key.txt`). Meant to be fetched by a Google Sheet's
  `=IMPORTDATA(...)`, which then Looker Studio reads via its ordinary,
  built-in Sheets connector — no SQLite connector exists for Looker
  Studio, so this is the bridge. See `CLAUDE.md` for the full setup
  steps and the reasoning behind the token-over-login design.
- Both CSV routes (the existing login-gated one and the new token-gated
  one) now share one response-building function, so there is exactly
  one place that decides what "the CSV export" contains.

## [1.0.1] - 2026-08-19
Data correction release — no application code changed, only the
historical data, `.gitignore`, and the docs.

### Fixed
- **Gas asados were scored slightly low across the whole history.** The
  original spreadsheet had Gas cocción at weight 0.5, while `config.py`
  has always said 0.7. `Base Histórica v2.csv` corrects it at source,
  and re-importing brought 98 rows (every Gas asado) into line — both
  the stored points and the frozen `coccion_weight` column, so Base de
  Asados can't show a weight that doesn't produce the points beside it.
  Group total went 199.75 → 208.25; the standings order is unchanged.
- **`.gitignore` now uses the glob `Base Histórica*.csv`.** The 1.0.0
  rule named one exact filename, so `Base Histórica v2.csv` showed up
  untracked but un-ignored — the same near-miss the 1.0.0 audit had
  just caught with v1, on a public repo holding real home addresses.

### Added
- Two new asados (14 and 15 Aug 2026, both Nico G.), bringing the
  history to **234 asados / 264 participations**.

## [1.0.0] - 2026-08-14 — "Primera versión completa"
First version with the group's **real history** in it (232 asados,
262 participations, imported from the historical spreadsheet) rather
than test data, and the first full audit pass over the whole codebase.
Phases 1, 2, 3, 5 and 6 of the roadmap are done, and Phase 4's
leaderboard half shipped here as "Resumen".

### Added
- **Historical data import**: the group's real asado history (Jan–Aug
  2026) replaced the ~149 randomly-generated test asados. Points and
  weights were imported EXACTLY as originally calculated in the
  spreadsheet rather than recalculated, so past scores are untouched by
  any later weight change — the same "frozen" rule the app already
  follows. Total points reconciled exactly against the source.
- **9 recurring locations** seeded into Ubicaciones from the imported
  history (the addresses that came up 4+ times), so the places the
  group actually uses are one dropdown pick away.
- Database **indexes** on every foreign key (`participations.asado_id`,
  `participations.user_id`, `asado_tipo_carne.asado_id`,
  `activity_log_changes.log_id`). SQLite indexes primary keys and
  UNIQUE columns automatically but never foreign keys, so these lookups
  were full table scans — invisible at today's size, but the home page
  runs two of them per asado shown.
- Explicit `SameSite=Lax` / `HttpOnly` on the session cookie — mostly
  making the existing browser-default behavior explicit, as a second
  layer behind the CSRF token check.

### Fixed
- **`/api/points` required no login** — the only endpoint in the app
  reachable without an account. It reads and writes nothing, so no data
  was exposed, but it did let an anonymous caller probe the scoring
  weights. Now `@login_required` like every other route.
- **Base de Asados showed two columns under the wrong headers**:
  "Cantidad Carne (kg)" was displaying the Rol weight (0.7/0.8/1.0) and
  "Peso Rol" was displaying kilograms of meat. An HTML table ties cells
  to headers by ORDER only, so reordering the headers without reordering
  the cells silently mislabels data. (The CSV export was unaffected —
  it keeps its own separate, still-correct column list.)
- The navbar now highlights whichever section you're currently in
  (a gold underline, same trim color as the navbar's own bottom
  border) — in both the desktop row and the phone dropdown.
- Base de Asados showed the literal word "None" in every empty
  Personas / Cantidad Carne / Lat. / Long. cell (those columns are
  genuinely optional). They render as blank cells now.

### Changed
- **README rewritten** — it still described the app as "Phase 3" and
  listed leaderboards and deployment as not-yet-built, both of which
  had shipped. Now documents every page, the deploy steps, and the
  three places a version number has to be bumped.
- `Base Histórica.csv` added to `.gitignore`. **This repo is public**
  and that file holds real home addresses and GPS coordinates for the
  whole group — the same reason `asados.db` was already ignored.
- `__pycache__/*.pyc` files finally untracked (`git rm --cached`).
  They'd been committed before `.gitignore` covered them, and gitignore
  never retroactively untracks files git already knows about.

### Fixed (also in this release)
- Resumen's standings table was flush against the left edge of its
  wide container instead of centered — a follow-on bug from capping
  its width narrower than the page, missing the `margin: 0 auto` that
  actually centers a width-capped block.
- Every navbar link (and `.secondary-button`/`.primary-button` links
  like "Exportar CSV") turned a hard-to-read brick-orange once clicked
  — the app's global `a:visited` rule was silently overriding those
  components' own white/text color, since `:visited` beats a plain
  class in CSS specificity. Fixed by having each component repeat its
  color under `:visited` too, rather than removing the global rule
  (which would have fallen back to the browser's own default purple
  visited-link color instead).

### Changed (also in this release)
- "Añadir Asado" is now a distinct muted green in the navbar — the one
  ACTION among otherwise purely navigational links.
- Navbar order is now: Añadir Asado, Resumen, Base de Asados,
  Ubicaciones, Config, username, Actividad, Salir.
- The navbar's collapse breakpoint moved from 1024px to 1125px,
  re-measured after adding the "🏆 Resumen" link (seven links need
  ~1151px, up from ~1026px). Left at 1024 it would have silently
  reintroduced the squeezed navbar between ~1125px and 1024px.

### Added — the Resumen page
- "Resumen" (`/resumen`): a standings/position table — one row per
  user, with their summed Tipo de Carne / Cocción / Superficie / Local
  / Rol weights, average points per participation, participation
  count, and total points. Sorted by total points by default; every
  column header is clickable to re-sort (click again to flip the
  direction), and sorting is a plain GET so a sorted view is a
  shareable URL. Filters by Año and Semestre (1° = ene–jun,
  2° = jul–dic, "Ambos" = no filter). No schema change — this reads
  the existing frozen weights/points.
  Note: the five "Suma" columns deliberately do NOT add up to Puntos
  Totales, and can't — the points formula multiplies those variables
  rather than adding them, so Superficie/Local/Rol scale the result
  instead of contributing a fixed share. They're there to show what
  KIND of asados someone has been at. This is stated on the page too.

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
