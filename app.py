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
import csv
import io
import functools
import secrets                     # for generating unguessable CSRF tokens
from flask import Flask, render_template, request, redirect, url_for, g, jsonify, session, Response
from werkzeug.security import check_password_hash, generate_password_hash
from config import (
    calculate_points, get_shared_weights, get_rol_weight, get_tipo_carne_weights,
    TIPO_CARNE_WEIGHTS, COCCION_WEIGHTS, SUPERFICIE_WEIGHTS,
    LOCAL_WEIGHTS, ROL_WEIGHTS, FORMULA, VARIABLE_LABELS,
)
from backup_db import backup_database

DATABASE = "asados.db"  # the SQLite database is just a single file on disk

# How many rows to show per page before showing a "next" arrow, on the
# home page and on Base de Asados respectively. Base de Asados can show
# more per page since each row is much narrower (a spreadsheet line)
# than a full asado card.
INDEX_PAGE_SIZE = 30
BASE_ASADOS_PAGE_SIZE = 100

# For the home page's "Mes" filter dropdown. Kept as a plain number
# (label) rather than a Spanish month name, to save space in the filter
# bar. Values stay zero-padded ("01".."12") on purpose — SQLite's
# strftime('%m', ...) always returns a zero-padded month, so the
# filter's WHERE clause can compare these values directly without any
# extra padding logic.
MESES = [(f"{m:02d}", str(m)) for m in range(1, 13)]


def parse_page_number(value):
    """
    Reads a ?page= query param into a valid page number (an integer,
    at least 1). Falls back to 1 for anything invalid — a missing page
    param, non-numeric text, or a negative/zero number — rather than
    raising an error, since this only affects which page you land on,
    never whether the page loads at all.
    """
    try:
        page = int(value)
    except (TypeError, ValueError):
        return 1
    return page if page >= 1 else 1


# ---------------------------------------------------------------------
# "BASE DE ASADOS" QUERY (spreadsheet-style export)
# ---------------------------------------------------------------------
# ONE ROW PER PARTICIPATION, with that participation's asado/user info
# joined in — NOT one row per asado. An asado with 5 participants
# produces 5 rows here, each repeating that asado's date/nombre/etc.
# This is intentional: it's the flat, "spreadsheet" shape you'd want
# for a CSV export (one line per person-at-an-asado), as opposed to
# index.html's one-card-per-asado view.
#
# LEFT JOIN (not JOIN) in both directions from participations, so a
# participation is never silently dropped even in the edge case its
# linked asado or user row is missing (schema.sql has no ON DELETE
# CASCADE, so this can't currently happen through the app's own UI, but
# a LEFT JOIN costs nothing and is the safer default for an "export
# everything" view).
#
# tipo_carne is the odd one out here: an asado can have MULTIPLE meat
# types (asado_tipo_carne table), but this query's grain is one row per
# PARTICIPATION — so the nested subquery below GROUP_CONCATs every
# selected type for an asado into one "Cordero; Pollo" string FIRST
# (per asado_id), and only THEN that single pre-joined string gets
# LEFT JOINed onto each participation row, same as any other asado-level
# column here. The inner "ORDER BY id" before GROUP_CONCAT keeps the
# types listed in the order they were originally selected/saved, not
# arbitrary — GROUP_CONCAT has no ORDER BY of its own in the SQLite
# version this app targets, so a pre-sorted subquery is the accepted way
# to get consistent ordering out of it.
BASE_ASADOS_QUERY = """
    SELECT
        participations.id AS participation_id,
        participations.asado_id AS asado_id,
        asados.date AS date,
        asados.nombre AS nombre,
        tipos_carne.tipo_carne_list AS tipo_carne,
        asados.tipo_carne_weight AS tipo_carne_weight,
        asados.coccion AS coccion,
        asados.coccion_weight AS coccion_weight,
        asados.superficie AS superficie,
        asados.superficie_weight AS superficie_weight,
        asados.local AS local,
        asados.local_weight AS local_weight,
        asados.location AS location,
        asados.latitude AS latitude,
        asados.longitude AS longitude,
        asados.people AS people,
        asados.total_weight AS total_weight,
        users.username AS username,
        users.name AS name,
        participations.rol AS rol,
        participations.rol_weight AS rol_weight,
        participations.points AS points
    FROM participations
    LEFT JOIN asados ON participations.asado_id = asados.id
    LEFT JOIN users ON participations.user_id = users.id
    LEFT JOIN (
        SELECT asado_id, GROUP_CONCAT(tipo_carne, '; ') AS tipo_carne_list
        FROM (SELECT asado_id, tipo_carne FROM asado_tipo_carne ORDER BY id)
        GROUP BY asado_id
    ) AS tipos_carne ON tipos_carne.asado_id = asados.id
    ORDER BY asados.date DESC, participations.id
"""

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
        # SQLite does NOT enforce FOREIGN KEY constraints by default,
        # even though schema.sql declares them (e.g.
        # participations.user_id REFERENCES users(id)) — that PRAGMA
        # has to be set on every connection, or the constraints are
        # purely decorative. Turning it on here means SQLite itself
        # will now refuse an INSERT/DELETE that would orphan a row,
        # as a backstop alongside the explicit checks the app's own
        # routes already do (like delete_user_route's participation check).
        g.db.execute("PRAGMA foreign_keys = ON")
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


# ---------------------------------------------------------------------
# CSRF PROTECTION (Cross-Site Request Forgery)
# ---------------------------------------------------------------------
# Without this, some OTHER website could embed a hidden form pointing at
# one of our POST routes (e.g. "delete this user", "change my password")
# and auto-submit it — the browser would still attach our session
# cookie, since cookies are sent to whatever domain they belong to
# regardless of which page triggered the request. This app's session
# cookie is Flask's default SameSite=Lax, which already blocks most of
# that on modern browsers, but a real, checked token is the actual fix
# rather than relying only on a cookie default — especially once this
# app is reachable from the open internet (see the Phase 6 deploy goal).
#
# The approach: every session gets ONE random token, stored server-side
# in the session itself. Every template embeds that same token as a
# hidden form field (via the csrf_token() function below). Every POST
# request must send that exact token back — a page from another site
# has no way to read OUR session's token to include it, so its
# auto-submitted form gets rejected.
def ensure_csrf_token():
    """Makes sure the current session has a token, generating one the
    first time a browser shows up. Runs on EVERY request (not just
    form pages) so the token already exists by the time any page with
    a form gets rendered."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)


def validate_csrf_token():
    """Rejects any POST whose submitted csrf_token doesn't match the
    one stored in this browser's session. Runs for every route — POST
    is the only method any of our forms use, so this alone covers
    login, profile updates, user create/delete, and new-asado."""
    if request.method == "POST":
        submitted = request.form.get("csrf_token")
        if not submitted or submitted != session.get("csrf_token"):
            return "Token de seguridad inválido o expirado. Recarga la página e intenta de nuevo.", 400


app.before_request(ensure_csrf_token)
app.before_request(validate_csrf_token)


@app.context_processor
def inject_csrf_token():
    """Makes csrf_token() callable from inside any Jinja template
    (e.g. {{ csrf_token() }}) without every render_template() call
    needing to pass it explicitly."""
    return {"csrf_token": lambda: session.get("csrf_token", "")}


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


def asado_form_context(db):
    """
    The dropdown options + weights (for the live points preview) +
    registered users needed to render templates/_asado_form.html — the
    shared create/edit form used by both new_asado() and view_asado().
    Built in exactly one place so the two routes can never end up
    offering different dropdown options or a different WEIGHTS object
    to their JavaScript.
    """
    return {
        "tipo_carne_options": TIPO_CARNE_WEIGHTS.keys(),
        "coccion_options": COCCION_WEIGHTS.keys(),
        "superficie_options": SUPERFICIE_WEIGHTS.keys(),
        "local_options": LOCAL_WEIGHTS.keys(),
        "rol_options": ROL_WEIGHTS.keys(),
        "weights": {
            "tipo_carne": TIPO_CARNE_WEIGHTS,
            "coccion": COCCION_WEIGHTS,
            "superficie": SUPERFICIE_WEIGHTS,
            "local": LOCAL_WEIGHTS,
            "rol": ROL_WEIGHTS,
            "formula": FORMULA,  # the literal formula text, read directly by the JS preview
            "labels": VARIABLE_LABELS,  # human-readable names for the formula's variables
        },
        # All registered users, for the participant dropdowns —
        # participants must be existing accounts, selected by id, not
        # free-typed names. Ordered/displayed by "name" (the friendly
        # display name), matching how every other page identifies a user.
        "registered_users": db.execute("SELECT id, username, name FROM users ORDER BY name").fetchall(),
    }


# ---------------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------------

@app.route("/")
@login_required
def index():
    """
    HOME PAGE: lists every asado, most recent first, along with a quick
    summary (who participated and how many points they got).

    Supports several OPTIONAL filters, read from the URL's query string
    (?date_from=...&date_to=...&year=...&month=...&user_id=3) rather
    than form-submitted POST data — this keeps the filtered view a
    normal, bookmarkable/shareable GET URL, and lets the
    <select>/<input> fields below auto-submit their own form on change
    (see index.html) without any JavaScript fetch() calls.

    date_from/date_to are an inclusive RANGE (either end optional) —
    NOT the same thing as year/month, which match on a PART of the
    date via SQLite's strftime() regardless of the rest of it. That
    means year and month combine independently: year alone -> every
    asado in that year; month alone -> every asado that ever happened
    in that calendar month, across ALL years (e.g. "every December we've
    ever had"); both together -> that specific month of that year. All
    active filters AND together, same as date_from/date_to/user_id do.

    Also PAGINATED (?page=2), INDEX_PAGE_SIZE asados at a time, so a
    group with years of history doesn't render hundreds of cards on one
    page. Pagination is computed AFTER filtering, so "page 2" always
    means "the second page of whatever the current filters matched."
    """
    db = get_db()

    date_from_filter = request.args.get("date_from", "").strip()
    date_to_filter = request.args.get("date_to", "").strip()
    year_filter = request.args.get("year", "").strip()
    month_filter = request.args.get("month", "").strip()
    user_filter = request.args.get("user_id", "").strip()
    page = parse_page_number(request.args.get("page"))

    # Built up conditionally: a plain "FROM asados" when no filters are
    # set, or narrowed down as needed. Filtering by participant requires
    # joining through participations — DISTINCT (below) avoids listing
    # the same asado twice if it somehow matched more than once.
    from_clause = "FROM asados"
    conditions = []
    params = []

    if user_filter:
        from_clause += " JOIN participations ON participations.asado_id = asados.id"
        conditions.append("participations.user_id = ?")
        params.append(user_filter)

    if date_from_filter:
        conditions.append("asados.date >= ?")
        params.append(date_from_filter)

    if date_to_filter:
        conditions.append("asados.date <= ?")
        params.append(date_to_filter)

    if year_filter:
        conditions.append("strftime('%Y', asados.date) = ?")
        params.append(year_filter)

    if month_filter:
        conditions.append("strftime('%m', asados.date) = ?")
        params.append(month_filter)

    where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    # Count how many asados match the filters BEFORE paginating, so we
    # know how many pages there are (and can clamp an out-of-range
    # ?page= back onto the last real page instead of showing a blank one).
    total_count = db.execute(
        f"SELECT COUNT(DISTINCT asados.id) {from_clause}{where_clause}", params
    ).fetchone()[0]
    total_pages = max(1, -(-total_count // INDEX_PAGE_SIZE))  # ceiling division
    page = min(page, total_pages)
    offset = (page - 1) * INDEX_PAGE_SIZE

    asados = db.execute(
        f"SELECT DISTINCT asados.* {from_clause}{where_clause} "
        "ORDER BY asados.date DESC LIMIT ? OFFSET ?",
        params + [INDEX_PAGE_SIZE, offset],
    ).fetchall()

    # For each asado, also fetch its participants (a small extra query
    # per asado — totally fine for Phase 1's scale; we can optimize
    # with a JOIN later if the dataset grows).
    asados_with_participants = []
    for asado in asados:
        participants = db.execute(
            """
            SELECT users.name, participations.rol, participations.points
            FROM participations
            JOIN users ON participations.user_id = users.id
            WHERE participations.asado_id = ?
            """,
            (asado["id"],),
        ).fetchall()
        # An asado can have more than one Tipo de Carne (minimum one) —
        # joined into one "Cordero; Pollo" string for the card display,
        # same "; " separator used in Base de Asados/CSV.
        tipos_carne = db.execute(
            "SELECT tipo_carne FROM asado_tipo_carne WHERE asado_id = ? ORDER BY id",
            (asado["id"],),
        ).fetchall()
        asados_with_participants.append({
            "asado": asado,
            "participants": participants,
            "tipos_carne": "; ".join(row["tipo_carne"] for row in tipos_carne),
        })

    # For the "Usuario" filter dropdown.
    registered_users = db.execute("SELECT id, username, name FROM users ORDER BY name").fetchall()

    # For the "Año" filter dropdown — only years that actually have at
    # least one asado, newest first, rather than hardcoding a range.
    available_years = [
        row["year"] for row in db.execute(
            "SELECT DISTINCT strftime('%Y', date) AS year FROM asados ORDER BY year DESC"
        ).fetchall()
    ]

    return render_template(
        "index.html",
        asados=asados_with_participants,
        registered_users=registered_users,
        available_years=available_years,
        meses=MESES,
        selected_date_from=date_from_filter,
        selected_date_to=date_to_filter,
        selected_year=year_filter,
        selected_month=month_filter,
        selected_user_id=user_filter,
        page=page,
        total_pages=total_pages,
        # Only actually populated when redirected here after deleting
        # an asado (see delete_asado) — same lightweight ?success=/
        # ?error= pattern used by config.html and base_asados.html.
        success=request.args.get("success"),
        error=request.args.get("error"),
    )


@app.route("/api/points")
def api_points():
    """
    JSON API used ONLY by the live points preview in new_asado.html.
    The browser sends the current form selections as URL query
    parameters, and this route calls the EXACT SAME calculate_points()
    function that saves real data — so the preview can never drift out
    of sync, no matter how the formula changes later (new weights, new
    coefficients, or a completely restructured equation).

    tipo_carne is read with getlist(), not get() — an asado can have
    more than one Tipo de Carne selected at once (only the
    highest-weight one actually counts, see calculate_points()).
    """
    tipo_carne_list = request.args.getlist("tipo_carne")
    coccion = request.args.get("coccion", "")
    superficie = request.args.get("superficie", "")
    local = request.args.get("local", "")
    rol = request.args.get("rol", "")

    points = calculate_points(tipo_carne_list, coccion, superficie, local, rol)
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
        # An asado can have more than one Tipo de Carne (minimum one) —
        # getlist() reads every "tipo_carne" field the form submitted,
        # not just the first. The blank-filter is defensive (the UI
        # never lets you remove the last row or leave one unselected,
        # but a tampered/malformed request shouldn't crash the route).
        tipo_carne_list = [tc for tc in request.form.getlist("tipo_carne") if tc]
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
        # Look up (and freeze) the shared weights NOW, at creation time
        # — see the comment on these columns in schema.sql for why this
        # matters (config.py's weights could change later). "carne" here
        # is the MAX weight across every selected Tipo de Carne — the
        # one that actually feeds the points formula.
        shared_weights = get_shared_weights(tipo_carne_list, coccion, superficie, local)

        cursor = db.execute(
            """
            INSERT INTO asados
                (date, nombre, description, coccion,
                 superficie, local, location, latitude, longitude, people, total_weight,
                 tipo_carne_weight, coccion_weight, superficie_weight, local_weight)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (date, nombre, description, coccion,
             superficie, local, location, latitude, longitude, people, total_weight,
             shared_weights["carne"], shared_weights["coccion"],
             shared_weights["superficie"], shared_weights["local"]),
        )
        asado_id = cursor.lastrowid  # the id SQLite just assigned to this new row

        # Freeze EVERY selected Tipo de Carne's own weight too, not just
        # the winning max above — see schema.sql's asado_tipo_carne
        # table for why (full audit trail: which types were chosen, and
        # each one's own weight, not just the final number that won).
        tipo_carne_weights = get_tipo_carne_weights(tipo_carne_list)
        for tc in tipo_carne_list:
            db.execute(
                "INSERT INTO asado_tipo_carne (asado_id, tipo_carne, tipo_carne_weight) VALUES (?, ?, ?)",
                (asado_id, tc, tipo_carne_weights[tc]),
            )

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
            # Rol is per-participant, so points (and its weight) can
            # differ between people even though they were at the SAME
            # asado — freeze rol_weight here for the same reason as
            # shared_weights above.
            points = calculate_points(tipo_carne_list, coccion, superficie, local, rol)
            rol_weight = get_rol_weight(rol)

            db.execute(
                """
                INSERT INTO participations (asado_id, user_id, rol, rol_weight, points)
                VALUES (?, ?, ?, ?, ?)
                """,
                (asado_id, user_id, rol, rol_weight, points),
            )

        db.commit()  # save everything permanently to the database file

        # Automatic backup, every time a new asado is added — see
        # backup_db.py for why this is a safe SQLite-level backup and
        # not just a file copy. Wrapped in try/except so that if the
        # backup itself ever fails (disk full, permissions, etc.), the
        # user's asado is still saved and the page still loads
        # normally — a failed backup should never look like a failed
        # save. DATABASE (not backup_db's own default) is passed
        # explicitly so this always backs up whichever database file
        # this app instance is actually using, including test runs
        # that point DATABASE at a throwaway file.
        try:
            backup_database(database=DATABASE)
        except Exception as e:
            print(f"Warning: automatic backup failed: {e}")

        return redirect(url_for("index"))  # redirect back to the home page

    # GET request: just show the blank form — same shared partial
    # (_asado_form.html) that view_asado()'s edit form uses below,
    # here in "create mode": asado=None and no existing_participants
    # means it renders one blank participant row instead of prefilling.
    return render_template(
        "new_asado.html",
        asado=None,
        existing_participants=[],
        existing_tipos_carne=[],
        form_action=url_for("new_asado"),
        submit_label="Añadir Asado",
        **asado_form_context(db),
    )


@app.route("/asado/<int:asado_id>")
@login_required
def view_asado(asado_id):
    """
    DETAIL PAGE for one asado: a read-only summary by default, with a
    hidden (until "Editar" is clicked) copy of the shared create/edit
    form (_asado_form.html), prefilled with the asado's current values
    — ANY logged-in user can edit ANY asado here and save (see
    edit_asado() below); only an admin sees the delete button (see
    delete_asado() below and view_asado.html).
    """
    db = get_db()

    asado = db.execute(
        "SELECT * FROM asados WHERE id = ?", (asado_id,)
    ).fetchone()

    if asado is None:
        # No asado has this id (bad/old link, or it was deleted) —
        # without this check, asado would be None and the template's
        # {{ asado.nombre }} would crash the whole page with a 500
        # error instead of a normal "not found" response.
        return "Asado no encontrado.", 404

    # ONE query serves both halves of the page: the read-only view
    # needs name/rol/points to display, and the (hidden) edit form
    # needs user_id/rol to prefill its participant rows.
    participants = db.execute(
        """
        SELECT participations.user_id, users.name, participations.rol, participations.points
        FROM participations
        JOIN users ON participations.user_id = users.id
        WHERE participations.asado_id = ?
        ORDER BY participations.id
        """,
        (asado_id,),
    ).fetchall()
    existing_participants = [{"user_id": p["user_id"], "rol": p["rol"]} for p in participants]

    # Every Tipo de Carne selected for this asado (minimum one) — the
    # list of raw names prefills the edit form's repeatable rows, and
    # the "; "-joined string is what the read-only summary above it shows.
    tipo_carne_rows = db.execute(
        "SELECT tipo_carne FROM asado_tipo_carne WHERE asado_id = ? ORDER BY id",
        (asado_id,),
    ).fetchall()
    existing_tipos_carne = [row["tipo_carne"] for row in tipo_carne_rows]

    return render_template(
        "view_asado.html",
        asado=asado,
        participants=participants,
        existing_participants=existing_participants,
        existing_tipos_carne=existing_tipos_carne,
        tipos_carne_display="; ".join(existing_tipos_carne),
        form_action=url_for("edit_asado", asado_id=asado_id),
        submit_label="Guardar Cambios",
        success=request.args.get("success"),
        error=request.args.get("error"),
        **asado_form_context(db),
    )


@app.route("/asado/<int:asado_id>/edit", methods=["POST"])
@login_required
def edit_asado(asado_id):
    """
    Saves changes to an existing asado. ANY logged-in user may edit ANY
    asado — unlike deleting (admin-only, see delete_asado below), Phase
    3 deliberately does NOT restrict editing to "your own" entries.

    Recalculates and re-freezes the shared weights AND every
    participant's rol_weight/points from config.py's CURRENT values,
    exactly like new_asado()'s POST branch does for a brand new asado.
    An edit counts as a new "freezing moment" — see CLAUDE.md for the
    full reasoning on why weights/points are frozen at all; the same
    logic means the numbers shown after a save should always match
    what's actually on the form, not whatever was frozen back when the
    asado was first created (which may have used different config.py
    weights, if they've since changed).

    Participants are replaced WHOLESALE: every existing participation
    for this asado is deleted, then fresh rows are inserted from
    whatever the form submitted — simpler and correct for a small edit
    form, rather than diffing which rows are new/removed/changed. The
    cost: participation ids change on every edit of that asado's
    participants, but nothing in this app treats participation id as a
    stable reference across edits.
    """
    db = get_db()

    asado = db.execute("SELECT id FROM asados WHERE id = ?", (asado_id,)).fetchone()
    if asado is None:
        return "Asado no encontrado.", 404

    date = request.form["date"]
    nombre = request.form["nombre"]
    description = request.form.get("description", "")
    tipo_carne_list = [tc for tc in request.form.getlist("tipo_carne") if tc]
    coccion = request.form["coccion"]
    superficie = request.form["superficie"]
    local = request.form["local"]
    location = request.form.get("location", "")
    latitude = request.form.get("latitude", type=float)
    longitude = request.form.get("longitude", type=float)
    people = request.form.get("people", type=int)
    total_weight = request.form.get("total_weight", type=float)

    shared_weights = get_shared_weights(tipo_carne_list, coccion, superficie, local)

    db.execute(
        """
        UPDATE asados
        SET date = ?, nombre = ?, description = ?, coccion = ?,
            superficie = ?, local = ?, location = ?, latitude = ?, longitude = ?,
            people = ?, total_weight = ?,
            tipo_carne_weight = ?, coccion_weight = ?, superficie_weight = ?, local_weight = ?
        WHERE id = ?
        """,
        (date, nombre, description, coccion, superficie, local,
         location, latitude, longitude, people, total_weight,
         shared_weights["carne"], shared_weights["coccion"],
         shared_weights["superficie"], shared_weights["local"],
         asado_id),
    )

    # Replace selected Tipo de Carne types wholesale, same pattern (and
    # same reasoning) as participants below.
    db.execute("DELETE FROM asado_tipo_carne WHERE asado_id = ?", (asado_id,))
    tipo_carne_weights = get_tipo_carne_weights(tipo_carne_list)
    for tc in tipo_carne_list:
        db.execute(
            "INSERT INTO asado_tipo_carne (asado_id, tipo_carne, tipo_carne_weight) VALUES (?, ?, ?)",
            (asado_id, tc, tipo_carne_weights[tc]),
        )

    # Replace participants wholesale (see docstring above).
    db.execute("DELETE FROM participations WHERE asado_id = ?", (asado_id,))

    user_ids = request.form.getlist("participant_user_id")
    roles = request.form.getlist("participant_rol")

    for user_id_str, rol in zip(user_ids, roles):
        if not user_id_str:
            continue  # skip any row where nothing was selected

        user_id = int(user_id_str)

        # Safety check: confirm this id really matches an existing
        # user, in case of any tampering with the submitted form.
        user_row = db.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if user_row is None:
            continue

        points = calculate_points(tipo_carne_list, coccion, superficie, local, rol)
        rol_weight = get_rol_weight(rol)

        db.execute(
            """
            INSERT INTO participations (asado_id, user_id, rol, rol_weight, points)
            VALUES (?, ?, ?, ?, ?)
            """,
            (asado_id, user_id, rol, rol_weight, points),
        )

    db.commit()
    return redirect(url_for("view_asado", asado_id=asado_id, success="Asado actualizado."))


@app.route("/asado/<int:asado_id>/delete", methods=["POST"])
@admin_required
def delete_asado(asado_id):
    """
    Admin-only: permanently deletes an asado and ALL its participations
    (i.e. every participant's points for that event too). No server-side
    "are you sure" step — view_asado.html's delete button has a JS
    confirm() instead, the same pattern delete_user_route already uses.
    """
    db = get_db()

    asado = db.execute("SELECT id FROM asados WHERE id = ?", (asado_id,)).fetchone()
    if asado is None:
        return "Asado no encontrado.", 404

    # Participations and asado_tipo_carne FIRST — schema.sql declares
    # both asado_id columns as FOREIGN KEYs, and get_db() enforces that
    # (PRAGMA foreign_keys = ON), so deleting the asado row first would
    # fail with an IntegrityError while either still references it.
    db.execute("DELETE FROM participations WHERE asado_id = ?", (asado_id,))
    db.execute("DELETE FROM asado_tipo_carne WHERE asado_id = ?", (asado_id,))
    db.execute("DELETE FROM asados WHERE id = ?", (asado_id,))
    db.commit()

    return redirect(url_for("index", success="Asado eliminado."))


@app.route("/base-asados")
@login_required
def base_asados():
    """
    "Base de Asados": a flat, spreadsheet-style table — one row per
    PARTICIPATION rather than per asado (see BASE_ASADOS_QUERY above).
    Meant for scanning/sorting like a spreadsheet, and for the CSV
    export below.

    PAGINATED (?page=2), BASE_ASADOS_PAGE_SIZE rows at a time — the CSV
    export below intentionally does NOT paginate (it's a "give me
    everything" download, not a page you're scrolling through), so the
    LIMIT/OFFSET here is added on top of BASE_ASADOS_QUERY only in this
    route, never touching BASE_ASADOS_QUERY itself.
    """
    db = get_db()
    page = parse_page_number(request.args.get("page"))

    total_count = db.execute("SELECT COUNT(*) FROM participations").fetchone()[0]
    total_pages = max(1, -(-total_count // BASE_ASADOS_PAGE_SIZE))  # ceiling division
    page = min(page, total_pages)
    offset = (page - 1) * BASE_ASADOS_PAGE_SIZE

    rows = db.execute(
        BASE_ASADOS_QUERY + " LIMIT ? OFFSET ?", (BASE_ASADOS_PAGE_SIZE, offset)
    ).fetchall()

    return render_template(
        "base_asados.html", rows=rows, page=page, total_pages=total_pages
    )


def sanitize_csv_cell(value):
    """
    Defends against "CSV/Excel formula injection": if a cell's text
    STARTS WITH =, +, -, or @, spreadsheet programs (Excel, Google
    Sheets, LibreOffice) may interpret it as a FORMULA instead of plain
    text when the file is opened, rather than showing it as literal
    text. Several fields exported here are free text a group member
    controls themselves — an asado's nombre/location, or their own
    display name via the Configuración page — so without this, someone
    could plant something like "=HYPERLINK(...)" in their own name and
    have it execute in whoever's spreadsheet program opens this export.

    Prefixing with a single quote/apostrophe forces spreadsheet programs
    to treat the cell as literal text; it's invisible in every other
    program that reads CSV files (including re-importing this same file).
    Only touches actual strings — numeric columns (points, weights,
    coordinates, ids) come back from sqlite3 as int/float, never str,
    so they pass through untouched.
    """
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


@app.route("/base-asados/csv")
@login_required
def base_asados_csv():
    """Exports ALL rows (ignoring pagination — this is a full download,
    not a scrolled-through page) as a downloadable CSV file."""
    db = get_db()
    rows = db.execute(BASE_ASADOS_QUERY).fetchall()

    # csv.writer wants a file-like object to write into; io.StringIO
    # gives us an in-memory "file" so we never touch the disk for this.
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Participation ID", "Asado ID", "Fecha", "Nombre Asado",
        "Tipo Carne", "Peso Tipo Carne", "Cocción", "Peso Cocción",
        "Superficie", "Peso Superficie", "Local", "Peso Local",
        "Ubicación", "Latitud", "Longitud", "Personas", "Peso Total (kg)",
        "Usuario", "Nombre", "Rol", "Peso Rol", "Puntos",
    ])
    for row in rows:
        writer.writerow([
            sanitize_csv_cell(value) for value in (
                row["participation_id"], row["asado_id"], row["date"], row["nombre"],
                row["tipo_carne"], row["tipo_carne_weight"], row["coccion"], row["coccion_weight"],
                row["superficie"], row["superficie_weight"], row["local"], row["local_weight"],
                row["location"], row["latitude"], row["longitude"], row["people"], row["total_weight"],
                row["username"], row["name"], row["rol"], row["rol_weight"], row["points"],
            )
        ])

    # "﻿" is a UTF-8 BOM (byte-order mark). Excel on Windows needs
    # it to correctly detect UTF-8 and render accented characters
    # (ñ, ó, í, etc.) instead of garbling them — invisible in every
    # other program that opens this file.
    csv_data = "﻿" + output.getvalue()

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=base_asados.csv"},
    )


# ---------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------
if __name__ == "__main__":
    # debug=True auto-reloads the server when you edit code, and shows
    # detailed error pages — great for development, turn OFF in production.
    app.run(debug=True, host="0.0.0.0", port=5000)
