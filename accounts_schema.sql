-- =====================================================================
-- accounts_schema.sql
-- The REGISTRY database (accounts.db): who can log in, which groups
-- exist, and who belongs to which group. It holds NO asado data at all
-- — every group's asados, participations, points, locations and
-- activity log live in that group's OWN database file under groups/,
-- with exactly the same shape as before (see schema.sql).
--
-- WHY TWO KINDS OF DATABASE FILE (see CLAUDE.md's "Groups" section for
-- the full story): one file per group makes it physically impossible
-- for one group's data to show up in another's pages — there is no
-- "WHERE group_id = ?" anywhere that could be forgotten, because a
-- group's queries can only ever see the one file they were opened on.
-- But a login has to be checked BEFORE we know which group someone is
-- in, so the logins themselves need one shared place. That's this file.
--
-- UNLIKE schema.sql, THIS FILE NEVER DROPS ANYTHING. Every statement is
-- "IF NOT EXISTS", so running it against an accounts.db that already
-- holds real logins is a harmless no-op — that's what lets
-- migrate_to_groups.py (and later scripts) apply it unconditionally.
-- Keep it that way: a DROP TABLE here would wipe every login on the
-- site, for every group at once.
-- =====================================================================

-- ---------------------------------------------------------------------
-- ACCOUNTS — one row per LOGIN (a username + password).
-- ---------------------------------------------------------------------
-- This is the only place a password hash lives from v2.0 on. Each
-- group's own `users` table still has one row per MEMBER (display name,
-- role, colour, and what every participation points at) — an account is
-- "can log in", a member is "is part of this group's competition".
-- memberships below is what joins the two.
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- COLLATE NOCASE: unique and looked up case-INsensitively. With one
    -- login page for every group, "Nico" in one group and "nico" in
    -- another would be two different accounts that look identical to a
    -- human — refusing the second one up front is much less confusing
    -- than working out later which one someone meant.
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,   -- never the password itself; see create_user.py
    created_at TEXT NOT NULL       -- 'YYYY-MM-DD HH:MM:SS', same format as activity_log
);

-- ---------------------------------------------------------------------
-- ASADO_GROUPS — one row per group (e.g. "Parrilla y Alma").
-- ---------------------------------------------------------------------
-- Named asado_groups, not "groups": GROUPS is an SQL keyword in SQLite
-- (window-function frames), and a table named after a keyword works
-- right up until some query puts it in exactly the wrong place.
CREATE TABLE IF NOT EXISTS asado_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- The group's permanent short id, e.g. "parrilla-y-alma". It also
    -- NAMES THE DATABASE FILE (groups/<slug>.db), which is why it never
    -- changes after creation — renaming the file is not something the
    -- app knows how to do. Only lowercase letters, digits and single
    -- hyphens are allowed (checked in accounts.py's SLUG_PATTERN), so a
    -- slug can never contain "..", "/" or anything else that would let
    -- it point at a file outside groups/.
    slug TEXT NOT NULL UNIQUE,
    -- The display name, e.g. "Parrilla y Alma". Free to change at any
    -- time — nothing refers to it except what's shown on screen.
    name TEXT NOT NULL,
    -- Per-group secret for /export/base-asados.csv (the Google Sheets /
    -- Looker Studio feed). One per group, so a leaked Sheets link can
    -- only ever expose that one group. It replaces export_token.txt;
    -- the migration copies the old file's value into the first group,
    -- so existing Sheets formulas keep working unchanged.
    export_token TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

-- ---------------------------------------------------------------------
-- MEMBERSHIPS — which account is which member of which group.
-- ---------------------------------------------------------------------
-- member_id is a users.id INSIDE that group's own database file. It
-- can't be a real FOREIGN KEY: SQLite only enforces foreign keys within
-- one database file, and that row lives in a different one. app.py
-- therefore treats a membership whose member row is missing as "not
-- in any group" rather than trusting it.
--
-- The table already allows one account in SEVERAL groups (only the
-- pair account+group has to be unique). "One account, one group" is
-- for now a rule in the CODE (see accounts.py), not in this schema, on
-- purpose: lifting it later is then a code change, never a migration —
-- SQLite can't remove a UNIQUE constraint without rebuilding the table.
CREATE TABLE IF NOT EXISTS memberships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    group_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    -- Also serves as the index for "which groups is this account in?"
    -- (the lookup made on every request): SQLite can use a UNIQUE
    -- constraint's automatic index for any query on its LEADING
    -- column, so a separate index on account_id would be redundant.
    UNIQUE (account_id, group_id),
    -- One member row can belong to at most one login.
    UNIQUE (group_id, member_id),
    FOREIGN KEY (account_id) REFERENCES accounts (id),
    FOREIGN KEY (group_id) REFERENCES asado_groups (id)
);
