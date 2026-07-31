# =====================================================================
# create_user.py
# A small command-line script (NOT a web page) for creating accounts.
# You run this yourself from the terminal whenever you want to add
# someone to the group — there's no public sign-up page, matching your
# choice to manage accounts manually. (Admins can also create accounts
# from the app's Configuración page once at least one admin exists —
# this script is how you create that FIRST admin account.)
#
# USAGE (from the project folder, with the database already created):
#   python create_user.py <username> <password> <name> [role]
#   - <name> is the display name shown around the app (e.g. "Don Nicola"),
#     separate from the login <username>.
#   - [role] is "admin" or "normal" (default: "normal" if omitted).
#
# Example:
#   python create_user.py nico "mySecretPass123" "Don Nicola" admin
# =====================================================================

import sys
import sqlite3
from werkzeug.security import generate_password_hash

DATABASE = "asados.db"
VALID_ROLES = ("admin", "normal")


def create_user(username, password, name, role="normal"):
    if role not in VALID_ROLES:
        print(f"Error: role must be one of {VALID_ROLES}, got '{role}'.")
        return

    # generate_password_hash() turns the plain-text password into a
    # scrambled, one-way "hash" — the actual password is never stored
    # anywhere, only this hash. Flask/Werkzeug picks a strong, modern
    # hashing algorithm automatically.
    password_hash = generate_password_hash(password)

    conn = sqlite3.connect(DATABASE)
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, name, role) VALUES (?, ?, ?, ?)",
            (username, password_hash, name, role),
        )
        conn.commit()
        print(f"User '{username}' ({name}, role={role}) created successfully.")
    except sqlite3.IntegrityError:
        # This fires if the username already exists (our schema marks
        # username as UNIQUE), so we give a clear message instead of a
        # confusing crash.
        print(f"Error: a user named '{username}' already exists.")
    finally:
        conn.close()


if __name__ == "__main__":
    # sys.argv is the list of command-line arguments. argv[0] is
    # always the script's own name, so real arguments start at argv[1].
    if len(sys.argv) not in (4, 5):
        print("Usage: python create_user.py <username> <password> <name> [role]")
        sys.exit(1)  # non-zero exit code signals "something went wrong"

    args = sys.argv[1:]
    username_arg, password_arg, name_arg = args[0], args[1], args[2]
    role_arg = args[3] if len(args) == 4 else "normal"
    create_user(username_arg, password_arg, name_arg, role_arg)
