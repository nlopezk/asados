# =====================================================================
# backup_db.py
# Makes a safe copy of asados.db, and deletes copies older than a
# retention window so backups don't quietly accumulate forever.
#
# This is called AUTOMATICALLY by app.py every time a new asado is
# saved (see new_asado() in app.py) — you don't need to schedule
# anything yourself. It's also runnable by hand for an on-demand extra
# backup (e.g. right before you're about to try something risky):
#   python backup_db.py [retention_days]
#
# WHY NOT JUST COPY THE FILE (e.g. `shutil.copy` or `cp`)?
# asados.db can be written to at any moment. A plain file copy has no
# idea whether it's grabbing the file mid-write — worst case, you'd
# back up a half-written, CORRUPTED database and not find out until
# the day you actually need it. sqlite3's built-in Connection.backup()
# is SQLite's own official mechanism for this exact situation: it
# produces a complete, consistent snapshot of a LIVE database safely,
# even while other connections are reading or writing it.
#
# WHERE BACKUPS GO: a "backups/" folder next to this file (created
# automatically), as asados_YYYY-MM-DD_HHMMSS.db. That folder is NOT
# under static/, so Flask never serves it over the web. This protects
# against accidental bad data (a mistaken delete, a bug, a bad edit) —
# it does NOT protect against losing the whole server/account, since
# the backups live on the same disk as the live database. For that
# you'd want to periodically copy the backups/ folder somewhere else
# entirely (a manual step for now — see CLAUDE.md).
# =====================================================================

import os
import sys
import sqlite3
from datetime import datetime, timedelta

DATABASE = "asados.db"
BACKUP_DIR = "backups"
RETENTION_DAYS = 14


def backup_database(database=DATABASE, backup_dir=BACKUP_DIR, retention_days=RETENTION_DAYS):
    if not os.path.exists(database):
        print(f"Error: '{database}' not found — nothing to back up.")
        return

    os.makedirs(backup_dir, exist_ok=True)

    # A sortable, human-readable timestamp in the filename means the
    # files themselves list in chronological order in any file browser,
    # and you can tell at a glance when each one was taken.
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"asados_{timestamp}.db")

    source = sqlite3.connect(database)
    try:
        dest = sqlite3.connect(backup_path)
        try:
            # This is the actual backup: SQLite copies every page of
            # the live source database into dest, safely, even if
            # something else is reading/writing source at this exact
            # moment. See the file header comment for why this is used
            # instead of a plain file copy.
            source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()

    print(f"Backup created: {backup_path}")
    _prune_old_backups(backup_dir, retention_days)
    return backup_path


def _prune_old_backups(backup_dir, retention_days):
    """Deletes asados_*.db files older than retention_days — otherwise
    a backup made on every asado would accumulate forever and
    eventually fill up the disk (a real concern on a free hosting
    tier's limited quota, not just a tidiness thing)."""
    cutoff = datetime.now() - timedelta(days=retention_days)
    removed = 0

    for filename in os.listdir(backup_dir):
        if not (filename.startswith("asados_") and filename.endswith(".db")):
            continue  # ignore anything in this folder that isn't one of our own backups

        path = os.path.join(backup_dir, filename)
        modified = datetime.fromtimestamp(os.path.getmtime(path))
        if modified < cutoff:
            os.remove(path)
            removed += 1

    if removed:
        print(f"Removed {removed} backup(s) older than {retention_days} days.")


if __name__ == "__main__":
    retention = RETENTION_DAYS
    if len(sys.argv) > 1:
        try:
            retention = int(sys.argv[1])
        except ValueError:
            print("Usage: python backup_db.py [retention_days]")
            sys.exit(1)

    backup_database(retention_days=retention)
