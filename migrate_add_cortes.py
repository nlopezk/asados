# =====================================================================
# migrate_add_cortes.py
# Adds the asado_cortes table (and its index) to an EXISTING database
# WITHOUT touching anything already in it.
#
# ---------------------------------------------------------------------
# WHY THIS FILE EXISTS AT ALL
# ---------------------------------------------------------------------
# This project has no migration system. schema.sql opens with DROP
# TABLE, and app.py's init_db() runs it verbatim. That was harmless
# when the database held randomly-seeded test data — you'd just
# re-seed. It is NOT harmless now: asados.db holds the group's real,
# irreplaceable history (239 asados / 269 participations as of this
# writing), locally AND on PythonAnywhere. Running init_db() would
# destroy it.
#
# So from now on, a schema change ships as a script like this one:
#   * ADDITIVE ONLY — it creates, it never drops or alters,
#   * IDEMPOTENT — safe to run twice, because you will,
#   * and it reports what it did, in row counts, so you can SEE that
#     nothing was lost rather than trusting that it wasn't.
#
# It deliberately does NOT read schema.sql, even though schema.sql
# contains the same CREATE TABLE text. Reading it would drag those DROP
# TABLE statements along, which is the exact disaster this script
# exists to avoid. The duplicated CREATE below is a knowing violation
# of this project's usual "one place decides the shape" rule (see
# CLAUDE.md) — accepted because the only way to avoid the copy is to
# execute the file that destroys the data. Six duplicated lines is the
# cheaper risk by a wide margin. If the two ever drift, schema.sql is
# authoritative for FRESH databases and this file for already-migrated
# ones.
#
# It also deliberately does not import app.py — so there is no path,
# however indirect, from running this to running init_db(). That also
# means it works from a PythonAnywhere Bash console without activating
# the virtualenv, since sqlite3 is part of the standard library.
#
# ---------------------------------------------------------------------
# USAGE
# ---------------------------------------------------------------------
#   python migrate_add_cortes.py                   # -> asados.db
#   python migrate_add_cortes.py path/to/other.db  # -> an isolated copy
#
# SAFE TO RUN TWICE. Both statements use IF NOT EXISTS, so a second run
# is a no-op that says "already present" instead of erroring.
#
# ON PYTHONANYWHERE, ORDER MATTERS:
#   1. git pull
#   2. python3 migrate_add_cortes.py   <-- BEFORE the reload
#   3. Web tab -> Reload
# Reloading first would put the new code live against a database with
# no asado_cortes table, and every asado page would throw "no such
# table" until step 2 ran. Pulling doesn't restart the app, so the old
# code keeps serving safely until you reload.
# =====================================================================

import os
import sqlite3
import sys

from backup_db import backup_database

DATABASE = "asados.db"

# See schema.sql for the fully commented version of this table,
# including why there is deliberately no `corte_weight` column.
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS asado_cortes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asado_id INTEGER NOT NULL,
    corte TEXT NOT NULL,
    FOREIGN KEY (asado_id) REFERENCES asados (id)
);
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_asado_cortes_asado_id ON asado_cortes (asado_id);
"""

# Every table that must still be here, with exactly the same number of
# rows, when this script finishes. Counted before and after and printed
# side by side — reading "asados: 239 -> 239" with your own eyes is the
# proof that nothing was dropped. Trusting IF NOT EXISTS to have done
# the right thing is not the same thing as checking.
EXISTING_TABLES = [
    "users",
    "asados",
    "asado_tipo_carne",
    "participations",
    "activity_log",
    "activity_log_changes",
    "locations",
]


def count_rows(db, tables):
    """Row count per table, skipping any that don't exist yet (an older
    database predating some feature is a legitimate state, not an
    error — report it rather than crashing halfway through)."""
    counts = {}
    for table in tables:
        try:
            counts[table] = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except sqlite3.OperationalError:
            counts[table] = None  # table not present in this database
    return counts


def table_exists(db, name):
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone()
    return row is not None


def main(database=DATABASE):
    print(f"Migration: add asado_cortes  ->  {database}")
    print("=" * 60)

    # A schema change is exactly the "something risky" that backup_db.py's
    # own header describes as worth an on-demand backup. new_asado() is
    # the only route that backs up automatically, and this isn't a route,
    # so take one here explicitly. Uses SQLite's own Connection.backup(),
    # never a plain file copy — see backup_db.py for why that matters.
    #
    # The backup goes NEXT TO whichever database is being migrated, not
    # into backup_db.py's default "backups/" (which is relative to the
    # current directory). Running this against an isolated test copy
    # from the project root would otherwise drop a backup of the TEST
    # database into the real backups/ folder, named exactly like a real
    # one — indistinguishable later, at precisely the moment you'd be
    # reaching for a backup because something went wrong.
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(database)), "backups")
    backup_database(database=database, backup_dir=backup_dir)
    print()

    db = sqlite3.connect(database)
    try:
        already_present = table_exists(db, "asado_cortes")
        before = count_rows(db, EXISTING_TABLES)

        db.execute(CREATE_TABLE_SQL)
        db.execute(CREATE_INDEX_SQL)
        db.commit()

        after = count_rows(db, EXISTING_TABLES)
        created_ok = table_exists(db, "asado_cortes")
        cortes_rows = db.execute("SELECT COUNT(*) FROM asado_cortes").fetchone()[0]
    finally:
        db.close()

    if already_present:
        print("asado_cortes was ALREADY present — this run changed nothing.")
    else:
        print("asado_cortes created.")
    print(f"asado_cortes now holds {cortes_rows} row(s).")
    print()

    # The whole point of the script's output: prove the existing data
    # survived, table by table.
    print(f"{'table':<24} {'before':>8} {'after':>8}   status")
    print("-" * 60)
    unchanged = True
    for table in EXISTING_TABLES:
        b, a = before[table], after[table]
        if b is None and a is None:
            print(f"{table:<24} {'n/a':>8} {'n/a':>8}   not in this database")
            continue
        if b == a:
            print(f"{table:<24} {b:>8} {a:>8}   ok")
        else:
            unchanged = False
            print(f"{table:<24} {b:>8} {a:>8}   *** CHANGED — INVESTIGATE ***")

    print("-" * 60)
    if unchanged and created_ok:
        print("Migration OK: asado_cortes present, every existing table untouched.")
        return 0

    # Loud, and a non-zero exit code, so this can never be mistaken for
    # success in a scrollback or a script.
    print("MIGRATION FAILED — restore from the backup printed above.")
    return 1


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else DATABASE
    sys.exit(main(target))
