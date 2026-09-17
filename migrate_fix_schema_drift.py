# =====================================================================
# migrate_fix_schema_drift.py
# Brings an EXISTING database back in line with schema.sql, without
# touching any data. Two things, both found by the v1.7.3 audit:
#
#   1. THREE MISSING INDEXES on foreign keys —
#      activity_log.asado_id, activity_log.user_id,
#      locations.created_by. SQLite indexes PRIMARY KEY and UNIQUE
#      columns only; a declared FOREIGN KEY gets nothing automatically,
#      so every lookup by those columns is a full table scan. The
#      v1.0.0 audit already established "any new foreign key should get
#      one too" and added four; these three were added later and missed
#      it. Harmless at today's row counts, wrong as a standing rule.
#
#   2. locations.address / latitude / longitude WERE NOT ACTUALLY
#      NOT NULL. schema.sql declares all three NOT NULL, and CLAUDE.md
#      describes that as the third of three deliberately redundant
#      layers (HTML `required`, a server-side check, then the database
#      itself). The table predates those constraints and no migration
#      ever applied them, so the layer documented as the last-resort
#      backstop did not exist. No bad data had slipped through — the
#      app-level checks held — but the guarantee was imaginary.
#
# WHY THIS IS A SEPARATE SCRIPT from migrate_add_cortes.py: that one
# has already been run against both databases, and a migration that has
# been applied should stay applied and unedited. Adding steps to it
# would mean the same filename meaning two different things depending
# on when you ran it. One script per schema change, each idempotent.
#
#   python migrate_fix_schema_drift.py                   # -> asados.db
#   python migrate_fix_schema_drift.py path/to/other.db  # -> a copy
#
# SAFE TO RUN TWICE. It inspects the current schema first and skips
# whatever is already correct, printing what it found either way.
#
# ON PYTHONANYWHERE: backup -> git pull -> run this -> then Reload.
# Same order and reasoning as every other migration (README has the
# full checklist).
# =====================================================================

import os
import sqlite3
import sys

from backup_db import backup_database

DATABASE = "asados.db"

# Every table whose row count must be identical before and after.
EXISTING_TABLES = [
    "users", "asados", "asado_tipo_carne", "asado_cortes",
    "participations", "activity_log", "activity_log_changes", "locations",
]

MISSING_INDEXES = [
    ("idx_activity_log_asado_id", "activity_log", "asado_id"),
    ("idx_activity_log_user_id", "activity_log", "user_id"),
    ("idx_locations_created_by", "locations", "created_by"),
]

# The shape locations SHOULD have, copied from schema.sql. Rebuilding is
# the only way to add NOT NULL to an existing SQLite column — there is
# no ALTER TABLE for it.
LOCATIONS_NEW = """
CREATE TABLE locations_migrated (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    address TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    created_by INTEGER,
    created_at TEXT NOT NULL,

    FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE SET NULL
);
"""


def count_rows(db, tables):
    counts = {}
    for table in tables:
        try:
            counts[table] = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except sqlite3.OperationalError:
            counts[table] = None
    return counts


def locations_needs_rebuild(db):
    """True if any of the three columns is still nullable.

    Read from PRAGMA table_info rather than by matching the CREATE
    statement's text — the pragma is SQLite's own parse of the schema,
    so it can't be fooled by whitespace or comments."""
    nullable = [r[1] for r in db.execute("PRAGMA table_info(locations)")
                if r[1] in ("address", "latitude", "longitude") and not r[3]]
    return nullable


def rebuild_locations(db):
    """The 12-step table rebuild, in the order SQLite's own docs
    prescribe. The order matters: foreign_keys must be OFF for the
    drop-and-rename (otherwise dropping the old table looks like it
    orphans nothing but can still trip the pragma mid-transaction), and
    foreign_key_check must run BEFORE the commit so a violation can
    still be rolled back."""
    db.execute("PRAGMA foreign_keys = OFF")
    db.execute("BEGIN")
    try:
        db.execute(LOCATIONS_NEW)
        db.execute("""
            INSERT INTO locations_migrated
                (id, name, address, latitude, longitude, created_by, created_at)
            SELECT id, name, address, latitude, longitude, created_by, created_at
            FROM locations
        """)
        db.execute("DROP TABLE locations")
        db.execute("ALTER TABLE locations_migrated RENAME TO locations")
        violations = db.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(f"foreign_key_check failed: {violations}")
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK")
        raise
    finally:
        db.execute("PRAGMA foreign_keys = ON")


def main(database=DATABASE):
    print(f"Migration: fix schema drift  ->  {database}")
    print("=" * 62)
    if not os.path.exists(database):
        print(f"ERROR: '{database}' not found.")
        return 1

    # Same reasoning as migrate_add_cortes.py: a schema change is the
    # "something risky" worth an explicit backup, placed next to the
    # database being migrated rather than in the current directory's
    # backups/ (so migrating a test copy can't drop a snapshot of that
    # copy into the real backups folder, named like a real one).
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(database)), "backups")
    backup_database(database=database, backup_dir=backup_dir)
    print()

    db = sqlite3.connect(database)
    try:
        before = count_rows(db, EXISTING_TABLES)

        # --- 1. indexes (cheap, idempotent, no data movement) ---
        existing = {r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index'")}
        for name, table, column in MISSING_INDEXES:
            if name in existing:
                print(f"index {name:34s} already present")
            else:
                db.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({column})")
                print(f"index {name:34s} CREATED")
        db.commit()

        # --- 2. locations NOT NULL (a rebuild; do the safety checks first) ---
        print()
        nullable = locations_needs_rebuild(db)
        if not nullable:
            print("locations.address/latitude/longitude already NOT NULL — nothing to do")
        else:
            print(f"locations: still nullable -> {', '.join(nullable)}")
            bad = db.execute("""
                SELECT COUNT(*) FROM locations
                WHERE address IS NULL OR latitude IS NULL OR longitude IS NULL
            """).fetchone()[0]
            if bad:
                # Refuse rather than guess. Inventing a value for a
                # missing address or coordinate would be fabricating
                # data; the operator has to decide what those rows mean.
                print(f"\nSTOPPED: {bad} existing row(s) have a NULL in one of those")
                print("columns, so adding NOT NULL would fail. Fix or delete those")
                print("rows on /ubicaciones first, then re-run this.")
                return 1
            print("  no NULL values present — safe to add the constraint")
            rebuild_locations(db)
            print("  locations rebuilt with NOT NULL on address/latitude/longitude")
            # The rebuild drops the table, and its indexes with it.
            db.execute("CREATE INDEX IF NOT EXISTS idx_locations_created_by "
                       "ON locations (created_by)")
            db.commit()
            print("  idx_locations_created_by re-created (a table rebuild drops indexes)")

        after = count_rows(db, EXISTING_TABLES)
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        fk = db.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        db.close()

    # --- prove nothing was lost ---
    print()
    print(f"{'table':<24} {'before':>8} {'after':>8}   status")
    print("-" * 62)
    unchanged = True
    for table in EXISTING_TABLES:
        b, a = before[table], after[table]
        if b is None and a is None:
            print(f"{table:<24} {'n/a':>8} {'n/a':>8}   not in this database")
        elif b == a:
            print(f"{table:<24} {b:>8} {a:>8}   ok")
        else:
            unchanged = False
            print(f"{table:<24} {b:>8} {a:>8}   *** CHANGED — INVESTIGATE ***")
    print("-" * 62)
    print(f"integrity_check: {integrity}")
    print(f"foreign_key_check: {'ok' if not fk else fk}")

    if unchanged and integrity == "ok" and not fk:
        print("\nMigration OK: schema fixed, every existing table untouched.")
        return 0
    print("\nMIGRATION FAILED — restore from the backup printed above.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else DATABASE))
