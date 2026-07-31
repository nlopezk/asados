# =====================================================================
# create_user.py
# A small command-line script (NOT a web page) for creating accounts.
# You run this yourself from the terminal whenever you want to add
# someone to the group — there's no public sign-up page, matching your
# choice to manage accounts manually.
#
# USAGE (from the project folder, with the database already created):
#   python create_user.py <username> <password>
#
# Example:
#   python create_user.py nico "mySecretPass123"
# =====================================================================

import sys
import sqlite3
from werkzeug.security import generate_password_hash

DATABASE = "asados.db"


def create_user(username, password):
    # generate_password_hash() turns the plain-text password into a
    # scrambled, one-way "hash" — the actual password is never stored
    # anywhere, only this hash. Flask/Werkzeug picks a strong, modern
    # hashing algorithm automatically.
    password_hash = generate_password_hash(password)

    conn = sqlite3.connect(DATABASE)
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )
        conn.commit()
        print(f"User '{username}' created successfully.")
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
    if len(sys.argv) != 3:
        print("Usage: python create_user.py <username> <password>")
        sys.exit(1)  # non-zero exit code signals "something went wrong"

    _, username_arg, password_arg = sys.argv
    create_user(username_arg, password_arg)
