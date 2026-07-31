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
from flask import Flask, render_template, request, redirect, url_for, g, jsonify
from config import (
    calculate_points, TIPO_CARNE_WEIGHTS, COCCION_WEIGHTS, SUPERFICIE_WEIGHTS,
    LOCAL_WEIGHTS, ROL_WEIGHTS, CARNE_COEF, COCCION_COEF,
)

DATABASE = "asados.db"  # the SQLite database is just a single file on disk

app = Flask(__name__)  # __name__ tells Flask where this file lives, for finding templates/static


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
# ROUTES
# ---------------------------------------------------------------------

@app.route("/")
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
        # The form sends parallel lists: participant_username[] and participant_rol[]
        # (multiple people can be added dynamically in the HTML form).
        usernames = request.form.getlist("participant_username")
        roles = request.form.getlist("participant_rol")

        for username, rol in zip(usernames, roles):
            username = username.strip()
            if not username:
                continue  # skip empty rows

            # Find the user, or create them if they don't exist yet
            # (keeps Phase 1 simple — no login required to "exist" as a user).
            user_row = db.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()

            if user_row is None:
                user_cursor = db.execute(
                    "INSERT INTO users (username) VALUES (?)", (username,)
                )
                user_id = user_cursor.lastrowid
            else:
                user_id = user_row["id"]

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
        "coefficients": {"carne": CARNE_COEF, "coccion": COCCION_COEF},
    }

    return render_template(
        "new_asado.html",
        tipo_carne_options=TIPO_CARNE_WEIGHTS.keys(),
        coccion_options=COCCION_WEIGHTS.keys(),
        superficie_options=SUPERFICIE_WEIGHTS.keys(),
        local_options=LOCAL_WEIGHTS.keys(),
        rol_options=ROL_WEIGHTS.keys(),
        weights=weights,
    )


@app.route("/asado/<int:asado_id>")
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
