# =====================================================================
# accounts.py
# Everything about LOGINS and GROUPS, in one place — used by app.py,
# migrate_to_groups.py, and the account/group scripts.
#
# The model (see accounts_schema.sql for the tables themselves):
#   * accounts.db           — logins, groups, memberships (the registry)
#   * groups/<slug>.db      — one per group, same schema as the old
#                             asados.db (asados, participations, ...)
#
# An ACCOUNT is "can log in" (username + password, in accounts.db).
# A MEMBER is "is part of a group's competition" (a row in that
# group's own `users` table — display name, role, and what every
# participation and activity-log entry points at). A MEMBERSHIP links
# one account to one member of one group.
#
# Why members stayed inside each group's file instead of moving to
# accounts.db with the logins: participations, activity_log and
# locations all have FOREIGN KEYs to users(id), and SQLite only
# enforces a foreign key inside a single file. Moving users out would
# have silently turned every one of those into decoration. Keeping
# them meant the group files kept their exact schema and every query
# in app.py stayed untouched.
#
# This file deliberately does NOT import app.py (same rule as the
# migration scripts): a script that only wants to add a user must never
# be one indirect import away from app-level setup code.
# =====================================================================

import os
import re
import sqlite3
import secrets
from datetime import datetime
from urllib.request import pathname2url

# Relative paths, like every other file this app opens — they resolve
# against the working directory, which the PythonAnywhere WSGI file
# pins with os.chdir() (see CLAUDE.md, "How the live deployment is
# actually wired up").
ACCOUNTS_DATABASE = "accounts.db"
ACCOUNTS_SCHEMA = "accounts_schema.sql"
GROUPS_DIR = "groups"

# A slug is the group's permanent short id AND its database filename,
# so this pattern is a SECURITY BOUNDARY, not tidiness: lowercase
# letters, digits and single hyphens only — no dots, no slashes, no
# backslashes — so a slug can never be "../accounts" or anything else
# that points outside groups/. group_db_path() checks it every time a
# path is built, not just when a group is created, so even a slug that
# somehow got into the database by hand can't escape.
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

VALID_ROLES = ("admin", "normal")


def now_timestamp():
    """Same 'YYYY-MM-DD HH:MM:SS' format as activity_log.now_timestamp().
    Duplicated (two lines) rather than imported, so this module stays
    free of any app-side import."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def generate_export_token():
    """Same strength as the old export_token.txt (24 random bytes, hex)."""
    return secrets.token_hex(24)


# ---------------------------------------------------------------------
# OPENING DATABASES
# ---------------------------------------------------------------------
def connect_existing(path):
    """
    Opens a database file that MUST already exist, and refuses to
    create one.

    Plain sqlite3.connect("x.db") silently CREATES an empty x.db if it
    isn't there. For a single-file app that was a nuisance; with one
    file per group it would be a real hazard — a mistyped path, a
    missing migration, or the wrong working directory would quietly
    give someone an empty group instead of an error, and their next
    asado would be saved into that stray file. "mode=rw" in an SQLite
    URI means read-write but never create; the explicit exists() check
    in front of it is only there to give a readable message instead of
    SQLite's own "unable to open database file".
    """
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Database not found: '{path}'. If this is a fresh setup or a "
            f"new deploy, run migrate_to_groups.py first (see README)."
        )
    # pathname2url turns a filesystem path into the URI form SQLite
    # expects, on both Windows ("D:\x.db" -> "///D:/x.db") and Linux.
    uri = "file:" + pathname2url(os.path.abspath(path)) + "?mode=rw"
    conn = sqlite3.connect(uri, uri=True)
    # Rows behave like dicts (row["name"]), as everywhere else in the app.
    conn.row_factory = sqlite3.Row
    # SQLite ignores FOREIGN KEY declarations unless told otherwise, on
    # every single connection — see get_db() in app.py for the longer
    # explanation. Both kinds of database rely on it.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def apply_accounts_schema(conn, schema_path=ACCOUNTS_SCHEMA):
    """Runs accounts_schema.sql. Safe on a database that already holds
    real logins: that file is IF NOT EXISTS throughout and never drops
    anything (unlike schema.sql — never confuse the two)."""
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())


def is_valid_slug(slug):
    return bool(slug) and SLUG_PATTERN.match(slug) is not None


def group_db_path(slug, groups_dir=GROUPS_DIR):
    """
    The ONE function that turns a group into a filename. Everything
    that opens a group database goes through here — never build
    "groups/" + something by hand anywhere else.

    The file is derived from the slug instead of being stored as its own
    column, so the registry can't end up saying one thing while the
    filename says another.
    """
    if not is_valid_slug(slug):
        raise ValueError(f"Invalid group slug: {slug!r}")
    return os.path.join(groups_dir, f"{slug}.db")


# ---------------------------------------------------------------------
# WHICH FILES EXIST — for scripts that work on every group at once
# ---------------------------------------------------------------------
# The single database file of v1.x. Only still referenced so the
# schema migrations can run on it during the ONE deploy that converts
# it (they run before migrate_to_groups.py), and by that migration.
LEGACY_DATABASE = "asados.db"


def registered_group_paths(accounts_path=ACCOUNTS_DATABASE, groups_dir=GROUPS_DIR):
    """
    [(slug, path)] for every group in the registry, oldest first.

    The REGISTRY is the authority on what counts as a group, not a
    directory listing of groups/: a stray or half-made file in that
    folder (a manual copy, a backup someone dropped there) isn't a
    group, and a migration or backup run must not quietly treat it as
    one — nor skip a registered group whose file has gone missing,
    which is why a missing file is an error here, not a skip.
    """
    conn = connect_existing(accounts_path)
    try:
        slugs = [r["slug"] for r in conn.execute("SELECT slug FROM asado_groups ORDER BY id")]
    finally:
        conn.close()
    paths = [(slug, group_db_path(slug, groups_dir)) for slug in slugs]
    missing = [p for _, p in paths if not os.path.exists(p)]
    if missing:
        raise FileNotFoundError(f"Registered group database(s) missing: {', '.join(missing)}")
    return paths


def migration_targets(cli_args, accounts_path=ACCOUNTS_DATABASE, groups_dir=GROUPS_DIR,
                      legacy_path=LEGACY_DATABASE):
    """
    Which database file(s) a schema migration should run on:
      * paths given on the command line -> exactly those (for testing
        against an isolated copy, as before);
      * otherwise, if accounts.db exists (v2.0+) -> EVERY registered
        group, so one command keeps all groups on the same schema;
      * otherwise, if the old asados.db exists (the v2.0 deploy itself,
        where the schema migrations run before migrate_to_groups.py)
        -> just that file;
      * otherwise nothing (a brand-new checkout).
    Every migration must reach every group: a group left on an older
    schema would break the moment the new code runs against it.
    """
    if cli_args:
        return list(cli_args)
    if os.path.exists(accounts_path):
        return [path for _, path in registered_group_paths(accounts_path, groups_dir)]
    if os.path.exists(legacy_path):
        return [legacy_path]
    return []


# ---------------------------------------------------------------------
# LOOKUPS
# ---------------------------------------------------------------------
def find_account_by_username(accounts_db, username):
    # The column is COLLATE NOCASE, so this "=" is case-insensitive too.
    return accounts_db.execute(
        "SELECT id, username, password_hash FROM accounts WHERE username = ?",
        (username,),
    ).fetchone()


def resolve_membership(accounts_db, account_id):
    """
    Which group (and which member of it) is this account using right now?
    Returns (group_row, member_id), or (None, None) if the account isn't
    in any group.

    THIS IS THE ONE PLACE "which group am I in?" is decided. Today the
    rule is "an account belongs to exactly one group", so it simply
    returns that one. When accounts can belong to several groups, this
    is where a chosen group (from a switcher, or from the URL) gets
    picked instead — and nothing else in the app has to change, because
    every route asks app.py's current_group(), which is filled from here.

    ORDER BY memberships.id makes the answer deterministic even if an
    account somehow gained a second membership before multi-group
    support exists: it keeps using the group it joined first.
    """
    row = accounts_db.execute(
        """
        SELECT asado_groups.id, asado_groups.slug, asado_groups.name,
               memberships.member_id
        FROM memberships
        JOIN asado_groups ON asado_groups.id = memberships.group_id
        WHERE memberships.account_id = ?
        ORDER BY memberships.id
        LIMIT 1
        """,
        (account_id,),
    ).fetchone()
    if row is None:
        return None, None
    return row, row["member_id"]


def find_group_by_slug(accounts_db, slug):
    return accounts_db.execute(
        "SELECT id, slug, name, export_token FROM asado_groups WHERE slug = ?", (slug,)
    ).fetchone()


def find_group_by_export_token(accounts_db, submitted):
    """
    For the no-login CSV export: which group (if any) does this token
    belong to?

    Compares against EVERY group with secrets.compare_digest() rather
    than "WHERE export_token = ?" — the same constant-time comparison
    the single-token version used (see the export route in app.py for
    why), and it keeps going through every group even after a match,
    so the response time says nothing about which group matched or how
    close a guess was. A loop over a handful of groups costs nothing.
    """
    match = None
    if not submitted:
        return None
    for row in accounts_db.execute("SELECT id, slug, name, export_token FROM asado_groups"):
        if secrets.compare_digest(submitted, row["export_token"]):
            match = row
    return match


# ---------------------------------------------------------------------
# CREATING AND REMOVING MEMBERS (account + member row + membership)
# ---------------------------------------------------------------------
# These write to TWO database files, which can't share one transaction
# here (the group connection is app.py's per-request one). So each step
# commits, and a failure in a later step UNDOES the earlier ones
# ("compensation"). The order is chosen so that if the process died
# between two steps, what's left over is harmless:
#   - an account with no membership can't get past login (it's "not in
#     any group"), and
#   - a member row with no account is just a member who can't log in,
#     exactly like the group's history would show anyway.
# Neither can expose another group's data.

def create_member_account(accounts_db, group_db, group_id, username, password_hash, name, role):
    """
    Creates a new login that is a member of ONE group: the account in
    accounts.db, the member row in the group's own database, and the
    membership joining them. Returns (account_id, member_id).

    Raises sqlite3.IntegrityError if the username is already taken
    ANYWHERE on the site (usernames are unique across all groups,
    since there is one login page for everyone).
    """
    if role not in VALID_ROLES:
        raise ValueError(f"role must be one of {VALID_ROLES}, got {role!r}")
    created = now_timestamp()

    # Step 1: the account first. Its UNIQUE username is the global
    # "is this name free?" check, so it doubles as a reservation —
    # nothing else is written if the name is taken.
    cur = accounts_db.execute(
        "INSERT INTO accounts (username, password_hash, created_at) VALUES (?, ?, ?)",
        (username, password_hash, created),
    )
    account_id = cur.lastrowid
    accounts_db.commit()

    # Step 2: the member row in the group's own file. password_hash is
    # written as '' on purpose: that column predates accounts.db and is
    # still NOT NULL in every existing group file, but nothing reads it
    # any more — the real hash lives only in accounts.db (see schema.sql).
    try:
        cur = group_db.execute(
            "INSERT INTO users (username, password_hash, name, role) VALUES (?, '', ?, ?)",
            (username, name, role),
        )
        member_id = cur.lastrowid
        group_db.commit()
    except Exception:
        group_db.rollback()
        accounts_db.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        accounts_db.commit()
        raise

    # Step 3: the link between them.
    try:
        accounts_db.execute(
            "INSERT INTO memberships (account_id, group_id, member_id, created_at) VALUES (?, ?, ?, ?)",
            (account_id, group_id, member_id, created),
        )
        accounts_db.commit()
    except Exception:
        accounts_db.rollback()
        group_db.execute("DELETE FROM users WHERE id = ?", (member_id,))
        group_db.commit()
        accounts_db.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        accounts_db.commit()
        raise

    return account_id, member_id


def delete_member_account(accounts_db, group_db, group_id, member_id):
    """
    Removes a member from a group: the member row, the membership, and
    the account itself if it isn't in any other group.

    The CALLER is responsible for refusing first if the member has
    participations (see delete_user_route in app.py) — this function
    just does the removal. The member row goes first: if it can't be
    deleted (a foreign key still points at it), nothing else has been
    touched yet.
    """
    group_db.execute("DELETE FROM users WHERE id = ?", (member_id,))
    group_db.commit()

    membership = accounts_db.execute(
        "SELECT id, account_id FROM memberships WHERE group_id = ? AND member_id = ?",
        (group_id, member_id),
    ).fetchone()
    if membership is None:
        return  # a member with no login (none exist yet, but nothing to undo)

    accounts_db.execute("DELETE FROM memberships WHERE id = ?", (membership["id"],))
    still_elsewhere = accounts_db.execute(
        "SELECT 1 FROM memberships WHERE account_id = ? LIMIT 1", (membership["account_id"],)
    ).fetchone()
    if not still_elsewhere:
        accounts_db.execute("DELETE FROM accounts WHERE id = ?", (membership["account_id"],))
    accounts_db.commit()
