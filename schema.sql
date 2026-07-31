-- =====================================================================
-- schema.sql
-- This file defines the STRUCTURE of our database (the "blueprint").
-- It does NOT contain any actual data — just the shape of the tables.
-- We will run this once to create empty tables, then fill them via the app.
-- =====================================================================

-- Drop tables first if they already exist, so we can re-run this file
-- safely during development without errors. (In production you would NOT
-- do this, since it deletes all existing data!)
DROP TABLE IF EXISTS participations;
DROP TABLE IF EXISTS asados;
DROP TABLE IF EXISTS users;

-- ---------------------------------------------------------------------
-- USERS TABLE
-- One row per person who can log in and participate in asados.
-- ---------------------------------------------------------------------
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- unique numeric ID, auto-generated
    username TEXT UNIQUE NOT NULL          -- must be unique, cannot be empty
    -- NOTE: no password field yet — that comes in Phase 2 (login system).
    -- For now we just need to be able to reference "who" participated.
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
    tipo_carne TEXT NOT NULL,          -- e.g. "Vacío", "Chorizo", etc.
    coccion TEXT NOT NULL,             -- e.g. "A las brasas", "Ahumado"
    superficie TEXT NOT NULL,          -- e.g. "Parrilla", "Plancha", "Disco"
    local TEXT NOT NULL,               -- e.g. "Casa", "Restaurante", "Quincho"
    location TEXT,                     -- free text: address / place name (optional)
    latitude REAL,                     -- geographic coordinate from the map picker (optional)
    longitude REAL,                    -- geographic coordinate from the map picker (optional)
    people INTEGER,                    -- total headcount at the asado
    total_weight REAL                  -- total kg of meat (REAL = decimal number in SQLite)
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
    points REAL NOT NULL,          -- calculated at creation time and FROZEN (never recalculated later)

    -- FOREIGN KEY = tells the database "this column must match an id that
    -- really exists in the other table". This prevents orphaned data, like
    -- a participation pointing to an asado that doesn't exist.
    FOREIGN KEY (asado_id) REFERENCES asados (id),
    FOREIGN KEY (user_id) REFERENCES users (id)
);
