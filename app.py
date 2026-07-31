# =====================================================================
# app.py
# This is the "brain" of our web app. It uses Flask to:
#   1. Define URLs ("routes") that respond when someone visits them.
#   2. Talk to the SQLite database to read/write asado data.
#   3. Render HTML templates (in the templates/ folder) to show pages.
#
# Flask concept in one sentence: every function decorated with
# @app.route(...) runs when a browser visits that URL.
# =====================================================================

import sqlite3                     # Python's built-in library to talk to SQLite databases
import os
import functools
from flask import Flask, render_template, request, redirect, url_for, g, jsonify, session
from werkzeug.security import check_password_hash, generate_password_hash
from config import (
    calculate_points, TIPO_CARNE_WEIGHTS, COCCION_WEIGHTS, SUPERFICIE_WEIGHTS,
    LOCAL_WEIGHTS, ROL_WEIGHTS, FORMULA, VARIABLE_LABELS,
)

DATABASE = "asados.db"  # the SQLite database is just a single file on disk

app = Flask(__name__)  # __name__ tells Flask where this file lives, for finding templates/static

# ---------------------------------------------------------------------
# SECRET KEY (needed for login sessions)
# ---------------------------------------------------------------------
# Flask uses this key to cryptographically SIGN the session cookie it
# gives each visitor's browser — this is what lets Flask trust that a
# returning cookie hasn't been tampered with, which is how it knows
# "this browser is still logged in as user X" on every later request.
#
# We generate a random key the FIRST time the app ever runs, and save
# it to a local file (secret_key.txt, which is in .gitignore — it must
# NEVER be committed to GitHub, since anyone with it could forge login
# sessions). Every time the app starts after that, it reuses the same
# saved key, so people don't get logged out every time you restart it.
SECRET_KEY_FILE = "secret_key.txt"

if os.path.exists(SECRET_KEY_FILE):
    with open(SECRET_KEY_FILE, "r") as f:
        app.secret_key = f.read().strip()
else:
    # os.urandom(24) generates 24 random bytes — cryptographically
    # unpredictable, good for a secret key. .hex() turns it into a
    # readable string of letters/numbers we can save to a text file.
    new_key = os.urandom(24).hex()
    with open(SECRET_KEY_FILE, "w") as f:
        f.write(new_key)
    app.secret_key = new_key


# ---------------------------------------------------------------------
# DATABASE CONNECTION HELPERS
# ---------------------------------------------------------------------
def get_db():
    """
    Returns a connection to the SQLite database.
    We store it on Flask's special 'g' object, which is a per-request
    storage box — this means we only open ONE connection per web
    request, instead of opening a new one every time we need data.
    """
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        # This makes query results behave like dictionaries (row["date"])
        # instead of plain tuples (row[1]) — much easier to read in code.
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    """Flask automatically calls this after every request finishes,
    so we can cleanly close the database connection."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Reads schema.sql and runs it to (re)create empty tables.
    We'll call this once manually to set up the database file."""
    with app.app_context():
        db = get_db()
        with open("schema.sql", "r") as f:
            db.executescript(f.read())
        db.commit()


# ---------------------------------------------------------------------
# AUTHENTICATION HELPERS
# ---------------------------------------------------------------------

def login_required(view_function):
    """
    A DECORATOR: a function that wraps another function to add behavior
    around it. Putting @login_required above a route means "run this
    check before letting anyone reach the actual page."

    functools.wraps() preserves the original function's name/metadata,
    which Flask needs internally to tell routes apart — without it,
    Flask would get confused if you used @login_required on more than
    one route (a common gotcha worth knowing about).
    """
    @functools.wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if session.get("user_id") is None:
            # Not logged in — send them to the login page. We also
            # remember where they were TRYING to go (request.path) as a
            # "next" URL, so login() can send them back there afterward.
            return redirect(url_for("login", next=request.path))
        return view_function(*args, **kwargs)
    return wrapped_view


def admin_required(view_function):
    """
    Like @login_required, but ALSO requires the logged-in user's role
    to be "admin" (see the users.role column in schema.sql). Used for
    the account-management actions on the Configuración page (creating
    and deleting other users) — normal users can only reach their own
    profile fields there.
    """
    @functools.wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("login", next=request.path))
        if g.role != "admin":
            return "Acceso denegado: se requieren permisos de administrador.", 403
        return view_function(*args, **kwargs)
    return wrapped_view


@app.before_request
def load_logged_in_user():
    """
    Runs before EVERY request. If the session says someone is logged
    in, we look up their username/name/role here once and stash it on
    Flask's 'g' object — so every template can display "logged in as
    ___" (and check admin-only UI) without each route having to
    re-fetch it individually.
    """
    user_id = session.get("user_id")
    if user_id is None:
        g.username = None
        g.name = None
        g.role = None
    else:
        db = get_db()
        user = db.execute(
            "SELECT username, name, role FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        g.username = user["username"] if user else None
        g.name = user["name"] if user else None
        g.role = user["role"] if user else None


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    LOGIN PAGE.
    GET  -> show the login form.
    POST -> check the submitted username/password against the database.
    """
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        db = get_db()
        user = db.execute(
            "SELECT id, password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()

        # check_password_hash() re-hashes the SUBMITTED password using
        # the same method, and compares it to the STORED hash. It
        # returns True only if they match — we never decrypt or see
        # the original stored password, because it was never stored.
        if user is not None and check_password_hash(user["password_hash"], password):
            # session is a special Flask dictionary that persists
            # across requests for one browser, via a signed cookie.
            # Storing just the user's id here (not their password!) is
            # standard practice — it's like a coat-check ticket, not
            # the coat itself.
            session.clear()
            session["user_id"] = user["id"]

            # If login_required redirected them here with a "next"
            # parameter, send them back to whatever page they wanted.
            # Otherwise, default to the home page.
            next_url = request.args.get("next") or url_for("index")
            return redirect(next_url)

        # Wrong username or password: show the form again with an error.
        return render_template("login.html", error="Usuario o contraseña incorrectos.")

    return render_template("login.html", error=None)


@app.route("/logout")
def logout():
    """Clears the session (logs the user out) and returns to login."""
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------
# CONFIGURACIÓN (profile settings + admin user management)
# ---------------------------------------------------------------------
# Every logged-in user can change their own name/password here. Admins
# (users.role == "admin") additionally see a user-management panel to
# create or delete accounts, replacing the terminal-only create_user.py
# script for day-to-day use (that script remains the way to create the
# very first admin account, since this page requires being logged in
# already).
#
# "Success"/"error" feedback is passed back as query-string params after
# a redirect (?success=...&error=...), the same lightweight pattern used
# by login.html's error message — no flash-message system needed yet.

@app.route("/config")
@login_required
def config_page():
    db = get_db()
    users = None
    if g.role == "admin":
        # Only fetch the full user list when it'll actually be shown —
        # normal users only ever see their own profile fields.
        users = db.execute(
            "SELECT id, username, name, role FROM users ORDER BY username"
        ).fetchall()

    return render_template(
        "config.html",
        users=users,
        success=request.args.get("success"),
        error=request.args.get("error"),
    )


@app.route("/config/profile", methods=["POST"])
@login_required
def update_profile():
    """Lets ANY logged-in user change their own display name and,
    optionally, their password (leaving the password field blank keeps
    the current one)."""
    db = get_db()
    name = request.form.get("name", "").strip()
    new_password = request.form.get("new_password", "")

    if not name:
        return redirect(url_for("config_page", error="El nombre no puede estar vacío."))

    if new_password:
        password_hash = generate_password_hash(new_password)
        db.execute(
            "UPDATE users SET name = ?, password_hash = ? WHERE id = ?",
            (name, password_hash, session["user_id"]),
        )
    else:
        db.execute("UPDATE users SET name = ? WHERE id = ?", (name, session["user_id"]))
    db.commit()

    return redirect(url_for("config_page", success="Perfil actualizado."))


@app.route("/config/users/create", methods=["POST"])
@admin_required
def create_user_route():
    """Admin-only: create a new account without needing terminal access
    to create_user.py."""
    db = get_db()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    name = request.form.get("name", "").strip()
    role = request.form.get("role", "normal")

    if not username or not password or not name:
        return redirect(url_for("config_page", error="Usuario, contraseña y nombre son obligatorios."))
    if role not in ("admin", "normal"):
        role = "normal"

    password_hash = generate_password_hash(password)
    try:
        db.execute(
            "INSERT INTO users (username, password_hash, name, role) VALUES (?, ?, ?, ?)",
            (username, password_hash, name, role),
        )
        db.commit()
    except sqlite3.IntegrityError:
        # users.username is UNIQUE — this fires if that name is taken.
        return redirect(url_for("config_page", error=f"El usuario '{username}' ya existe."))

    return redirect(url_for("config_page", success=f"Usuario '{username}' creado."))


@app.route("/config/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user_route(user_id):
    """Admin-only: remove an account. Blocked in two cases to avoid
    footguns: deleting yourself (would lock you out with no other admin
    action possible from the UI), and deleting someone who already has
    asado participations recorded (schema.sql has no ON DELETE CASCADE,
    so those rows would silently become orphaned and vanish from that
    asado's participant list instead of erroring)."""
    db = get_db()

    if user_id == session["user_id"]:
        return redirect(url_for("config_page", error="No puedes eliminar tu propia cuenta."))

    has_participations = db.execute(
        "SELECT 1 FROM participations WHERE user_id = ? LIMIT 1", (user_id,)
    ).fetchone()
    if has_participations:
        return redirect(url_for(
            "config_page",
            error="No se puede eliminar: este usuario tiene asados registrados.",
        ))

    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    return redirect(url_for("config_page", success="Usuario eliminado."))


# ---------------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------------

@app.route("/")
@login_required
def index():
    """
    HOME PAGE: lists every asado, most recent first, along with a quick
    summary (who participated and how many points they got).
    """
    db = get_db()

    # Fetch all asados, newest date first.
    asados = db.execute(
        "SELECT * FROM asados ORDER BY date DESC"
    ).fetchall()

    # For each asado, also fetch its participants (a small extra query
    # per asado — totally fine for Phase 1's scale; we can optimize
    # with a JOIN later if the dataset grows).
    asados_with_participants = []
    for asado in asados:
        participants = db.execute(
            """
            SELECT users.username, participations.rol, participations.points
            FROM participations
            JOIN users ON participations.user_id = users.id
            WHERE participations.asado_id = ?
            """,
            (asado["id"],),
        ).fetchall()
        asados_with_participants.append({"asado": asado, "participants": participants})

    return render_template("index.html", asados=asados_with_participants)


@app.route("/api/points")
def api_points():
    """
    JSON API used ONLY by the live points preview in new_asado.html.
    The browser sends the current form selections as URL query
    parameters, and this route calls the EXACT SAME calculate_points()
    function that saves real data — so the preview can never drift out
    of sync, no matter how the formula changes later (new weights, new
    coefficients, or a completely restructured equation).
    """
    tipo_carne = request.args.get("tipo_carne", "")
    coccion = request.args.get("coccion", "")
    superficie = request.args.get("superficie", "")
    local = request.args.get("local", "")
    rol = request.args.get("rol", "")

    points = calculate_points(tipo_carne, coccion, superficie, local, rol)
    return jsonify({"points": points})


@app.route("/asado/new", methods=["GET", "POST"])
@login_required
def new_asado():
    """
    ADD ASADO PAGE.
    GET  -> just show the empty form.
    POST -> the form was submitted; save the new asado + its participants.
    """
    db = get_db()

    if request.method == "POST":
        # --- Step 1: read the shared asado fields from the submitted form ---
        # request.form is a dictionary-like object holding whatever the
        # <input name="..."> fields sent.
        date = request.form["date"]
        nombre = request.form["nombre"]
        description = request.form.get("description", "")  # .get() with default = optional field
        tipo_carne = request.form["tipo_carne"]
        coccion = request.form["coccion"]
        superficie = request.form["superficie"]
        local = request.form["local"]
        location = request.form.get("location", "")
        # These are hidden inputs, filled in by the map-picker JavaScript
        # (see new_asado.html). type=float means Flask converts the text
        # to a Python float automatically; if empty, it becomes None.
        latitude = request.form.get("latitude", type=float)
        longitude = request.form.get("longitude", type=float)
        people = request.form.get("people", type=int)
        total_weight = request.form.get("total_weight", type=float)

        # --- Step 2: insert the asado row and get its new auto-generated id ---
        cursor = db.execute(
            """
            INSERT INTO asados
                (date, nombre, description, tipo_carne, coccion,
                 superficie, local, location, latitude, longitude, people, total_weight)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (date, nombre, description, tipo_carne, coccion,
             superficie, local, location, latitude, longitude, people, total_weight),
        )
        asado_id = cursor.lastrowid  # the id SQLite just assigned to this new row

        # --- Step 3: handle participants ---
        # The form now sends a REGISTERED user's id (from a dropdown,
        # not free-typed text) alongside their Rol for this asado.
        # This matches your decision: only registered accounts can be
        # participants, no more auto-creating users on the fly.
        user_ids = request.form.getlist("participant_user_id")
        roles = request.form.getlist("participant_rol")

        for user_id_str, rol in zip(user_ids, roles):
            if not user_id_str:
                continue  # skip any row where nothing was selected

            user_id = int(user_id_str)

            # Safety check: confirm this id really matches an existing
            # user, in case of any tampering with the submitted form
            # (e.g. someone editing the HTML before submitting).
            user_row = db.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
            if user_row is None:
                continue  # silently skip an invalid id rather than crashing

            # Calculate this participant's points using our formula from config.py.
            # Rol is per-participant, so points can differ between people
            # even though they were at the SAME asado.
            points = calculate_points(tipo_carne, coccion, superficie, local, rol)

            db.execute(
                """
                INSERT INTO participations (asado_id, user_id, rol, points)
                VALUES (?, ?, ?, ?)
                """,
                (asado_id, user_id, rol, points),
            )

        db.commit()  # save everything permanently to the database file
        return redirect(url_for("index"))  # redirect back to the home page

    # GET request: just show the blank form.
    # We pass the category dictionaries so the HTML can build dropdowns
    # from them, instead of hardcoding options in the template too.
    #
    # We ALSO pass the full weight dictionaries as a single "weights"
    # object. The template will convert this to JSON with Jinja's
    # |tojson filter, so JavaScript in the browser can read the exact
    # same numbers Python uses — letting us show a LIVE points preview
    # without needing to contact the server on every dropdown change.
    weights = {
        "tipo_carne": TIPO_CARNE_WEIGHTS,
        "coccion": COCCION_WEIGHTS,
        "superficie": SUPERFICIE_WEIGHTS,
        "local": LOCAL_WEIGHTS,
        "rol": ROL_WEIGHTS,
        "formula": FORMULA,  # the literal formula text, read directly by the JS preview
        "labels": VARIABLE_LABELS,  # human-readable names for the formula's variables
    }

    # All registered users, for the participant dropdowns — participants
    # must now be existing accounts, selected by id, not free-typed names.
    registered_users = db.execute("SELECT id, username FROM users ORDER BY username").fetchall()

    return render_template(
        "new_asado.html",
        tipo_carne_options=TIPO_CARNE_WEIGHTS.keys(),
        coccion_options=COCCION_WEIGHTS.keys(),
        superficie_options=SUPERFICIE_WEIGHTS.keys(),
        local_options=LOCAL_WEIGHTS.keys(),
        rol_options=ROL_WEIGHTS.keys(),
        weights=weights,
        registered_users=registered_users,
    )


@app.route("/asado/<int:asado_id>")
@login_required
def view_asado(asado_id):
    """DETAIL PAGE for a single asado, showing all its info + participants."""
    db = get_db()

    asado = db.execute(
        "SELECT * FROM asados WHERE id = ?", (asado_id,)
    ).fetchone()

    participants = db.execute(
        """
        SELECT users.username, participations.rol, participations.points
        FROM participations
        JOIN users ON participations.user_id = users.id
        WHERE participations.asado_id = ?
        """,
        (asado_id,),
    ).fetchall()

    return render_template("view_asado.html", asado=asado, participants=participants)


# ---------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------
if __name__ == "__main__":
    # debug=True auto-reloads the server when you edit code, and shows
    # detailed error pages — great for development, turn OFF in production.
    app.run(debug=True, host="0.0.0.0", port=5000)
