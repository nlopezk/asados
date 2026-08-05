-- =====================================================================
-- schema.sql
-- This file defines the STRUCTURE of our database (the "blueprint").
-- It does NOT contain any actual data — just the shape of the tables.
-- We will run this once to create empty tables, then fill them via the app.
-- =====================================================================

-- Drop tables first if they already exist, so we can re-run this file
-- safely during development without errors. (In production you would NOT
-- do this, since it deletes all existing data!)
DROP TABLE IF EXISTS asado_tipo_carne;
DROP TABLE IF EXISTS participations;
DROP TABLE IF EXISTS asados;
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
