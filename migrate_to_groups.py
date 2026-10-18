# =====================================================================
# migrate_to_groups.py
# Turns the single-group app (one asados.db) into the multi-group
# layout introduced in v2.0:
#
#     asados.db  ──copy──►  groups/parrilla-y-alma.db   (all the asados)
#                           accounts.db                  (logins + groups)
#
# ---------------------------------------------------------------------
# WHAT IT DOES, IN ORDER
# ---------------------------------------------------------------------
#   1. Checks everything it can BEFORE writing anything (source exists,
#      no half-finished earlier run, no usernames that would collide).
#   2. Backs up asados.db (and accounts.db, if one already exists).
#   3. COPIES asados.db into groups/<slug>.db — with SQLite's own
#      backup(), never a plain file copy (see backup_db.py for why).
#      asados.db itself is NEVER modified. It stays exactly as it was,
#      which is the whole rollback plan: redeploy the old code and it
#      picks asados.db up again as if nothing happened.
#   4. In ONE transaction spanning both files: registers the group,
#      creates one login (account) per existing user — same username,
#      same password hash, so nobody's password changes — links each
#      to their member row, and blanks the password hashes left behind
#      in the group's copy (the real ones now live only in accounts.db).
#   5. Proves nothing was lost: row counts of every table, source vs.
#      copy, side by side.
#
# Every user id, asado id and participation id is kept exactly as it
# was — the group file is a page-for-page copy, so nothing that points
# at anything else had to be rewritten.
#
# ---------------------------------------------------------------------
# WHY ONE TRANSACTION ACROSS TWO FILES MATTERS
# ---------------------------------------------------------------------
# Writing accounts.db and then the group file as two separate commits
# would leave a window where one is done and the other isn't — e.g.
# accounts created but hashes not yet moved, or the reverse. Instead
# accounts.db is ATTACHed to the group file's connection, so a single
# COMMIT covers both: SQLite guarantees that either both files get the
# changes or neither does (in its default "rollback journal" mode,
# which this script forces on both files for exactly that reason —
# the guarantee does NOT hold in WAL mode).
#
# ---------------------------------------------------------------------
# USAGE
# ---------------------------------------------------------------------
#   python migrate_to_groups.py            # migrate (or report "already done")
#   python migrate_to_groups.py --verify   # run ONCE right after Reload; see below
#
# SAFE TO RUN TWICE — and, like every other migration here, meant to be
# run on EVERY deploy. Once done, it says "ALREADY migrated" and changes
# nothing.
#
# Options for testing against isolated copies (defaults in brackets):
#   --source PATH       the old single database      [asados.db]
#   --accounts PATH     the registry to create/use   [accounts.db]
#   --groups-dir PATH   where group files go         [groups]
#   --export-token-file PATH                         [export_token.txt]
#
# ---------------------------------------------------------------------
# ON PYTHONANYWHERE — THE ORDER MATTERS, AND SO DOES THE GAP
# ---------------------------------------------------------------------
#   1. Download a copy of asados.db (Files tab) — your offsite backup.
#   2. git pull
#   3. python3 migrate_to_groups.py
#   4. Web tab -> Reload, IMMEDIATELY
#   5. python3 migrate_to_groups.py --verify
#
# Between steps 3 and 4 the OLD code is still running and still writing
# to asados.db — anything saved in that gap (an asado added seconds
# after the copy) would land in the old file, not the new one. That's
# why step 4 follows step 3 straight away, and why step 5 exists: it
# checks that every row in the old file also made it into the group's
# file, and names what's missing if not.
# =====================================================================

import argparse
import os
import sqlite3
import sys

from accounts import (
    ACCOUNTS_DATABASE, ACCOUNTS_SCHEMA, GROUPS_DIR,
    apply_accounts_schema, group_db_path, generate_export_token, now_timestamp,
)
from backup_db import backup_database

SOURCE_DATABASE = "asados.db"
EXPORT_TOKEN_FILE = "export_token.txt"

# The group the existing data becomes. The NAME can be changed later
# (it's just a column); the SLUG can't — it names the database file.
DEFAULT_SLUG = "parrilla-y-alma"
DEFAULT_NAME = "Parrilla y Alma"

# Every table in a group database. All of them have an `id` column,
# which --verify relies on.
GROUP_TABLES = [
    "users",
    "asados",
    "asado_tipo_carne",
    "asado_cortes",
    "participations",
    "activity_log",
    "activity_log_changes",
    "locations",
]

# accounts_schema.sql is looked up next to THIS script, not in the
# current directory, so running the script from elsewhere still finds it.
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ACCOUNTS_SCHEMA)


def table_exists(db, name, schema="main"):
    row = db.execute(
        f"SELECT name FROM {schema}.sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone()
    return row is not None


def count_rows(db, tables):
    """Row count per table; None for a table this database doesn't have
    (an older database predating a feature is a legitimate state)."""
    counts = {}
    for table in tables:
        try:
            counts[table] = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except sqlite3.OperationalError:
            counts[table] = None
    return counts


def read_export_token(path):
    """Reuse the old export_token.txt so existing Google Sheets
    IMPORTDATA() formulas keep working with no edit. Only a brand-new
    token if there was never one."""
    if os.path.exists(path):
        with open(path, "r") as f:
            token = f.read().strip()
        if token:
            return token, True
    return generate_export_token(), False


def registry_state(accounts_path, slug):
    """Returns the existing asado_groups row for this slug, or None —
    without creating accounts.db if it isn't there yet."""
    if not os.path.exists(accounts_path):
        return None
    conn = sqlite3.connect(accounts_path)
    conn.row_factory = sqlite3.Row
    try:
        if not table_exists(conn, "asado_groups"):
            return None
        return conn.execute("SELECT id, slug, name FROM asado_groups WHERE slug = ?", (slug,)).fetchone()
    finally:
        conn.close()


def find_username_problems(source_path, accounts_path):
    """
    Usernames become unique across the WHOLE site, case-insensitively
    (see accounts_schema.sql). Two users differing only in case ("Nico"
    and "nico"), or one that already exists in accounts.db from another
    group, would make the migration fail halfway — so find them first
    and refuse before anything is written.

    lower() here and COLLATE NOCASE in the schema both fold ASCII
    letters only, so the two agree on what counts as "the same".
    """
    problems = []
    src = sqlite3.connect(source_path)
    try:
        for (folded, n) in src.execute(
            "SELECT lower(username), COUNT(*) FROM users GROUP BY lower(username) HAVING COUNT(*) > 1"
        ):
            problems.append(f"'{folded}' appears {n} times in {source_path} (differing only in case)")
        usernames = [r[0] for r in src.execute("SELECT username FROM users")]
    finally:
        src.close()

    if os.path.exists(accounts_path):
        acc = sqlite3.connect(accounts_path)
        try:
            if table_exists(acc, "accounts"):
                for username in usernames:
                    if acc.execute("SELECT 1 FROM accounts WHERE username = ? COLLATE NOCASE", (username,)).fetchone():
                        problems.append(f"'{username}' already has an account in {accounts_path}")
        finally:
            acc.close()
    return problems


def migrate(source_path, accounts_path, groups_dir, token_path, slug, name):
    target_path = group_db_path(slug, groups_dir)
    print(f"Migration: single database -> groups")
    print(f"  source   {source_path}")
    print(f"  group    {name}  ->  {target_path}")
    print(f"  registry {accounts_path}")
    print("=" * 60)

    # --- 1. Checks. Nothing has been written yet. ----------------------
    existing = registry_state(accounts_path, slug)
    if existing is not None:
        if os.path.exists(target_path):
            print(f"ALREADY migrated: group '{existing['name']}' is registered and "
                  f"{target_path} exists. This run changed nothing.")
            return 0
        print(f"ERROR: {accounts_path} lists group '{slug}' but {target_path} is missing.")
        print("Do not re-run. Restore groups/ from a backup, or ask for help.")
        return 1

    if not os.path.exists(source_path):
        print(f"No {source_path} found — nothing to migrate.")
        print("(Fine on a brand-new install: create groups with `manage_groups.py create` instead.)")
        return 0

    if os.path.exists(target_path):
        # A group file with no registry entry: a previous run died, or
        # someone copied a file in by hand. Either way, overwriting it
        # could destroy data — stop and let a human look.
        print(f"ERROR: {target_path} already exists but isn't registered in {accounts_path}.")
        print("Not touching it. Move it aside (it may hold data) and run again.")
        return 1

    problems = find_username_problems(source_path, accounts_path)
    if problems:
        print("ERROR: these usernames would collide once logins are site-wide:")
        for p in problems:
            print(f"  - {p}")
        print("Rename one of each pair in the source database, then run again. Nothing was changed.")
        return 1

    # --- 2. Backups ----------------------------------------------------
    # Next to whichever database is being migrated (same reasoning as
    # migrate_add_cortes.py: a backup of a TEST copy must never land in
    # the real backups/ folder looking like a real one).
    source_backup_dir = os.path.join(os.path.dirname(os.path.abspath(source_path)), "backups")
    backup_database(database=source_path, backup_dir=source_backup_dir)
    if os.path.exists(accounts_path):
        backup_database(
            database=accounts_path,
            backup_dir=os.path.join(os.path.dirname(os.path.abspath(accounts_path)), "backups", "accounts"),
        )
    print()

    # --- 3. Copy the data into the group's own file --------------------
    os.makedirs(groups_dir, exist_ok=True)
    source = sqlite3.connect(source_path)
    try:
        before = count_rows(source, GROUP_TABLES)
        dest = sqlite3.connect(target_path)
        try:
            source.backup(dest)  # consistent snapshot, even if the app is writing right now
        finally:
            dest.close()
    finally:
        source.close()
    print(f"Copied {source_path} -> {target_path}")

    # --- 4. Registry + logins, one transaction across both files -------
    # Create the registry's tables first (harmless if they exist —
    # IF NOT EXISTS throughout). This part commits on its own, but it
    # only ever adds EMPTY tables, so there's nothing to undo if the
    # data step below fails.
    acc = sqlite3.connect(accounts_path)
    try:
        apply_accounts_schema(acc, SCHEMA_PATH)
        acc.commit()
    finally:
        acc.close()

    export_token, token_reused = read_export_token(token_path)
    created = now_timestamp()

    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    try:
        # ATTACH and journal_mode changes must happen OUTSIDE a
        # transaction, i.e. before the first INSERT below starts one.
        conn.execute("ATTACH DATABASE ? AS acc", (accounts_path,))
        conn.execute("PRAGMA main.journal_mode = DELETE")
        conn.execute("PRAGMA acc.journal_mode = DELETE")
        conn.execute("PRAGMA foreign_keys = ON")

        cur = conn.execute(
            "INSERT INTO acc.asado_groups (slug, name, export_token, created_at) VALUES (?, ?, ?, ?)",
            (slug, name, export_token, created),
        )
        group_id = cur.lastrowid

        users = conn.execute("SELECT id, username, password_hash FROM main.users ORDER BY id").fetchall()
        for user in users:
            cur = conn.execute(
                "INSERT INTO acc.accounts (username, password_hash, created_at) VALUES (?, ?, ?)",
                (user["username"], user["password_hash"], created),
            )
            conn.execute(
                "INSERT INTO acc.memberships (account_id, group_id, member_id, created_at) VALUES (?, ?, ?, ?)",
                (cur.lastrowid, group_id, user["id"], created),
            )

        # The group file keeps its users table (every participation
        # points at it) but no longer holds passwords. '' rather than
        # NULL because the column is NOT NULL in every existing file.
        conn.execute("UPDATE main.users SET password_hash = ''")

        conn.commit()  # <- the single commit covering BOTH files
    except Exception as e:
        conn.rollback()
        conn.close()
        # Nothing was committed, so the copy is just an unregistered
        # file — remove it so a re-run starts clean instead of hitting
        # the "exists but isn't registered" stop above.
        os.remove(target_path)
        print(f"MIGRATION FAILED, nothing was changed: {e}")
        print(f"{source_path} is untouched.")
        return 1

    # --- 5. Prove it -----------------------------------------------------
    try:
        after = count_rows(conn, GROUP_TABLES)
        leftover_hashes = conn.execute("SELECT COUNT(*) FROM main.users WHERE password_hash != ''").fetchone()[0]
        memberships = conn.execute(
            "SELECT COUNT(*) FROM acc.memberships WHERE group_id = ?", (group_id,)
        ).fetchone()[0]
    finally:
        conn.close()

    print()
    print(f"{'table':<24} {'source':>8} {'group':>8}   status")
    print("-" * 60)
    ok = True
    for table in GROUP_TABLES:
        b, a = before[table], after[table]
        if b is None and a is None:
            print(f"{table:<24} {'n/a':>8} {'n/a':>8}   not in this database")
        elif b == a:
            print(f"{table:<24} {b:>8} {a:>8}   ok")
        else:
            ok = False
            print(f"{table:<24} {b!s:>8} {a!s:>8}   *** CHANGED — INVESTIGATE ***")
    print("-" * 60)
    print(f"logins created:        {len(users)}  (one per user, same usernames and passwords)")
    print(f"memberships created:   {memberships}")
    print(f"hashes left in group:  {leftover_hashes}  (should be 0)")
    print("export token:          " + ("carried over from export_token.txt — Sheets links keep working"
                                       if token_reused else "NEW (there was no export_token.txt)"))
    print()

    if ok and memberships == len(users) and leftover_hashes == 0:
        print(f"Migration OK. '{name}' now lives in {target_path}.")
        print(f"{source_path} was not modified — keep it until v2 has run without problems.")
        return 0
    print("MIGRATION FAILED VERIFICATION — restore from the backups printed above.")
    return 1


def verify(source_path, accounts_path, groups_dir, slug):
    """
    Run ONCE, right after Reload. Checks that every row in the old
    asados.db also exists in the group's file — i.e. that nothing was
    written to the old file in the gap between copying it and Reloading.

    Checks by ID ("is every source id present in the group file?")
    rather than by count, because the group file is allowed to have
    MORE rows by now (people may already be using the new version).
    It is only meaningful soon after the migration: once v2 has been in
    use for a while, a legitimate delete would show up here as
    "missing" too.
    """
    target_path = group_db_path(slug, groups_dir)
    print(f"Verify: every row of {source_path} present in {target_path}?")
    print("=" * 60)
    if not (os.path.exists(source_path) and os.path.exists(target_path)):
        print("Both files must exist to verify. Nothing checked.")
        return 1

    conn = sqlite3.connect(target_path)
    try:
        conn.execute("ATTACH DATABASE ? AS src", (source_path,))
        missing_total = 0
        for table in GROUP_TABLES:
            if not (table_exists(conn, table, "src") and table_exists(conn, table, "main")):
                print(f"{table:<24} n/a")
                continue
            missing = conn.execute(
                f"SELECT COUNT(*) FROM (SELECT id FROM src.{table} EXCEPT SELECT id FROM main.{table})"
            ).fetchone()[0]
            missing_total += missing
            print(f"{table:<24} {'ok' if missing == 0 else f'*** {missing} row(s) MISSING ***'}")
    finally:
        conn.close()

    print("-" * 60)
    if missing_total == 0:
        print("Verify OK: nothing was written to the old database after the copy.")
        return 0
    print("Something was saved to the OLD database between the migration and the Reload.")
    print("Those rows are NOT in the group yet. Don't re-run the migration — note")
    print("which asados they are (they're in the old file) and re-enter or copy them.")
    return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Move asados.db into the multi-group layout.")
    parser.add_argument("--verify", action="store_true", help="check nothing was missed (run right after Reload)")
    parser.add_argument("--source", default=SOURCE_DATABASE)
    parser.add_argument("--accounts", default=ACCOUNTS_DATABASE)
    parser.add_argument("--groups-dir", default=GROUPS_DIR)
    parser.add_argument("--export-token-file", default=EXPORT_TOKEN_FILE)
    args = parser.parse_args()

    if args.verify:
        sys.exit(verify(args.source, args.accounts, args.groups_dir, DEFAULT_SLUG))
    sys.exit(migrate(args.source, args.accounts, args.groups_dir, args.export_token_file,
                     DEFAULT_SLUG, DEFAULT_NAME))
