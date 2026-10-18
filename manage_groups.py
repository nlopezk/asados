# =====================================================================
# manage_groups.py
# Command-line tool for the SITE OWNER (whoever has terminal access) to
# manage groups. There is no web page for this yet on purpose: for now,
# new groups are created by hand, and having a terminal on the server
# is what makes you the one allowed to do it.
#
# USAGE (from the project folder):
#   python manage_groups.py create <slug> "<Group name>" <admin_username> <admin_password> "<Admin display name>"
#   python manage_groups.py list
#   python manage_groups.py rename <slug> "<New group name>"
#
# Examples:
#   python manage_groups.py create los-del-sur "Los del Sur" pedro "s3cret" "Don Pedro"
#   python manage_groups.py rename parrilla-y-alma "Parrilla & Alma"
#
# <slug> is the group's PERMANENT short id: lowercase letters, digits
# and single hyphens ("los-del-sur"). It names the group's database file
# (groups/<slug>.db), which is why it can never change afterwards. The
# display NAME can be changed any time with `rename`.
#
# The admin you create here is that group's first member; they add
# everyone else from the app's own Configuración page, exactly as
# before. Their username must be unused ANYWHERE on the site.
#
# `list` prints each group's export token — the secret for its Google
# Sheets / Looker Studio link (see README). Treat the output like a
# password: don't paste it anywhere shared.
#
# This replaces the old `python -c "from app import init_db; init_db()"`
# for making a fresh database. The difference that matters: `create`
# REFUSES to touch a file that already exists, so it can never be aimed
# at a group that already holds data. That one-liner could.
#
# Like the migration scripts, this deliberately does NOT import app.py.
# =====================================================================

import os
import sqlite3
import sys

from werkzeug.security import generate_password_hash

from accounts import (
    ACCOUNTS_DATABASE, ACCOUNTS_SCHEMA, GROUPS_DIR, LEGACY_DATABASE,
    apply_accounts_schema, connect_existing, create_member_account,
    find_group_by_slug, generate_export_token, group_db_path, is_valid_slug,
    now_timestamp,
)

HERE = os.path.dirname(os.path.abspath(__file__))
# The fresh-group blueprint. Its DROP TABLE lines are harmless here
# ONLY because `create` runs it against a file it has just checked does
# not exist yet — never point this at anything else.
GROUP_SCHEMA_PATH = os.path.join(HERE, "schema.sql")
ACCOUNTS_SCHEMA_PATH = os.path.join(HERE, ACCOUNTS_SCHEMA)


def open_registry(create_if_missing=False):
    """Opens accounts.db. Only `create` may bring it into existence,
    and only on a genuinely fresh install — if the old asados.db is
    still sitting here unmigrated, creating a registry next to it
    would start a second, empty world beside the real data."""
    if not os.path.exists(ACCOUNTS_DATABASE):
        if not create_if_missing:
            print(f"Error: {ACCOUNTS_DATABASE} not found. Nothing to show yet.")
            sys.exit(1)
        if os.path.exists(LEGACY_DATABASE):
            print(f"Error: {LEGACY_DATABASE} exists but hasn't been migrated yet.")
            print("Run `python migrate_to_groups.py` first, then create new groups.")
            sys.exit(1)
        conn = sqlite3.connect(ACCOUNTS_DATABASE)
        apply_accounts_schema(conn, ACCOUNTS_SCHEMA_PATH)
        conn.commit()
        conn.close()
        print(f"Created a new, empty {ACCOUNTS_DATABASE} (fresh install).")
    return connect_existing(ACCOUNTS_DATABASE)


def create(slug, name, admin_username, admin_password, admin_name):
    name, admin_username, admin_name = name.strip(), admin_username.strip(), admin_name.strip()
    if not is_valid_slug(slug):
        print(f"Error: '{slug}' isn't a valid slug — use lowercase letters, digits and")
        print("single hyphens only, e.g. 'los-del-sur'.")
        return 1
    if not (name and admin_username and admin_password and admin_name):
        print("Error: group name, admin username, password and display name are all required.")
        return 1

    accounts_db = open_registry(create_if_missing=True)
    path = group_db_path(slug, GROUPS_DIR)
    try:
        # --- every check BEFORE anything is written --------------------
        if find_group_by_slug(accounts_db, slug):
            print(f"Error: a group with slug '{slug}' already exists.")
            return 1
        if os.path.exists(path):
            print(f"Error: {path} already exists but isn't a registered group.")
            print("Not touching it — it may hold data. Move it aside first.")
            return 1
        if accounts_db.execute("SELECT 1 FROM accounts WHERE username = ?", (admin_username,)).fetchone():
            print(f"Error: the username '{admin_username}' is already taken on this site.")
            return 1

        # --- 1. the group's own, empty database ------------------------
        os.makedirs(GROUPS_DIR, exist_ok=True)
        group_db = sqlite3.connect(path)
        try:
            with open(GROUP_SCHEMA_PATH, "r", encoding="utf-8") as f:
                group_db.executescript(f.read())
            group_db.commit()
        finally:
            group_db.close()

        # --- 2. register it, 3. its first admin --------------------------
        # If either step fails, undo everything so a retry starts clean
        # (same "never leave half a group behind" rule as the migration).
        group_id = None
        try:
            cur = accounts_db.execute(
                "INSERT INTO asado_groups (slug, name, export_token, created_at) VALUES (?, ?, ?, ?)",
                (slug, name, generate_export_token(), now_timestamp()),
            )
            group_id = cur.lastrowid
            accounts_db.commit()

            group_db = connect_existing(path)
            try:
                create_member_account(
                    accounts_db, group_db, group_id, admin_username,
                    generate_password_hash(admin_password), admin_name, "admin",
                )
            finally:
                group_db.close()
        except Exception as e:
            accounts_db.rollback()
            if group_id is not None:
                accounts_db.execute("DELETE FROM asado_groups WHERE id = ?", (group_id,))
                accounts_db.commit()
            os.remove(path)
            print(f"Error: couldn't create the group, nothing was kept: {e}")
            return 1
    finally:
        accounts_db.close()

    print(f"Group '{name}' created: {path}")
    print(f"First admin: {admin_username} ({admin_name}). They can now log in and add")
    print("the rest of the group from Configuración.")
    print("Run `python manage_groups.py list` to see its export token.")
    return 0


def list_groups():
    accounts_db = open_registry()
    try:
        rows = accounts_db.execute("""
            SELECT asado_groups.slug, asado_groups.name, asado_groups.export_token,
                   asado_groups.created_at, COUNT(memberships.id) AS logins
            FROM asado_groups
            LEFT JOIN memberships ON memberships.group_id = asado_groups.id
            GROUP BY asado_groups.id
            ORDER BY asado_groups.id
        """).fetchall()
    finally:
        accounts_db.close()

    if not rows:
        print("No groups yet.")
        return 0
    for r in rows:
        path = group_db_path(r["slug"], GROUPS_DIR)
        asados = "FILE MISSING"
        if os.path.exists(path):
            conn = connect_existing(path)
            asados = conn.execute("SELECT COUNT(*) FROM asados").fetchone()[0]
            conn.close()
        print(f"{r['name']}  [{r['slug']}]")
        print(f"  created {r['created_at']}, {r['logins']} login(s), {asados} asado(s)")
        print(f"  database:     {path}")
        print(f"  export token: {r['export_token']}")
        print()
    return 0


def rename(slug, new_name):
    new_name = new_name.strip()
    if not new_name:
        print("Error: the new name can't be empty.")
        return 1
    accounts_db = open_registry()
    try:
        cur = accounts_db.execute("UPDATE asado_groups SET name = ? WHERE slug = ?", (new_name, slug))
        accounts_db.commit()
    finally:
        accounts_db.close()
    if cur.rowcount == 0:
        print(f"Error: no group with slug '{slug}'.")
        return 1
    print(f"Group [{slug}] is now called '{new_name}'. (Its slug and database file are unchanged.)")
    return 0


USAGE = """Usage:
  python manage_groups.py create <slug> "<Group name>" <admin_username> <admin_password> "<Admin display name>"
  python manage_groups.py list
  python manage_groups.py rename <slug> "<New group name>\""""

if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["create"] and len(args) == 6:
        sys.exit(create(*args[1:]))
    if args == ["list"]:
        sys.exit(list_groups())
    if args[:1] == ["rename"] and len(args) == 3:
        sys.exit(rename(args[1], args[2]))
    print(USAGE)
    sys.exit(1)
