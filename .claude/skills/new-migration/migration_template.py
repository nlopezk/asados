# =====================================================================
# migrate_<WHAT>.py                        <-- rename, e.g. migrate_add_fotos.py
# <ONE LINE: what this adds, e.g. "Adds the asado_fotos table and its index">
# to EXISTING databases WITHOUT touching anything already in them.
#
# ---------------------------------------------------------------------
# WHY  <-- the reason for the change, in plain words. Someone reading
#          this in a year should understand what feature needed it.
# ---------------------------------------------------------------------
#
# ---------------------------------------------------------------------
# HOW THIS SCRIPT STAYS SAFE (the same rules every migration here follows)
# ---------------------------------------------------------------------
#   * ADDITIVE ONLY - it creates tables, columns and indexes; it never
#     drops, renames or rewrites. (Need NOT NULL on an existing column,
#     a dropped column or a changed type? That's a table REBUILD - see
#     migrate_fix_schema_drift.py's rebuild_locations() for the 12-step
#     recipe, and talk it through first: it moves every row.)
#   * IDEMPOTENT - every step checks "is this already applied?" first,
#     so running it twice is a no-op that says so. It WILL be run twice:
#     every deploy runs every migration (see README, "Deploying an update").
#   * ALL OR NOTHING - the steps run inside one transaction, so a failure
#     halfway leaves the database exactly as it was, not half-migrated.
#   * BACKS UP FIRST, next to the database being migrated (backup_dir_for()),
#     so migrating a test copy never drops a snapshot into the real backups/.
#   * PROVES NOTHING WAS LOST - counts every table's rows before and after
#     and prints them side by side. Reading "asados: 239 -> 239" is the
#     proof; trusting IF NOT EXISTS is not.
#   * It does NOT read schema.sql. The CREATE statements below are copied
#     from it by hand, because reading that file would drag its DROP TABLE
#     lines along - the one thing this script exists to never do. If the
#     two ever drift, schema.sql is authoritative for FRESH databases and
#     this file for already-migrated ones.
#   * It does NOT import app.py - no path, however indirect, from running
#     this to app-level setup. sqlite3 is standard library, so it also
#     runs on PythonAnywhere without activating the virtualenv.
#
# ---------------------------------------------------------------------
# USAGE
# ---------------------------------------------------------------------
#   python migrate_<WHAT>.py                   # -> every registered group's database
#   python migrate_<WHAT>.py path/to/copy.db   # -> one isolated copy (test here first)
#
# ON PYTHONANYWHERE, ORDER MATTERS: backup -> git pull -> run this ->
# THEN Reload. Reloading first would put new code live against a
# database without the new table/column, and the pages using it would
# error until this ran.
# =====================================================================

import os
import sys

from accounts import connect_existing
from backup_db import backup_database, backup_dir_for

MIGRATION_NAME = "<WHAT, e.g. add asado_fotos>"


# --- small "is it already there?" helpers ----------------------------
# Read from sqlite_master / PRAGMA table_info - SQLite's own parse of the
# schema - never by matching CREATE statement text.
def table_exists(db, name):
    return db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone() is not None


def column_exists(db, table, column):
    return any(r[1] == column for r in db.execute(f"PRAGMA table_info({table})"))


def index_exists(db, name):
    return db.execute("SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ?", (name,)).fetchone() is not None


# --- THE CHANGE ITSELF -----------------------------------------------
# One entry per step, in order. Each has:
#   describe   - what gets printed ("table asado_fotos")
#   is_applied - a function returning True if this step is already done
#   sql        - the statement that does it, copied from schema.sql
#
# Why an explicit is_applied check when CREATE ... IF NOT EXISTS exists:
# ALTER TABLE ... ADD COLUMN has NO "if not exists" form in SQLite - run
# twice, it errors. The check makes every kind of step idempotent the
# same way, and lets the output say "already present" vs "CREATED".
#
# EXAMPLES - delete the ones you don't need:
STEPS = [
    {
        "describe": "table asado_EXAMPLE",
        "is_applied": lambda db: table_exists(db, "asado_EXAMPLE"),
        "sql": """
            CREATE TABLE IF NOT EXISTS asado_EXAMPLE (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asado_id INTEGER NOT NULL,
                value TEXT NOT NULL,
                FOREIGN KEY (asado_id) REFERENCES asados (id)
            )
        """,
    },
    {
        # Every foreign key gets an index: SQLite only auto-indexes
        # PRIMARY KEY and UNIQUE columns, so without this every
        # "WHERE asado_id = ?" is a full table scan (the v1.0.0 audit).
        "describe": "index idx_asado_EXAMPLE_asado_id",
        "is_applied": lambda db: index_exists(db, "idx_asado_EXAMPLE_asado_id"),
        "sql": "CREATE INDEX IF NOT EXISTS idx_asado_EXAMPLE_asado_id ON asado_EXAMPLE (asado_id)",
    },
    {
        # A new column on an existing table. It must be NULLable or have
        # a DEFAULT - SQLite can't add a NOT NULL column without one,
        # because the existing rows would have nothing to put there.
        "describe": "column asados.EXAMPLE",
        "is_applied": lambda db: column_exists(db, "asados", "EXAMPLE"),
        "sql": "ALTER TABLE asados ADD COLUMN EXAMPLE TEXT",
    },
]


def count_all_tables(db):
    """Row count for EVERY table currently in the file. Discovered from
    sqlite_master rather than a hand-written list (the older migrations
    use a list) so a table added later can never be left out of the
    before/after proof by someone forgetting to update the list."""
    names = [r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return {n: db.execute(f"SELECT COUNT(*) FROM {n}").fetchone()[0] for n in names}


def main(database):
    print(f"Migration: {MIGRATION_NAME}  ->  {database}")
    print("=" * 62)
    if not os.path.exists(database):
        print(f"ERROR: '{database}' not found - nothing was changed.")
        return 1

    # Backup BEFORE opening for writing. Same SQLite-level backup as
    # backup_db.py (never a plain file copy - see that file for why).
    # backup_database() returns the new file's path, or None if it
    # couldn't make one - and "no backup" means "don't migrate": the
    # backup is the undo button for everything below.
    if not backup_database(database=database, backup_dir=backup_dir_for(database)):
        print("ERROR: the backup failed, so the migration was NOT run.")
        return 1
    print()

    # connect_existing() refuses to CREATE a missing file - a typo in
    # the path must be an error, not a fresh empty "database" that then
    # gets migrated and reported as a success.
    db = connect_existing(database)
    # Python's sqlite3 commits DDL (CREATE/ALTER) immediately unless a
    # transaction is opened explicitly - so open one, to make the steps
    # all-or-nothing.
    db.isolation_level = None
    try:
        before = count_all_tables(db)
        pending = [s for s in STEPS if not s["is_applied"](db)]
        for s in STEPS:
            if s not in pending:
                print(f"  {s['describe']:<44} already present")

        if pending:
            db.execute("BEGIN")
            try:
                for s in pending:
                    db.execute(s["sql"])
                    print(f"  {s['describe']:<44} CREATED")
                # foreign_key_check before COMMIT, so a violation can still
                # be rolled back (same order as migrate_fix_schema_drift.py).
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
    # Loud, with a non-zero exit code, so it can't be mistaken for success.
    print("\nMIGRATION FAILED - restore from the backup printed above.")
    return 1


if __name__ == "__main__":
    # No argument = EVERY registered group (accounts.migration_targets()).
    # One failure fails the whole run, but every target is still
    # attempted and reported, so you see the full picture at once.
    from accounts import migration_targets
    targets = migration_targets(sys.argv[1:])
    if not targets:
        print("No database to migrate (fresh checkout?). Nothing done.")
    results = []
    for target in targets:
        try:
            results.append(main(target))
        except Exception as e:
            # Anything raised inside the BEGIN...COMMIT block was rolled
            # back before it got here, so the file is as it was.
            print(f"\nMIGRATION FAILED on {target}: {type(e).__name__}: {e}")
            print("Nothing was committed. The backup printed above is there too.")
            results.append(1)
        print()
    sys.exit(max(results, default=0))
