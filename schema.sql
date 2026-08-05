-- =====================================================================
-- schema.sql
-- This file defines the STRUCTURE of our database (the "blueprint").
-- It does NOT contain any actual data — just the shape of the tables.
-- We will run this once to create empty tables, then fill them via the app.
-- =====================================================================

-- Drop tables first if they already exist, so we can re-run this file
-- safely during development without errors. (In production you would NOT
-- do this, since it deletes all existing data!)
DROP TABLE IF EXISTS activity_log_changes;
DROP TABLE IF EXISTS activity_log;
DROP TABLE IF EXISTS asado_tipo_carne;
DROP TABLE IF EXISTS participations;
DROP TABLE IF EXISTS asados;
DROP TABLE IF EXISTS locations;
DROP TABLE IF EXISTS users;

-- ---------------------------------------------------------------------
-- USERS TABLE
-- One row per person who can log in and participate in asados.
-- ---------------------------------------------------------------------
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- unique numeric ID, auto-generated
    username TEXT UNIQUE NOT NULL,         -- must be unique, cannot be empty
    -- We NEVER store the actual password — only a "hash" of it (a
    -- scrambled, one-way version). Even if someone read the database
    -- directly, they couldn't recover the real password from this.
    -- Accounts are created via the create_user.py script (see README),
    -- not through a public sign-up page.
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,                    -- display name, e.g. "Don Nicola" (separate from the login username)
    -- "admin" can create/delete accounts from the Configuración page;
    -- "normal" can only edit their own name/password there.
    role TEXT NOT NULL DEFAULT 'normal' CHECK (role IN ('admin', 'normal'))
);

-- ---------------------------------------------------------------------
-- ASADOS TABLE
-- One row per asado EVENT. This holds the facts that are shared by
-- everyone who attended (date, meat type, location, etc.) — i.e. things
-- that don't depend on which specific person we're talking about.
-- ---------------------------------------------------------------------
CREATE TABLE asados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,                -- stored as 'YYYY-MM-DD' text (SQLite has no native date type)
    nombre TEXT NOT NULL,              -- the fun/creative name of the asado
    description TEXT,                  -- optional (no NOT NULL constraint), can be empty
    -- Tipo de Carne is NOT a column here — an asado can have MULTIPLE
    -- meat types (see the asado_tipo_carne table below), so the list of
    -- types themselves lives there. tipo_carne_weight below is still a
    -- single number, though: whichever selected type has the HIGHEST
    -- weight is the one that actually feeds the points formula (a
    -- deliberate rule — see asado_tipo_carne's comment for the reasoning).
    coccion TEXT NOT NULL,             -- e.g. "A las brasas", "Ahumado"
    superficie TEXT NOT NULL,          -- e.g. "Parrilla", "Plancha", "Disco"
    local TEXT NOT NULL,               -- e.g. "Casa", "Restaurante", "Quincho"
    location TEXT,                     -- free text: address / place name (optional)
    latitude REAL,                     -- geographic coordinate from the map picker (optional)
    longitude REAL,                    -- geographic coordinate from the map picker (optional)
    people INTEGER,                    -- total headcount at the asado
    total_weight REAL,                 -- total kg of meat (REAL = decimal number in SQLite)

    -- The 4 numeric weights (from config.py's TIPO_CARNE_WEIGHTS etc.)
    -- that fed into every participant's points calculation for THIS
    -- asado, looked up and FROZEN here at creation time — same
    -- reasoning as participations.points below: if config.py's weights
    -- change later, old entries keep a record of what weight actually
    -- produced their points, instead of only being reconstructable by
    -- re-looking-up the (possibly since-changed) current weights.
    -- tipo_carne_weight specifically is the MAX across every selected
    -- type in asado_tipo_carne, not any one type's own weight.
    tipo_carne_weight REAL,
    coccion_weight REAL,
    superficie_weight REAL,
    local_weight REAL
);

-- ---------------------------------------------------------------------
-- ASADO_TIPO_CARNE TABLE  (another "junction" table, same idea as
-- participations below, just linking asados to MEAT TYPES instead of
-- USERS)
-- One row per (asado, tipo de carne) pair — an asado can have more than
-- one meat type (minimum one), e.g. both "Cordero" and "Pollo" at the
-- same event. Each row freezes THAT type's own weight at creation time,
-- for the same reason points/weights are frozen everywhere else in this
-- app: `asados.tipo_carne_weight` only stores the WINNING (highest)
-- weight, since only the biggest one actually feeds the points formula
-- — but keeping every selected type's own weight here means Base de
-- Asados/CSV can still show the complete picture of what was chosen and
-- why one weight won, not just the final number.
-- ---------------------------------------------------------------------
CREATE TABLE asado_tipo_carne (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asado_id INTEGER NOT NULL,
    tipo_carne TEXT NOT NULL,          -- e.g. "Vacío", "Chorizo", etc.
    tipo_carne_weight REAL NOT NULL,   -- THIS type's own frozen weight (not necessarily the max)

    FOREIGN KEY (asado_id) REFERENCES asados (id)
);

-- ---------------------------------------------------------------------
-- PARTICIPATIONS TABLE  (the "junction" / "bridge" table)
-- One row per (user, asado) pair. This is what lets MANY users link to
-- MANY asados — a classic "many-to-many" relationship.
-- It also stores anything that's specific to THAT person's involvement:
-- their Rol, and the Points they earned for that specific asado.
-- ---------------------------------------------------------------------
CREATE TABLE participations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asado_id INTEGER NOT NULL,     -- which asado this participation belongs to
    user_id INTEGER NOT NULL,      -- which user this participation belongs to
    rol TEXT NOT NULL,             -- e.g. "Asador", "Ayudante", "Invitado", "Anfitrión"
    rol_weight REAL NOT NULL,      -- this participant's Rol weight (config.py's ROL_WEIGHTS), FROZEN like points below
    points REAL NOT NULL,          -- calculated at creation time and FROZEN (never recalculated later)

    -- FOREIGN KEY = tells the database "this column must match an id that
    -- really exists in the other table". This prevents orphaned data, like
    -- a participation pointing to an asado that doesn't exist.
    FOREIGN KEY (asado_id) REFERENCES asados (id),
    FOREIGN KEY (user_id) REFERENCES users (id)
);

-- ---------------------------------------------------------------------
-- ACTIVITY_LOG TABLE
-- One row per create/edit/delete action taken on an asado — "who did
-- what, and when" (see CLAUDE.md's "Next Features" note this
-- implements). Every user-facing route that changes an asado
-- (new_asado, edit_asado, delete_asado) writes one row here, in the
-- SAME database transaction as the change itself (see activity_log.py)
-- — so a log entry and the change it describes always succeed or fail
-- together, never one without the other.
--
-- user_id/asado_id are kept as REAL foreign keys (so the row stays
-- accurate while the user/asado it points to still exists), but with
-- ON DELETE SET NULL rather than a hard block — deleting a user account
-- or an asado should NEVER be prevented just because old log entries
-- reference it (unlike participations, which DO block a user delete —
-- see delete_user_route in app.py). actor_name/asado_nombre/asado_date
-- are FROZEN copies of that info at the moment the action happened,
-- same "freeze it so history survives later changes" pattern already
-- used for weights/points elsewhere in this app — so even after a user
-- or asado is deleted, the log entry stays fully readable ("Nico
-- eliminó el asado 'Épico Junte'") instead of showing a blank/broken
-- reference.
-- ---------------------------------------------------------------------
CREATE TABLE activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,           -- 'YYYY-MM-DD HH:MM:SS', same plain-text-date approach as asados.date
    user_id INTEGER,                   -- who performed the action (NULL if that account was later deleted)
    actor_name TEXT NOT NULL,          -- FROZEN display name at the time of the action
    asado_id INTEGER,                  -- which asado (NULL if that asado was later deleted, or IS the delete this row records)
    asado_nombre TEXT NOT NULL,        -- FROZEN asado name at the time of the action
    asado_date TEXT NOT NULL,          -- FROZEN asado date at the time of the action
    action TEXT NOT NULL CHECK (action IN ('create', 'edit', 'delete')),

    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL,
    FOREIGN KEY (asado_id) REFERENCES asados (id) ON DELETE SET NULL
);

-- ---------------------------------------------------------------------
-- ACTIVITY_LOG_CHANGES TABLE
-- One row per individual FIELD that changed in an 'edit' action (e.g.
-- one row for "Fecha: 2026-07-10 → 2026-07-12", another for
-- "Participantes: ..."), linked back to its activity_log row. A real
-- relational table rather than one JSON/string blob column, matching
-- this app's existing preference (see asado_tipo_carne) for keeping
-- multi-value data queryable/auditable instead of concatenated text.
-- Only 'edit' actions ever populate this — 'create'/'delete' actions
-- are fully described by the single activity_log row alone (diffing
-- "nothing" against a brand-new asado, or vice versa, isn't useful).
-- ON DELETE CASCADE: if an activity_log row is ever removed, its
-- changes should go with it (nothing in the app currently deletes log
-- rows, but this keeps the schema correct regardless).
-- ---------------------------------------------------------------------
CREATE TABLE activity_log_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    log_id INTEGER NOT NULL,
    field_label TEXT NOT NULL,         -- human-readable Spanish label, e.g. "Fecha", "Participantes"
    old_value TEXT,                    -- NULL means the field was previously empty
    new_value TEXT,                    -- NULL means the field is now empty

    FOREIGN KEY (log_id) REFERENCES activity_log (id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------
-- LOCATIONS TABLE
-- A reusable, user-curated pool of saved places ("Casa de Nico",
-- "Quincho El Bosque", ...) — see CLAUDE.md's "Recurring locations"
-- section. This is DELIBERATELY NOT linked to `asados` via a foreign
-- key: picking a saved location on the asado form just PREFILLS the
-- normal asados.location/latitude/longitude columns (a one-time
-- quick-fill), exactly as if you'd typed/map-picked it yourself. That
-- means later renaming or deleting a saved location here never
-- retroactively changes any asado that already used it — same
-- "frozen at the moment it was used" philosophy as weights/points
-- elsewhere in this app, just applied to convenience data instead of
-- scoring data.
--
-- Any logged-in user can add or edit a row here (same open-editing
-- philosophy as asados themselves); only an admin can delete one (see
-- admin_required on delete_location in app.py) — the same asymmetry
-- delete_asado already uses, for the same reason (removing a shared
-- resource is the one genuinely destructive action here).
-- ---------------------------------------------------------------------
CREATE TABLE locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                -- short label shown in the dropdown, e.g. "Casa de Nico"
    -- address/latitude/longitude are NOT NULL here — unlike
    -- asados.location (which stays free/optional, see schema.sql's own
    -- comment on that column), a SAVED location genuinely needs a real
    -- address AND coordinates to be useful when picked from the
    -- dropdown later; a name-only entry with no location data would be
    -- useless as a map quick-fill. Enforced at the form level too (see
    -- create_location()/edit_location() in app.py and
    -- _location_picker.html's location_required flag) — this NOT NULL
    -- is the DB-level backstop, matching how asados.nombre/coccion/etc.
    -- are already both form-required AND NOT NULL.
    address TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    created_by INTEGER,                -- who added it (nullable — NOT a hard block on deleting that user)
    created_at TEXT NOT NULL,          -- 'YYYY-MM-DD HH:MM:SS', same plain-text-date approach as elsewhere

    FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE SET NULL
);
