# =====================================================================
# migrate_add_asado_status.py
# Adds the `status` column to the asados table ('planificado' or
# 'confirmado') in EXISTING databases, without touching anything else.
#
# ---------------------------------------------------------------------
# WHY
# ---------------------------------------------------------------------
# Asados can now be added ahead of time (the calendar, issue #5). Plans
# change, so an asado dated in the future is an "Asado Planificado": it
# earns NO points and appears in no standings until a member saves it on
# or after its date, which confirms it (issue #17, GLOSSARY.md,
# docs/adr/0001-planned-asados-score-on-confirmation.md). The app needs
# to remember which asados are confirmed, hence this column.
#
# WHAT EXISTING ASADOS BECOME - the one judgement in this migration:
#   * dated TODAY OR EARLIER -> 'confirmado'. That's every asado the
#     group has actually held, so every points total, the standings and
#     the charts come out EXACTLY as they were before this migration.
#   * dated AFTER TODAY      -> 'planificado'. Before this feature, the
#     app accepted future dates and scored them straight away; such an
#     asado hasn't happened yet, so by the new rule it doesn't count yet.
#     The script prints how many it marked and which ones, so you can
#     check that number on PythonAnywhere (normally 0).
# "Today" is Chile's date (asado_record.today()), the same one the app
# uses, so this script and the app agree on where "the future" starts.
#
# ---------------------------------------------------------------------
# HOW THIS SCRIPT STAYS SAFE (the same rules every migration here follows)
# ---------------------------------------------------------------------
#   * ADDITIVE ONLY - one new column with a DEFAULT, which SQLite can add
#     in place (ALTER TABLE ... ADD COLUMN) without rebuilding the table
#     or moving a single row. The only data it writes is that column's
#     value for future-dated asados.
#   * IDEMPOTENT - if the column is already there, it does nothing at all
#     (it does NOT re-mark anything: from then on the APP owns the
#     column, and a re-run must never overwrite what members confirmed).
#     It WILL be run again: every deploy runs every migration.
#   * ALL OR NOTHING - one transaction; a failure leaves the file as it was.
#   * BACKS UP FIRST, next to the database (backup_dir_for()), and refuses
#     to run if the backup fails.
#   * PROVES NOTHING WAS LOST - every table's row count, before and after.
#   * Does NOT read schema.sql (it starts with DROP TABLE) and does NOT
#     import app.py. It imports asado_record only for today(); that module
#     uses nothing outside Python's standard library, so this still runs
#     on PythonAnywhere without activating the virtualenv.
#
# ---------------------------------------------------------------------
# USAGE
# ---------------------------------------------------------------------
#   python migrate_add_asado_status.py                   # -> every registered group
#   python migrate_add_asado_status.py path/to/copy.db   # -> one isolated copy
#
# ON PYTHONANYWHERE: backup -> git pull -> run every migration (this one
# included) -> THEN Reload. Reload first and the new code asks for a
# column that isn't there yet: every page with asados would error.
# =====================================================================

import os
import sys

from accounts import connect_existing
from asado_record import today
from backup_db import backup_database, backup_dir_for

MIGRATION_NAME = "asados.status (planificado / confirmado)"

# Copied character for character from schema.sql's asados table.
ADD_COLUMN_SQL = (
    "ALTER TABLE asados ADD COLUMN status TEXT NOT NULL DEFAULT 'confirmado' "
    "CHECK (status IN ('planificado', 'confirmado'))"
)


def has_status_column(db):
    """True if asados already has a `status` column - read from
    PRAGMA table_info, SQLite's own description of the table."""
    return any(col[1] == "status" for col in db.execute("PRAGMA table_info(asados)"))


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
    planned = []
    try:
        before = count_all_tables(db)
        already = has_status_column(db)
        if already:
            print(f"  {'status column on asados':<44} already present")
        else:
            cutoff = today().isoformat()
            db.execute("BEGIN")
            try:
                db.execute(ADD_COLUMN_SQL)
                print(f"  {'status column on asados':<44} CREATED")
                # Every row now says 'confirmado' (the DEFAULT). The ones
                # that haven't happened yet become 'planificado'. Plain
                # text comparison works because dates are 'YYYY-MM-DD'.
                planned = db.execute(
                    "SELECT id, date, nombre FROM asados WHERE date > ? ORDER BY date", (cutoff,)
                ).fetchall()
                db.execute("UPDATE asados SET status = 'planificado' WHERE date > ?", (cutoff,))
                print(f"  {'asados dated after ' + cutoff + ' -> planificado':<44} {len(planned)}")
                for asado_id, asado_date, nombre in planned:
                    print(f"      #{asado_id}  {asado_date}  {nombre}")
                violations = db.execute("PRAGMA foreign_key_check").fetchall()
                if violations:
                    raise RuntimeError(f"foreign_key_check failed: {violations}")
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise

        after = count_all_tables(db)
        applied = has_status_column(db)
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        statuses = dict(db.execute("SELECT status, COUNT(*) FROM asados GROUP BY status").fetchall()) if applied else {}
    finally:
        db.close()

    if already:
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
    print(f"asados by status: {statuses}")
    print(f"integrity_check: {integrity}")

    if unchanged and applied and integrity == "ok":
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
