# =====================================================================
# create_user.py
# A small command-line script (NOT a web page) for creating accounts.
# You run this yourself from the terminal whenever you want to add
# someone to a group — there's no public sign-up page, matching your
# choice to manage accounts manually. (A group's admins can also create
# accounts from the app's Configuración page — usually the easier way.
# A group's FIRST admin is created together with the group itself, by
# `manage_groups.py create`.)
#
# USAGE (from the project folder, once the group exists):
#   python create_user.py <group-slug> <username> <password> <name> [role]
#   - <group-slug> is the group's short id, e.g. "parrilla-y-alma"
#     (`python manage_groups.py list` shows them all).
#   - <name> is the display name shown around the app (e.g. "Don Nicola"),
#     separate from the login <username>.
#   - [role] is "admin" or "normal" (default: "normal" if omitted) —
#     the role WITHIN THAT GROUP only.
#
# Example:
#   python create_user.py parrilla-y-alma nico "mySecretPass123" "Don Nicola" admin
#
# Since v2.0 a "user" is three linked rows (see accounts.py): a LOGIN in
# accounts.db, a MEMBER in the group's own database, and the MEMBERSHIP
# linking them. create_member_account() writes all three — and undoes
# the earlier ones if a later one fails — so this script and the
# Configuración page can never create users in two different ways.
# =====================================================================

import sys
import sqlite3
from werkzeug.security import generate_password_hash

from accounts import (
    ACCOUNTS_DATABASE, GROUPS_DIR, VALID_ROLES,
    connect_existing, create_member_account, find_group_by_slug, group_db_path,
)


def create_user(group_slug, username, password, name, role="normal"):
    if role not in VALID_ROLES:
        print(f"Error: role must be one of {VALID_ROLES}, got '{role}'.")
        return 1

    accounts_db = connect_existing(ACCOUNTS_DATABASE)
    try:
        group = find_group_by_slug(accounts_db, group_slug)
        if group is None:
            print(f"Error: no group with slug '{group_slug}'. "
                  f"`python manage_groups.py list` shows the existing ones.")
            return 1

        group_db = connect_existing(group_db_path(group["slug"], GROUPS_DIR))
        try:
            # generate_password_hash() turns the plain-text password into
            # a scrambled, one-way "hash" — the actual password is never
            # stored anywhere, only this hash. Flask/Werkzeug picks a
            # strong, modern hashing algorithm automatically.
            create_member_account(
                accounts_db, group_db, group["id"],
                username, generate_password_hash(password), name, role,
            )
        except sqlite3.IntegrityError:
            # Usernames are unique across the whole SITE (any capitalisation),
            # not just within one group — there's one login page for everyone.
            print(f"Error: the username '{username}' is already taken.")
            return 1
        finally:
            group_db.close()
    finally:
        accounts_db.close()

    print(f"User '{username}' ({name}, role={role}) created in '{group['name']}'.")
    return 0


if __name__ == "__main__":
    # sys.argv is the list of command-line arguments. argv[0] is
    # always the script's own name, so real arguments start at argv[1].
    if len(sys.argv) not in (5, 6):
        print("Usage: python create_user.py <group-slug> <username> <password> <name> [role]")
        sys.exit(1)  # non-zero exit code signals "something went wrong"

    args = sys.argv[1:]
    role_arg = args[4] if len(args) == 5 else "normal"
    sys.exit(create_user(args[0], args[1], args[2], args[3], role_arg))
