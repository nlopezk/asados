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
import collections
import secrets                     # unguessable CSRF tokens + the export-token comparison
from flask import Flask, render_template, request, redirect, url_for, g, jsonify, session, Response
from werkzeug.security import check_password_hash, generate_password_hash
from config import (
    calculate_points, get_shared_weights, get_rol_weight, get_tipo_carne_weights,
    TIPO_CARNE_WEIGHTS, COCCION_WEIGHTS, SUPERFICIE_WEIGHTS,
    LOCAL_WEIGHTS, ROL_WEIGHTS, FORMULA, VARIABLE_LABELS,
)
from backup_db import backup_database
from activity_log import log_create, log_edit, log_delete, diff_asado, now_timestamp

DATABASE = "asados.db"  # the SQLite database is just a single file on disk

# Shown in the small footer on every page (see base.html) — bumped by
# hand alongside CHANGELOG.md and the matching git tag each time a
# version is cut (see CLAUDE.md). Nothing ties these three together
# automatically; forgetting to bump this is a real, easy-to-repeat
# mistake, so check it specifically before tagging a new release.
VERSION = "1.2.0"

# How many rows to show per page before showing a "next" arrow, on the
# home page and on Base de Asados respectively. Base de Asados can show
# more per page since each row is much narrower (a spreadsheet line)
# than a full asado card.
INDEX_PAGE_SIZE = 30
BASE_ASADOS_PAGE_SIZE = 100
ACTIVITY_LOG_PAGE_SIZE = 30

# For the home page's "Mes" filter dropdown. Kept as a plain number
# (label) rather than a Spanish month name, to save space in the filter
# bar. Values stay zero-padded ("01".."12") on purpose — SQLite's
# strftime('%m', ...) always returns a zero-padded month, so the
# filter's WHERE clause can compare these values directly without any
# extra padding logic.
MESES = [(f"{m:02d}", str(m)) for m in range(1, 13)]

# For the Resumen page's "Semestre" filter. The cut is by CALENDAR half:
# 1st = January 1 through June 30, 2nd = July 1 through December 31.
# Values are matched against SQLite's strftime('%m', date), which always
# returns a zero-padded month ("01".."12") — so a plain string
# comparison against '06'/'07' works correctly here (all values are the
# same width, making lexical and numeric order identical). Same
# zero-padding reasoning as MESES above.
SEMESTRES = [
    ("1", "1° (ene–jun)"),
    ("2", "2° (jul–dic)"),
]

# ---------------------------------------------------------------------
# "RESUMEN" (standings table) — allowed sort columns
# ---------------------------------------------------------------------
# Maps the ?sort= value in the URL to the SQL expression to ORDER BY.
# This mapping is a SECURITY BOUNDARY, not just a convenience: the sort
# column can't be parameterized with a "?" placeholder the way values
# are everywhere else in this file (SQL placeholders work for values,
# never for identifiers/expressions), so it HAS to be concatenated into
# the query string. Concatenating the raw query param would be a
# straightforward SQL injection hole. Looking the user's input up as a
# KEY here means only these nine hard-coded expressions can ever reach
# the database — anything else falls back to the default. Never replace
# this with the raw ?sort= value, and keep any new column going through
# this same dict.
RESUMEN_SORT_COLUMNS = {
    "usuario": "users.name",
    "participaciones": "COUNT(participations.id)",
    "carne": "SUM(asados.tipo_carne_weight)",
    "coccion": "SUM(asados.coccion_weight)",
    "superficie": "SUM(asados.superficie_weight)",
    "local": "SUM(asados.local_weight)",
    "rol": "SUM(participations.rol_weight)",
    "promedio": "AVG(participations.points)",
    "total": "SUM(participations.points)",
}

# Sorted by total points, highest first — it's a standings table, so the
# leader belongs on top before anyone touches a header.
RESUMEN_DEFAULT_SORT = "total"
RESUMEN_DEFAULT_DIRECTION = "desc"

# ---------------------------------------------------------------------
# USER COLOR — one identity color per user, shared across the WHOLE app
# ---------------------------------------------------------------------
# Originally built just for the Resumen chart (hence the name that
# stuck on the variable below), then reused as-is for the small color
# swatch next to a name in Resumen's table and next to each participant
# on the home page — deliberately the SAME palette and the SAME
# assignment rule everywhere, via get_user_color() below, rather than
# three places independently deciding "what color is this person."
# Recoloring the app, or extending it to a 4th place (Base de Asados?
# view_asado.html?), means calling get_user_color() there too — never
# re-deriving a color inline.
#
# This is a CATEGORICAL palette (identity: which user), 8 fixed hues in
# a fixed order — never generated, never reassigned by row position.
# These are the dataviz skill's own documented default categorical
# hues (dark-surface column), used UNCHANGED: run against this app's
# actual chart/card surface (--color-surface, the walnut/leather
# #453524 cards use) rather than the skill's own near-black reference
# surface, they still clear every hard gate — lightness band, chroma
# floor, CVD separation (adjacent ΔE 8.4 — the relevant gate for a line
# chart or a column of swatches in a list, where only NEIGHBOURING
# entries are ever compared side by side; a scatter/bubble chart, where
# any two dots can end up adjacent, would need the much stricter
# all-pairs gate instead, which this palette's full 8 slots do NOT
# clear), and the normal-vision floor. Two slots (magenta, green) land
# under the 3:1 contrast floor against that surface — legal only WITH
# secondary encoding, which is why every place this color appears also
# shows the person's NAME right next to the swatch, never a color
# standing alone as the only identifier. See CLAUDE.md's "Resumen's
# chart" section for the full validation run this palette came from.
#
# Indexed by (user_id - 1) % 8 in get_user_color() below, NOT by row/
# sort position — "color follows the entity, never its rank" (dataviz
# skill). A user keeps the same color for as long as their account
# exists, regardless of another user being added or deleted, or of how
# any given table happens to be sorted at the moment. Past 8 users the
# palette repeats (two people would share a color) — a real limit
# worth revisiting with the same six-checks validator if this group
# ever grows past 8 active accounts, not something to silently patch
# by generating a 9th hue.
USER_COLOR_PALETTE = [
    "#3987e5",  # 1 blue
    "#d95926",  # 2 orange
    "#199e70",  # 3 aqua
    "#c98500",  # 4 yellow
    "#d55181",  # 5 magenta
    "#008300",  # 6 green
    "#9085e9",  # 7 violet
    "#e66767",  # 8 red
]


def get_user_color(user_id):
    """THE single place that decides what color a user is, anywhere in
    this app — the chart, the Resumen table, the home page's
    participant lists, and anywhere added later all call this instead
    of indexing USER_COLOR_PALETTE themselves. Also injected into every
    Jinja template as user_color() (see inject_user_color() below), so
    a template can call {{ user_color(row.user_id) }} directly without
    app.py needing to pre-compute a "color" field into every query
    result first."""
    return USER_COLOR_PALETTE[(user_id - 1) % len(USER_COLOR_PALETTE)]


def build_resumen_chart_data(db):
    """
    Builds the data for Resumen's "cumulative points over time" chart —
    one step-line per user, points accumulating as their asados happen.

    Deliberately INDEPENDENT of the page's own ?year=/?semester= filters
    that scope the standings table above it. Those answer "who's ahead
    THIS period"; a cumulative total sliced to a period and re-started
    at 0 answers a much less useful question ("points scored only
    inside this window", which isn't really "cumulative" any more).
    Instead the chart always plots the FULL history, and its own
    pan/zoom/range-selector (see resumen.html) is how a viewer explores
    a period — a real interactive control, not a second, conflicting
    filter fighting the one above the table.

    Returns a JSON-serializable dict (plain lists/dicts, never
    sqlite3.Row — those aren't JSON-serializable), embedded into
    resumen.html via `{{ chart_data | tojson }}`:
        {
            "series": [
                {"user_id": 1, "name": "...", "color": "#...",
                 "points": [["2026-01-01", 0.0], ["2026-01-02", 0.8], ...]},
                ...
            ],
        }
    Empty "series" (no participations at all, ever) is a valid, expected
    result — resumen.html shows a plain empty-state message instead of
    an empty chart in that case, same pattern as the table above it.

    THE STEP SHAPE (drawn in resumen.html via Plotly's `shape: 'hv'`)
    is what makes this an honest picture, not just a stylistic choice:
    a cumulative total is exactly flat between two asados and jumps
    EXACTLY on the date of the next one — a straight diagonal line
    between two points (the plotting default) would imply points
    trickled in continuously, which never happened.

    WHY EVERY LINE STARTS AT (min_date, 0) AND ENDS AT (max_date, their
    latest total): so all users sit on the same x-axis start/end and a
    late-joining or occasional participant reads as "flat, then
    rising" rather than a line that simply starts mid-chart with no
    visual way to compare it to someone who's been around since day
    one. This is honest, not misleading — their real cumulative total
    on a date before their first asado genuinely was zero.
    """
    rows = db.execute(
        """
        SELECT users.id AS user_id, users.name AS name, asados.date AS date,
               SUM(participations.points) AS day_points
        FROM participations
        JOIN asados ON asados.id = participations.asado_id
        JOIN users ON users.id = participations.user_id
        GROUP BY users.id, asados.date
        ORDER BY users.id, asados.date
        """
    ).fetchall()

    if not rows:
        return {"series": []}

    by_user = collections.OrderedDict()
    names = {}
    for r in rows:
        by_user.setdefault(r["user_id"], []).append((r["date"], r["day_points"]))
        names[r["user_id"]] = r["name"]

    all_dates = [r["date"] for r in rows]
    min_date = min(all_dates)
    max_date = max(all_dates)

    series = []
    for user_id, day_points in by_user.items():
        cumulative = 0.0
        curve = []
        # Anchor the start: if this user's own first asado is AFTER
        # the group's earliest one, insert an explicit (min_date, 0)
        # point so their line starts flat from the same left edge as
        # everyone else's, instead of only beginning wherever their
        # own history happens to start.
        if day_points[0][0] != min_date:
            curve.append([min_date, 0.0])
        for date, points_that_day in day_points:
            cumulative = round(cumulative + points_that_day, 2)
            curve.append([date, cumulative])
        # Anchor the end the same way, so every line reaches the same
        # right edge (flat at their latest total) rather than stopping
        # dead at whatever date they last happened to attend.
        if curve[-1][0] != max_date:
            curve.append([max_date, cumulative])

        series.append({
            "user_id": user_id,
            "name": names[user_id],
            "color": get_user_color(user_id),
            "points": curve,
        })

    # Cosmetic, not load-bearing: ordering series highest-final-total
    # first makes the legend read roughly like the standings table
    # above it, which is a nicer default than sqlite's GROUP BY order
    # (by user_id) — but nothing downstream depends on this order.
    series.sort(key=lambda s: -s["points"][-1][1])

    return {"series": series}


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
# EXPORT TOKEN (for the Looker Studio / Google Sheets CSV feed)
# ---------------------------------------------------------------------
# Same auto-generate-once-then-reuse pattern as SECRET_KEY_FILE above,
# for a completely different purpose: this token guards
# /export/base-asados.csv (see its own section near base_asados_csv()
# below), a CSV endpoint meant to be fetched by Google Sheets'
# IMPORTDATA() — which can't log in, so it can't use the normal
# session-cookie auth every other route relies on. A long random token
# in the URL is the standard way to let an external, non-interactive
# fetcher in without a real login system.
#
# export_token.txt is gitignored, exactly like secret_key.txt — it
# guards the same real personal data (names, addresses, points) via a
# path that skips the login page entirely, so treat it with the same
# care: never commit it, never paste it somewhere public. Rotating it
# is just deleting the file and restarting the app (or reloading, on
# PythonAnywhere) — a fresh token is generated the same way a fresh
# secret key would be.
EXPORT_TOKEN_FILE = "export_token.txt"

if os.path.exists(EXPORT_TOKEN_FILE):
    with open(EXPORT_TOKEN_FILE, "r") as f:
        EXPORT_TOKEN = f.read().strip()
else:
    EXPORT_TOKEN = os.urandom(24).hex()
    with open(EXPORT_TOKEN_FILE, "w") as f:
        f.write(EXPORT_TOKEN)

# --- Session cookie hardening ---------------------------------------
# SameSite=Lax tells the browser not to send our session cookie along
# with cross-site POSTs — the exact shape of a CSRF attack. Modern
# browsers already treat an unspecified SameSite as Lax, so this
# mostly makes the existing behavior EXPLICIT rather than depending on
# a browser default that older browsers don't share. It's a second
# layer behind validate_csrf_token() below, not a replacement for it.
#
# HTTPONLY (Flask's default, restated here so it's visible next to the
# others) keeps JavaScript from reading the cookie, limiting the damage
# an XSS bug could do.
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_HTTPONLY"] = True
# NOT set here on purpose: SESSION_COOKIE_SECURE = True would tell the
# browser to send the cookie over HTTPS only. That's correct for the
# PythonAnywhere deployment (it serves HTTPS) but would BREAK local
# development, where you visit plain http://127.0.0.1:5000 — the
# browser would refuse to send the cookie at all and login would
# silently never stick. If this app ever gets a production-vs-dev
# config split, turning it on for production is the right move.


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


@app.template_filter("blank_if_none")
def blank_if_none(value):
    """Renders a NULL database value as an empty cell instead of the
    literal text "None".

    Jinja prints Python's None as "None", which is what a nullable
    column (asados.people/total_weight/latitude/longitude — all
    genuinely optional on the form) looked like in Base de Asados: a
    column of the word "None" wherever nobody had filled that field in.

    A filter rather than the shorter "{{ value or '' }}" idiom on
    purpose: "or" treats every falsy value the same, so a real,
    deliberately-entered 0 (0 kg, or latitude 0) would also vanish.
    This only ever blanks an actual None.
    """
    return "" if value is None else value


@app.context_processor
def inject_version():
    """Makes {{ version }} available in every template — same
    "inject once, use everywhere" pattern as csrf_token() above — so
    base.html's footer can show it without every single route passing
    it through render_template() by hand."""
    return {"version": VERSION}


@app.context_processor
def inject_user_color():
    """Makes user_color(user_id) callable from any template — e.g.
    {{ user_color(row.user_id) }} — same "inject once, use everywhere"
    pattern as csrf_token()/version above. This is what lets
    resumen.html and index.html both show the same per-user color
    swatch without app.py needing to pre-compute a "color" key into
    every query result those two (and any future) routes build."""
    return {"user_color": get_user_color}


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
# UBICACIONES (reusable pool of saved locations)
# ---------------------------------------------------------------------
# See CLAUDE.md's "Recurring locations" section for the full reasoning.
# Any logged-in user can add a new saved location or fix a typo in an
# existing one (same open-editing philosophy as asados themselves);
# only an admin can delete one — same asymmetry as delete_asado, for
# the same reason (this removes a resource other people may be relying
# on). Deliberately NOT linked to `asados` via a foreign key: this pool
# only ever PREFILLS the normal location/latitude/longitude fields at
# save time, so editing/deleting a saved location here never
# retroactively touches any asado that already used it.

@app.route("/ubicaciones")
@login_required
def locations_page():
    db = get_db()
    locations = db.execute(
        """
        SELECT locations.*, users.name AS created_by_name
        FROM locations
        LEFT JOIN users ON locations.created_by = users.id
        ORDER BY locations.name
        """
    ).fetchall()
    return render_template(
        "ubicaciones.html",
        locations=locations,
        success=request.args.get("success"),
        error=request.args.get("error"),
    )


@app.route("/ubicaciones/create", methods=["POST"])
@login_required
def create_location():
    """Manual "add a saved location" form on /ubicaciones itself. The
    MORE common way a location gets added is opportunistically, via the
    "Guardar esta ubicación" checkbox on the asado form (see
    maybe_save_location() below) — this route exists so the pool can
    also be built up directly, without needing to create/edit an asado
    first."""
    db = get_db()
    name = request.form.get("name", "").strip()
    address = request.form.get("address", "").strip()
    latitude = request.form.get("latitude", type=float)
    longitude = request.form.get("longitude", type=float)

    # Name, address, AND coordinates are all mandatory here — unlike
    # the asado form's own (optional) location, a saved location with a
    # missing address or no real coordinates would be useless as a
    # future quick-fill. locations.* is NOT NULL at the DB level too
    # (see schema.sql); this is the friendly, form-level check that
    # runs first, same "form-required = DB NOT NULL" pattern asados
    # already uses for its own required fields.
    if not name:
        return redirect(url_for("locations_page", error="El nombre no puede estar vacío."))
    if not address:
        return redirect(url_for("locations_page", error="La dirección no puede estar vacía."))
    if latitude is None or longitude is None:
        return redirect(url_for(
            "locations_page",
            error="Selecciona una sugerencia o un punto en el mapa para fijar las coordenadas.",
        ))

    existing = db.execute("SELECT 1 FROM locations WHERE LOWER(name) = LOWER(?)", (name,)).fetchone()
    if existing:
        return redirect(url_for("locations_page", error=f"Ya existe una ubicación llamada '{name}'."))

    db.execute(
        "INSERT INTO locations (name, address, latitude, longitude, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (name, address, latitude, longitude, session["user_id"], now_timestamp()),
    )
    db.commit()
    return redirect(url_for("locations_page", success=f"Ubicación '{name}' guardada."))


@app.route("/ubicaciones/<int:location_id>/edit", methods=["POST"])
@login_required
def edit_location(location_id):
    """Any logged-in user may edit any saved location — e.g. fixing a
    typo'd address — same open-editing rule asados themselves use."""
    db = get_db()
    location = db.execute("SELECT id FROM locations WHERE id = ?", (location_id,)).fetchone()
    if location is None:
        return "Ubicación no encontrada.", 404

    name = request.form.get("name", "").strip()
    address = request.form.get("address", "").strip()
    latitude = request.form.get("latitude", type=float)
    longitude = request.form.get("longitude", type=float)

    # Same mandatory checks as create_location() above.
    if not name:
        return redirect(url_for("locations_page", error="El nombre no puede estar vacío."))
    if not address:
        return redirect(url_for("locations_page", error="La dirección no puede estar vacía."))
    if latitude is None or longitude is None:
        return redirect(url_for("locations_page", error="La latitud y longitud son obligatorias."))

    duplicate = db.execute(
        "SELECT 1 FROM locations WHERE LOWER(name) = LOWER(?) AND id != ?", (name, location_id)
    ).fetchone()
    if duplicate:
        return redirect(url_for("locations_page", error=f"Ya existe otra ubicación llamada '{name}'."))

    db.execute(
        "UPDATE locations SET name = ?, address = ?, latitude = ?, longitude = ? WHERE id = ?",
        (name, address, latitude, longitude, location_id),
    )
    db.commit()
    return redirect(url_for("locations_page", success="Ubicación actualizada."))


@app.route("/ubicaciones/<int:location_id>/delete", methods=["POST"])
@admin_required
def delete_location(location_id):
    """Admin-only — see the module-level comment above for why this one
    action (unlike add/edit) is restricted."""
    db = get_db()
    db.execute("DELETE FROM locations WHERE id = ?", (location_id,))
    db.commit()
    return redirect(url_for("locations_page", success="Ubicación eliminada."))


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
        # For the "Ubicación guardada" quick-fill dropdown — see
        # CLAUDE.md's "Recurring locations" section. Purely a prefill
        # convenience: picking one just fills in the same location/
        # latitude/longitude fields you'd otherwise type/map-pick
        # yourself, nothing here is a live link back to this table.
        "saved_locations": db.execute(
            "SELECT id, name, address, latitude, longitude FROM locations ORDER BY name"
        ).fetchall(),
    }


def maybe_save_location(db, user_id, name, address, latitude, longitude):
    """
    Called from new_asado()/edit_asado() when the "Guardar esta
    ubicación" checkbox was ticked — inserts a new row into `locations`
    so it shows up in the "Ubicación guardada" dropdown next time (see
    CLAUDE.md's "Recurring locations" section). A no-op (returns
    without inserting) if:
      - `name` is blank,
      - `address`/`latitude`/`longitude` are missing — locations.* are
        NOT NULL (see schema.sql), and unlike /ubicaciones' OWN "Nueva
        Ubicación" form, the asado form's location stays fully
        optional/free-typed, so it's entirely possible to reach here
        with an address that was never actually geocoded (no
        suggestion/map point ever picked). Silently not saving it to
        the pool is the right behavior — a location with no real
        coordinates would be useless as a map quick-fill anyway — and
        this asado itself must still save normally either way,
      - a location with that exact name (case-insensitive) already
        exists — silently skipping a duplicate is simpler and less
        surprising than erroring out an otherwise-successful asado save
        over a naming collision; renaming/fixing an existing saved
        location is what the /ubicaciones page itself is for.
    """
    if not name or not address or latitude is None or longitude is None:
        return
    existing = db.execute("SELECT 1 FROM locations WHERE LOWER(name) = LOWER(?)", (name,)).fetchone()
    if existing:
        return
    db.execute(
        "INSERT INTO locations (name, address, latitude, longitude, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (name, address, latitude, longitude, user_id, now_timestamp()),
    )


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
            SELECT users.id AS user_id, users.name, participations.rol, participations.points
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
@login_required
def api_points():
    """
    JSON API used ONLY by the live points preview in new_asado.html.

    @login_required like every other route: this was missing until a
    v1.0 audit caught it, making it the one endpoint in the whole app
    reachable without an account. Nothing here reads or writes the
    database, so nothing private leaked — but it did let an anonymous
    caller probe the scoring weights by trying combinations, and an
    unauthenticated endpoint is a liability regardless. The page that
    uses it is itself behind a login, so requiring one costs nothing.
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
        # "Guardar esta ubicación" checkbox (see _asado_form.html) — an
        # UNCHECKED box, the default, means today's original one-off
        # behavior: this location is used for THIS asado only and never
        # added to the reusable pool. See maybe_save_location() above.
        save_location = request.form.get("save_location") == "on"
        location_name = request.form.get("location_name", "").strip()

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

        # Log the creation — see activity_log.py. Called before commit()
        # so the log entry and the asado itself are saved together, in
        # the same transaction (either both succeed or, if something
        # above raised first, neither does).
        log_create(db, session["user_id"], g.name, asado_id, nombre, date)

        # If "Guardar esta ubicación" was checked, add it to the
        # reusable pool now — see maybe_save_location() above.
        if save_location:
            maybe_save_location(db, session["user_id"], location_name, location, latitude, longitude)

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

    # Fetch the FULL "before" state now, not just id — diff_asado()
    # below needs it to compare against what's being submitted.
    # Participations and asado_tipo_carne are captured too, since
    # they're about to be deleted and replaced wholesale further down
    # (see their own comments) — their old state wouldn't exist to look
    # up anymore by the time the diff is built otherwise.
    old_asado = db.execute("SELECT * FROM asados WHERE id = ?", (asado_id,)).fetchone()
    if old_asado is None:
        return "Asado no encontrado.", 404

    old_tipo_carne_rows = db.execute(
        "SELECT tipo_carne FROM asado_tipo_carne WHERE asado_id = ? ORDER BY id", (asado_id,)
    ).fetchall()
    old_tipo_carne = [row["tipo_carne"] for row in old_tipo_carne_rows]

    old_participant_rows = db.execute(
        """
        SELECT users.name, participations.rol
        FROM participations JOIN users ON participations.user_id = users.id
        WHERE participations.asado_id = ?
        ORDER BY participations.id
        """,
        (asado_id,),
    ).fetchall()
    old_participants = [f"{p['name']} ({p['rol']})" for p in old_participant_rows]

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
    save_location = request.form.get("save_location") == "on"
    location_name = request.form.get("location_name", "").strip()

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

    new_participants = []  # "Nombre (Rol)" strings, for the activity log diff below
    for user_id_str, rol in zip(user_ids, roles):
        if not user_id_str:
            continue  # skip any row where nothing was selected

        user_id = int(user_id_str)

        # Safety check: confirm this id really matches an existing
        # user, in case of any tampering with the submitted form. Also
        # fetches "name" now (not just "id"), needed for the activity
        # log's participant diff below.
        user_row = db.execute("SELECT id, name FROM users WHERE id = ?", (user_id,)).fetchone()
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
        new_participants.append(f"{user_row['name']} ({rol})")

    # Log this edit: one activity_log row, plus one activity_log_changes
    # row per field that actually differs from the "before" state
    # captured at the top of this route — see activity_log.py.
    changes = diff_asado(
        old_asado,
        {
            "date": date, "nombre": nombre, "description": description,
            "coccion": coccion, "superficie": superficie, "local": local,
            "location": location, "people": people, "total_weight": total_weight,
        },
        old_tipo_carne, tipo_carne_list,
        old_participants, new_participants,
    )
    log_edit(db, session["user_id"], g.name, asado_id, nombre, date, changes)

    # If "Guardar esta ubicación" was checked, add it to the reusable
    # pool now — see maybe_save_location() above.
    if save_location:
        maybe_save_location(db, session["user_id"], location_name, location, latitude, longitude)

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

    asado = db.execute("SELECT id, nombre, date FROM asados WHERE id = ?", (asado_id,)).fetchone()
    if asado is None:
        return "Asado no encontrado.", 404

    # Log the deletion FIRST, while asado_id still references a real,
    # not-yet-deleted row — activity_log.asado_id is a real FOREIGN KEY,
    # and its ON DELETE SET NULL only nulls it out once the asado row
    # below is actually removed, not before. See activity_log.py's
    # log_delete() docstring for the full reasoning.
    log_delete(db, session["user_id"], g.name, asado_id, asado["nombre"], asado["date"])

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


def build_base_asados_csv_response():
    """
    Builds the actual CSV Response — the header row, every sanitized
    cell, the BOM prefix, the attachment headers. Shared by BOTH CSV
    routes below (the login-gated one a browser downloads from, and the
    token-gated one Google Sheets fetches) so there is exactly ONE
    place that decides what "the CSV export" contains — same reasoning
    as BASE_ASADOS_QUERY itself being the one place that decides what
    "Base de Asados" means, or config.py's FORMULA being the one place
    the points formula is written. Two copies of this column list would
    eventually drift (the same lesson as index()/edit_asado()'s
    "reorder the headers, forget the cells" bug from the 1.0.0 audit —
    a second identical copy is just a second chance to make that
    mistake).
    """
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
    # other program that opens this file, including Google Sheets'
    # own IMPORTDATA() parser.
    csv_data = "﻿" + output.getvalue()

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=base_asados.csv"},
    )


@app.route("/base-asados/csv")
@login_required
def base_asados_csv():
    """Exports ALL rows (ignoring pagination — this is a full download,
    not a scrolled-through page) as a downloadable CSV file."""
    return build_base_asados_csv_response()


# ---------------------------------------------------------------------
# /export/base-asados.csv — the same CSV, for Google Sheets/Looker Studio
# ---------------------------------------------------------------------
# WHY THIS ROUTE EXISTS, AND WHY IT'S SHAPED THE WAY IT IS:
#
# Looker Studio (formerly Google Data Studio) has no SQLite connector
# at all — it only talks to things like Google Sheets, BigQuery, or a
# handful of specific databases. The bridge is: this endpoint serves
# the exact same CSV as base_asados_csv() above, a Google Sheet cell
# runs =IMPORTDATA() against this URL (Sheets refreshes that on its
# own every couple of hours, and instantly on demand), and Looker
# Studio connects to that Sheet with its ordinary, built-in Sheets
# connector. Nothing new on the Looker Studio side, nothing new in
# Google Cloud — the only new piece is this one route.
#
# It CANNOT use @login_required like every other route (deliberately,
# not an oversight — see the audit note in CLAUDE.md about routes
# missing that decorator): Sheets' IMPORTDATA() has no way to fill in a
# username/password or carry a session cookie, it just fetches a URL.
# So this route is gated by EXPORT_TOKEN instead — a long random
# secret in the query string, checked with secrets.compare_digest()
# rather than "!=" specifically because this token is a single,
# long-lived secret guarding real personal data (names, addresses,
# points) over a path with NO login at all; that's a meaningfully
# higher bar than the CSRF token's plain "!=" comparison elsewhere in
# this file, which is per-session, short-lived, and only ever
# compared against requests that already carry a valid login cookie.
# compare_digest() takes the same amount of time regardless of how
# much of the token matches, which is what actually defeats a
# timing-based guessing attack — a plain "!=" leaks a few nanoseconds
# of extra time per correct leading character, in principle enough to
# brute-force the token character by character given enough requests.
#
# A missing or wrong token gets a bare 403 with no CSV body — never a
# 200 with partial or dummy data, and never a different error message
# for "missing" vs "wrong" (either would help an attacker narrow down
# what's going on).
@app.route("/export/base-asados.csv")
def base_asados_csv_export():
    submitted = request.args.get("token", "")
    if not secrets.compare_digest(submitted, EXPORT_TOKEN):
        return "Acceso denegado: token inválido o ausente.", 403
    return build_base_asados_csv_response()


@app.route("/actividad")
@login_required
def activity_log_page():
    """
    "Registro de Actividad": a chronological feed of who created,
    edited, or deleted which asado, and when — the activity_log table
    populated by log_create()/log_edit()/log_delete() (see
    activity_log.py) from new_asado(), edit_asado(), and delete_asado()
    above.

    Visible to EVERY logged-in user, not just admins — deliberately the
    same visibility as editing itself (see CLAUDE.md's "Edit/delete
    permissions" note: any user can edit any asado). Since that
    openness already exists, this log is what makes it accountable/
    transparent to the whole group, not something that itself needs
    restricting.

    Newest first, paginated like index()/base_asados() above.
    """
    db = get_db()
    page = parse_page_number(request.args.get("page"))

    total_count = db.execute("SELECT COUNT(*) FROM activity_log").fetchone()[0]
    total_pages = max(1, -(-total_count // ACTIVITY_LOG_PAGE_SIZE))  # ceiling division
    page = min(page, total_pages)
    offset = (page - 1) * ACTIVITY_LOG_PAGE_SIZE

    entries = db.execute(
        "SELECT * FROM activity_log ORDER BY id DESC LIMIT ? OFFSET ?",
        (ACTIVITY_LOG_PAGE_SIZE, offset),
    ).fetchall()

    # One small extra query per entry for its field-level changes (only
    # 'edit' entries ever have any) — same "fine at this app's scale"
    # tradeoff index() already makes fetching each asado's participants.
    entries_with_changes = []
    for entry in entries:
        changes = db.execute(
            "SELECT field_label, old_value, new_value FROM activity_log_changes WHERE log_id = ? ORDER BY id",
            (entry["id"],),
        ).fetchall()
        entries_with_changes.append({"entry": entry, "changes": changes})

    return render_template(
        "activity_log.html",
        entries=entries_with_changes,
        page=page,
        total_pages=total_pages,
    )


@app.route("/resumen")
@login_required
def resumen_page():
    """
    "Resumen": a standings/position table — ONE ROW PER USER, with their
    totals across every participation that matches the current filters.

    Note the GRAIN, since this app now has three different table shapes
    and mixing them up is an easy mistake: index() is one row per ASADO,
    base_asados() is one row per PARTICIPATION, and this is one row per
    USER (a GROUP BY over participations). Don't try to reuse
    BASE_ASADOS_QUERY here.

    WHAT THE WEIGHT COLUMNS ARE, AND WHAT THEY ARE NOT
    --------------------------------------------------
    The five "Suma ..." columns are sums of the FROZEN WEIGHTS stored on
    each row (asados.tipo_carne_weight/coccion_weight/superficie_weight/
    local_weight and participations.rol_weight — see schema.sql), not a
    breakdown of where a user's points came from. They CAN'T be that:
    config.py's FORMULA is
    "(0.6 * carne + 0.4 * coccion) * superficie * local * rol", which is
    multiplicative, so an individual variable contributes no fixed,
    separable share of the total — superficie doesn't ADD anything, it
    SCALES whatever the carne/coccion part produced. So these columns
    answer "what kind of asados has this person been at?" (high Suma
    Superficie = mostly parrilla rather than horno de barro), which is a
    genuinely useful descriptive stat. They deliberately do NOT sum to
    "Puntos Totales", and no arrangement of them would — only
    SUM(participations.points) is the real scored total.

    Users with zero participations in the filtered period are omitted
    entirely rather than listed as a row of zeros — the JOIN below does
    this naturally, and a standings table listing people who weren't
    there is noise, not information.

    Filters (?year=&semester=) and sorting (?sort=&dir=) are all plain
    GET query params, same bookmarkable-URL approach as index()'s
    filters — so a sorted, filtered view can be linked/shared as-is, and
    the <select>s can auto-submit without any JavaScript fetch().
    """
    db = get_db()

    year_filter = request.args.get("year", "").strip()
    semester_filter = request.args.get("semester", "").strip()

    # Look the sort key up in the whitelist rather than trusting it —
    # see RESUMEN_SORT_COLUMNS' own comment for why this specific lookup
    # is what keeps the ORDER BY concatenation below safe.
    sort_key = request.args.get("sort", "").strip()
    if sort_key not in RESUMEN_SORT_COLUMNS:
        sort_key = RESUMEN_DEFAULT_SORT
    # Same idea for the direction: only two literal strings can ever
    # reach the SQL, chosen by an if/else, never interpolated from input.
    # Anything that isn't an explicit "asc" falls back to
    # RESUMEN_DEFAULT_DIRECTION, so the default lives next to
    # RESUMEN_DEFAULT_SORT at the top of this file rather than being
    # hard-coded here (they're one decision: "how does this table sort
    # before anyone touches it?").
    requested_dir = request.args.get("dir", "").strip().lower()
    direction = requested_dir if requested_dir in ("asc", "desc") else RESUMEN_DEFAULT_DIRECTION
    direction_sql = "ASC" if direction == "asc" else "DESC"

    conditions = []
    params = []

    if year_filter:
        conditions.append("strftime('%Y', asados.date) = ?")
        params.append(year_filter)

    # 1st semester = months 01-06, 2nd = 07-12. "Ambos" is simply the
    # absence of this filter (an empty value), exactly like every other
    # filter in this app — no third "both" branch is needed, since not
    # filtering IS "both".
    if semester_filter == "1":
        conditions.append("strftime('%m', asados.date) <= '06'")
    elif semester_filter == "2":
        conditions.append("strftime('%m', asados.date) >= '07'")

    where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    # A plain JOIN (not the LEFT JOIN that BASE_ASADOS_QUERY uses): this
    # query filters and aggregates ON asados columns, so a participation
    # whose asado row was somehow missing has nothing to contribute to a
    # standings row anyway.
    rows = db.execute(
        f"""
        SELECT
            users.id                            AS user_id,
            users.name                          AS name,
            COUNT(participations.id)            AS participations_count,
            SUM(asados.tipo_carne_weight)       AS sum_tipo_carne,
            SUM(asados.coccion_weight)          AS sum_coccion,
            SUM(asados.superficie_weight)       AS sum_superficie,
            SUM(asados.local_weight)            AS sum_local,
            SUM(participations.rol_weight)      AS sum_rol,
            AVG(participations.points)          AS avg_points,
            SUM(participations.points)          AS total_points
        FROM participations
        JOIN users ON participations.user_id = users.id
        JOIN asados ON participations.asado_id = asados.id
        {where_clause}
        GROUP BY users.id, users.name
        ORDER BY {RESUMEN_SORT_COLUMNS[sort_key]} {direction_sql}, users.name ASC
        """,
        params,
    ).fetchall()

    # Same "only years that actually have an asado" approach as index(),
    # rather than hardcoding a range of years.
    available_years = [
        row["year"] for row in db.execute(
            "SELECT DISTINCT strftime('%Y', date) AS year FROM asados ORDER BY year DESC"
        ).fetchall()
    ]

    return render_template(
        "resumen.html",
        rows=rows,
        available_years=available_years,
        semestres=SEMESTRES,
        selected_year=year_filter,
        selected_semester=semester_filter,
        sort_key=sort_key,
        direction=direction,
        # See build_resumen_chart_data()'s own docstring for why this
        # is computed from the FULL history, not the year/semester
        # filters above (rows/available_years/etc. all respect them;
        # this deliberately doesn't).
        chart_data=build_resumen_chart_data(db),
    )


# ---------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------
if __name__ == "__main__":
    # debug=True auto-reloads the server when you edit code, and shows
    # detailed error pages — great for development, turn OFF in production.
    app.run(debug=True, host="0.0.0.0", port=5000)
