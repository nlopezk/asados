# =====================================================================
# migrate_locations_unique_name.py
# Makes locations.name UNIQUE in every group database that doesn't have
# it yet, WITHOUT touching any data.
#
# ---------------------------------------------------------------------
# WHY
# ---------------------------------------------------------------------
# Two saved locations with the same name would be indistinguishable in
# the asado form's "Ubicación guardada" dropdown, so the app refuses a
# duplicate name in create_location(), edit_location() and
# maybe_save_location(). The database was meant to back that up with a
# UNIQUE constraint - and in the original group ("Parrilla y Alma") it
# does: migrate_fix_schema_drift.py added it when it rebuilt the table.
#
# But schema.sql's own `locations` table never got the word UNIQUE.
# schema.sql is what `manage_groups.py create` uses for every NEW group,
# so every group created since v2.0 has been missing the constraint.
# Found by compare_schema.py (the new-migration skill), not by any
# error: the app-level checks were still holding, so nothing visible
# went wrong - the backstop simply wasn't there.
#
# ---------------------------------------------------------------------
# WHY A UNIQUE INDEX, NOT A TABLE REBUILD
# ---------------------------------------------------------------------
# SQLite can't add a column-level UNIQUE to an existing table without
# rebuilding it (copy every row into a new table, drop the old one,
# rename). But inside SQLite a UNIQUE constraint IS a unique index -
# enforced exactly the same way. So this script adds
#     CREATE UNIQUE INDEX idx_locations_name_unique ON locations (name)
# instead: purely additive, no row moves anywhere. Groups that already
# have the constraint (Parrilla y Alma) are detected and left alone, so
# they don't end up with a second, redundant index.
#
# Case: the constraint is case-SENSITIVE ("Casa" and "casa" are
# different to it), exactly like the one Parrilla y Alma already has.
# The app's own checks are the stricter, case-insensitive layer.
#
# If a group already HAS two locations with the same name, creating the
# index would fail - so the script checks first and STOPS with a list of
# the duplicates, rather than guessing which one to delete or rename.
# Rename one on /ubicaciones, then re-run.
#
# ---------------------------------------------------------------------
# SAFETY (the rules every migration here follows)
# ---------------------------------------------------------------------
#   * additive only; idempotent (an already-applied group says "already
#     present"); one transaction; backs up first, next to the database
#     (backup_dir_for()), and refuses to run if the backup fails; prints
#     every table's row count before and after.
#   * does NOT read schema.sql (it starts with DROP TABLE) and does NOT
#     import app.py. sqlite3 is standard library, so it runs on
#     PythonAnywhere without activating the virtualenv.
#
# ---------------------------------------------------------------------
# USAGE
# ---------------------------------------------------------------------
#   python migrate_locations_unique_name.py                   # -> every registered group
#   python migrate_locations_unique_name.py path/to/copy.db   # -> one isolated copy
#
# ON PYTHONANYWHERE: backup -> git pull -> run every migration (this one
# included) -> THEN Reload. See README, "Deploying an update".
# =====================================================================

import os
import sys

from accounts import connect_existing
from backup_db import backup_database, backup_dir_for

MIGRATION_NAME = "locations.name UNIQUE"


def has_unique_on_name(db):
    """True if ANY unique index covers exactly locations(name) - either
    the auto-index behind a column's UNIQUE constraint (what Parrilla y
    Alma has) or the index this script creates. Read from PRAGMAs,
    SQLite's own view of the schema."""
    for idx in db.execute("PRAGMA index_list(locations)"):
        unique, name = idx[2], idx[1]
        if unique and [c[2] for c in db.execute(f"PRAGMA index_info({name})")] == ["name"]:
            return True
    return False


STEPS = [
    {
        "describe": "unique index on locations(name)",
        "is_applied": has_unique_on_name,
        "sql": "CREATE UNIQUE INDEX IF NOT EXISTS idx_locations_name_unique ON locations (name)",
    },
]


def duplicate_names(db):
    return db.execute("""
        SELECT name, COUNT(*) FROM locations GROUP BY name HAVING COUNT(*) > 1 ORDER BY name
    """).fetchall()


def count_all_tables(db):
    """Row count for EVERY table in the file, discovered rather than
    listed by hand, so no table can be left out of the proof."""
    names = [r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return {n: db.execute(f"SELECT COUNT(*) FROM {n}").fetchone()[0] for n in names}


def main(database):
    print(f"Migration: {MIGRATION_NAME}  ->  {database}")
    print("=" * 62)
    if not os.path.exists(database):
        print(f"ERROR: '{database}' not found - nothing was changed.")
        return 1

    # No backup, no migration: the backup is the undo button.
    if not backup_database(database=database, backup_dir=backup_dir_for(database)):
        print("ERROR: the backup failed, so the migration was NOT run.")
        return 1
    print()

    db = connect_existing(database)
    # Python's sqlite3 commits DDL immediately unless a transaction is
    # opened explicitly - so open one, making the steps all-or-nothing.
    db.isolation_level = None
    try:
        before = count_all_tables(db)
        pending = [s for s in STEPS if not s["is_applied"](db)]
        for s in STEPS:
            if s not in pending:
                print(f"  {s['describe']:<44} already present")

        if pending:
            dups = duplicate_names(db)
            if dups:
                # Refuse rather than guess: which of two same-named
                # places to rename or delete is the group's decision.
                print("\nSTOPPED: these location names appear more than once, so they")
                print("can't be made unique yet. Rename one of each on /ubicaciones,")
                print("then re-run this script:")
                for name, n in dups:
                    print(f"    '{name}' x{n}")
                return 1
            db.execute("BEGIN")
            try:
                for s in pending:
                    db.execute(s["sql"])
                    print(f"  {s['describe']:<44} CREATED")
                violations = db.execute("PRAGMA foreign_key_check").fetchall()
                if violations:
                    raise RuntimeError(f"foreign_key_check failed: {violations}")
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise

        after = count_all_tables(db)
        all_applied = all(s["is_applied"](db) for s in STEPS)
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        db.close()

    if not pending:
        print("\nEverything was ALREADY present - this run changed nothing.")

    # --- prove nothing was lost ---
    print()
    print(f"{'table':<24} {'before':>8} {'after':>8}   status")
    print("-" * 62)
    unchanged = True
    for table in sorted(set(before) | set(after)):
        b, a = before.get(table), after.get(table)
        if b is None:
            print(f"{table:<24} {'-':>8} {a:>8}   new table")
        elif b == a:
            print(f"{table:<24} {b:>8} {a:>8}   ok")
        else:
            unchanged = False
            print(f"{table:<24} {b:>8} {str(a):>8}   *** CHANGED - INVESTIGATE ***")
    print("-" * 62)
    print(f"integrity_check: {integrity}")

    if unchanged and all_applied and integrity == "ok":
        print(f"\nMigration OK: {MIGRATION_NAME} applied, every existing table untouched.")
        return 0
    print("\nMIGRATION FAILED - restore from the backup printed above.")
    return 1


if __name__ == "__main__":
    # No argument = EVERY registered group (accounts.migration_targets()).
    from accounts import migration_targets
    targets = migration_targets(sys.argv[1:])
    if not targets:
        print("No database to migrate (fresh checkout?). Nothing done.")
    results = []
    for target in targets:
        try:
            results.append(main(target))
        except Exception as e:
            # Anything raised inside BEGIN...COMMIT was rolled back.
            print(f"\nMIGRATION FAILED on {target}: {type(e).__name__}: {e}")
            print("Nothing was committed. The backup printed above is there too.")
            results.append(1)
        print()
    sys.exit(max(results, default=0))
