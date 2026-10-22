# =====================================================================
# asado_record.py
# The ONE place that saves, updates and deletes an asado.
#
# An "asado record" is more than the `asados` row: it is that row PLUS
# its child rows (participations, asado_tipo_carne, asado_cortes), the
# weights frozen onto all of them, and the activity-log entry that says
# who changed it. Before v2.0.2 that knowledge was written out three
# times - in new_asado(), in edit_asado() and in seed_random_asados.py -
# and adding one child table meant touching about seven places. Now the
# routes and the seed script all go through this module:
#
#     data = asado_record.read_form(request.form)      # or build AsadoInput yourself
#     asado_id = asado_record.create(db, data, actor)  # validates, writes, logs, commits
#     asado_record.update(db, asado_id, data, actor)
#     asado_record.delete(db, asado_id, actor)
#
# Each either succeeds or raises AsadoInvalid (a Spanish, user-facing
# message, safe to show in ?error=) / AsadoNotFound - and if it raises,
# NOTHING has been written.
#
# WHAT STAYS IN THE ROUTES, on purpose: the one-shot form token (it's
# about HTTP double-submits, see consume_form_token() in app.py), CSRF,
# redirects, and the automatic backup - which runs AFTER the commit and
# must never make a save look failed (see backup_db.py).
#
# DECISIONS THIS MODULE KEEPS EXACTLY (see CLAUDE.md for the why of each):
#   * weights are FROZEN at save time; an edit re-freezes them from the
#     CURRENT config.py (an edit is a new "freezing moment");
#   * on edit, participants, tipos de carne and cortes are REPLACED
#     WHOLESALE, never diffed row by row - participation ids don't
#     survive an edit;
#   * the activity-log entry is written in the SAME transaction as the
#     change it describes, so one can never exist without the other;
#   * cortes never score.
#
# This module does NOT import app.py (same rule as every script here),
# so seed_random_asados.py and tests can use it without a web request.
# =====================================================================

from dataclasses import dataclass, field
from datetime import date as _date

from activity_log import log_create, log_edit, log_delete, diff_asado, now_timestamp
from config import (
    TIPO_CARNE_WEIGHTS, COCCION_WEIGHTS, SUPERFICIE_WEIGHTS, LOCAL_WEIGHTS, ROL_WEIGHTS,
    CATEGORIAS_CON_DESPIECE, CORTES_VACUNO,
    get_shared_weights, get_rol_weight, get_tipo_carne_weights, calculate_points,
)

# Every table whose rows belong to ONE asado and must go when it goes.
# delete() empties them before the asado row (PRAGMA foreign_keys = ON
# would refuse the other order). ADD ANY NEW CHILD TABLE OF `asados`
# HERE - and only here: the smoke test checks this tuple against
# schema.sql's foreign keys, so forgetting it fails a check instead of
# giving the first admin who deletes such an asado a 500.
# (activity_log is deliberately NOT a child: its asado_id is ON DELETE
# SET NULL, because the log must outlive the asado it describes.)
CHILD_TABLES = ("participations", "asado_tipo_carne", "asado_cortes")


class AsadoInvalid(Exception):
    """The submitted asado breaks a rule. str(error) is a Spanish
    message meant for the person who submitted it."""


class AsadoNotFound(LookupError):
    """No asado with that id in this group's database."""


@dataclass(frozen=True)
class Actor:
    """Who is making the change, for the activity log. user_id is the
    MEMBER id in this group (g.user_id), or None for something that
    isn't a person (the seed script); name is frozen into the log as
    plain text, so the entry stays readable after the member is gone."""
    user_id: object
    name: str


@dataclass
class AsadoInput:
    """
    Everything that describes one asado, as submitted. Build it with
    read_form() from a web form, or directly (seed script, tests).

    participants: list of (user_id, rol). user_id may be an int or the
        form's string; a blank/None user_id is an empty row and is
        ignored, exactly like the form's "Elegir usuario..." row.
    cortes: individual beef cuts. They're DROPPED unless one of
        tipos_carne is a category with a despiece (see _clean_cortes()).
    save_location / location_name: the asado form's "Guardar esta
        ubicación" checkbox and the name typed next to it.
    """
    date: str
    nombre: str
    tipos_carne: list
    coccion: str
    superficie: str
    local: str
    participants: list = field(default_factory=list)
    description: str = ""
    cortes: list = field(default_factory=list)
    location: str = ""
    latitude: object = None
    longitude: object = None
    people: object = None
    total_weight: object = None
    save_location: bool = False
    location_name: str = ""


# ---------------------------------------------------------------------
# READING THE FORM
# ---------------------------------------------------------------------
def parse_decimal(raw_value):
    """
    Parses a hand-typed form field into a float, accepting BOTH '.' and
    ',' as the decimal separator.

    This app's users are Spanish/Latin-American, where ',' is the
    everyday decimal separator ("2,5 kg"). Python's float() only accepts
    '.', and the browser's <input type="number"> is worse: typing "2,5"
    silently DROPS the comma and submits "25", ten times too much, with
    no error at all (confirmed by typing it into a real browser). Every
    hand-typed decimal field is therefore type="text" inputmode="decimal"
    in the templates and goes through here on the server - see CLAUDE.md,
    "Decimal input accepts ',' as well as '.'".

    Returns None for a blank/missing/unparseable value, matching how
    Werkzeug's own type=float behaves - a drop-in replacement.

    Lives here because the asado form is its main user; app.py imports
    it for /ubicaciones' coordinates too.
    """
    if raw_value is None:
        return None
    raw_value = raw_value.strip()
    if not raw_value:
        return None
    try:
        return float(raw_value.replace(",", "."))
    except ValueError:
        return None


def read_form(form):
    """
    Turns a submitted asado form (Flask's request.form) into an
    AsadoInput. Only READS: it never raises over bad values - judging
    them is create()/update()'s job, so the same rules apply whether
    data came from a form, the seed script or a test.

    A missing field reads as "" rather than raising. Before 2.0.2,
    request.form["nombre"] on a missing field gave the user a bare
    "400 Bad Request" page; now it's a friendly "Falta el nombre" error.
    """
    return AsadoInput(
        date=form.get("date", ""),
        nombre=form.get("nombre", ""),
        description=form.get("description", ""),
        # getlist(): an asado can have several Tipos de Carne / cuts /
        # participants, each submitted as a repeated field.
        tipos_carne=[tc for tc in form.getlist("tipo_carne") if tc],
        cortes=form.getlist("corte"),
        coccion=form.get("coccion", ""),
        superficie=form.get("superficie", ""),
        local=form.get("local", ""),
        location=form.get("location", ""),
        # latitude/longitude are JS-filled hidden inputs (always '.'),
        # but one function deciding "how this app reads a decimal" beats
        # two rules for two paths.
        latitude=parse_decimal(form.get("latitude")),
        longitude=parse_decimal(form.get("longitude")),
        people=form.get("people", type=int),
        total_weight=parse_decimal(form.get("total_weight")),
        participants=list(zip(form.getlist("participant_user_id"), form.getlist("participant_rol"))),
        # An UNCHECKED box (the default) means the original behaviour:
        # this location is used for THIS asado only.
        save_location=form.get("save_location") == "on",
        location_name=form.get("location_name", "").strip(),
    )


# ---------------------------------------------------------------------
# VALIDATION - runs before the first write, every time
# ---------------------------------------------------------------------
DUPLICATE_PARTICIPANT = "Un mismo usuario no puede tener más de un rol en el mismo asado."


def _clean_cortes(data):
    """
    The cuts that will actually be saved. Two rules, both deliberate:

    1. DROPPED ENTIRELY unless a category with a despiece
       (CATEGORIAS_CON_DESPIECE) is among the tipos. This happens
       legitimately: someone picks cuts, then switches Tipo de Carne
       before saving. The form keeps their picks visible in case they
       switch back; the server makes the final call.
    2. Duplicates removed PRESERVING ORDER (dict.fromkeys, not set(),
       which would scramble it). A duplicate cut means nothing, so it's
       dropped rather than rejecting the whole submission.
    """
    if not any(tc in CATEGORIAS_CON_DESPIECE for tc in data.tipos_carne):
        return []
    return list(dict.fromkeys(c for c in data.cortes if c))


def _validate(db, data):
    """
    Checks every rule BEFORE anything is written, and returns what the
    writes need: (participants, cortes), where participants is a list of
    (user_id, name, rol) for the members who actually exist.

    Until 2.0.2 the server only enforced "no duplicate participant";
    everything else trusted the browser. These rules are the server-side
    half of what the form already enforces - the same "friendly client,
    authoritative server" layering as everywhere else in this app:
      * nombre and a real YYYY-MM-DD date are required (the home page's
        year/month filters read the date with SQLite's strftime);
      * at least one Tipo de Carne - before, an asado with none was
        saved AND scored as if its carne weight were 1 (config.py's
        max(..., default=1));
      * every category must be one config.py knows - before, a tampered
        value was saved and silently scored at weight 1;
      * participant ids must be numbers (before: a 500 error);
      * the same member can't appear twice (one person can't hold two
        Roles at one asado).
    Checked against the real data before adding: every stored value was
    already a known config.py value, so no existing asado breaks.
    """
    if not data.nombre.strip():
        raise AsadoInvalid("Falta el nombre del asado.")
    try:
        _date.fromisoformat(data.date)
    except (TypeError, ValueError):
        raise AsadoInvalid("Falta la fecha del asado, o no es válida.")
    if not data.tipos_carne:
        raise AsadoInvalid("Elegí al menos un Tipo de Carne.")
    for tc in data.tipos_carne:
        if tc not in TIPO_CARNE_WEIGHTS:
            raise AsadoInvalid(f"Tipo de Carne desconocido: {tc}.")
    for label, value, known in (("Cocción", data.coccion, COCCION_WEIGHTS),
                                ("Superficie", data.superficie, SUPERFICIE_WEIGHTS),
                                ("Local", data.local, LOCAL_WEIGHTS)):
        if value not in known:
            raise AsadoInvalid(f"Valor de {label} desconocido: {value or '(vacío)'}.")

    cortes = _clean_cortes(data)
    for corte in cortes:
        if corte not in CORTES_VACUNO:
            raise AsadoInvalid(f"Corte desconocido: {corte}.")

    chosen = []  # (user_id, rol) for every non-blank row
    for raw_id, rol in data.participants:
        if raw_id is None or str(raw_id).strip() == "":
            continue  # an empty "Elegir usuario..." row
        try:
            user_id = int(str(raw_id).strip())
        except ValueError:
            raise AsadoInvalid("Participante inválido.")
        if rol not in ROL_WEIGHTS:
            raise AsadoInvalid(f"Rol desconocido: {rol or '(vacío)'}.")
        chosen.append((user_id, rol))
    if len(chosen) != len({uid for uid, _ in chosen}):
        raise AsadoInvalid(DUPLICATE_PARTICIPANT)

    participants = []
    for user_id, rol in chosen:
        row = db.execute("SELECT id, name FROM users WHERE id = ?", (user_id,)).fetchone()
        # An id that isn't a member of this group is SKIPPED, not an
        # error - the original behaviour, kept: the dropdown only offers
        # real members, so this only happens with a tampered or stale
        # form, and losing one bogus row beats refusing the whole asado.
        if row is not None:
            participants.append((user_id, row["name"], rol))
    return participants, cortes


# ---------------------------------------------------------------------
# WRITING - shared by create() and update()
# ---------------------------------------------------------------------
def _write_children(db, asado_id, data, participants, cortes):
    """Inserts the asado's child rows, freezing each one's weight NOW
    (see schema.sql: config.py's weights may change later, and stored
    points must keep the weights that produced them)."""
    # Every selected Tipo de Carne with its OWN weight, not just the
    # winning max on the asados row - so a later look shows WHY it won.
    tipo_carne_weights = get_tipo_carne_weights(data.tipos_carne)
    for tc in data.tipos_carne:
        db.execute(
            "INSERT INTO asado_tipo_carne (asado_id, tipo_carne, tipo_carne_weight) VALUES (?, ?, ?)",
            (asado_id, tc, tipo_carne_weights[tc]),
        )
    # Cuts: descriptive only - no weight, nothing here touches points.
    for corte in cortes:
        db.execute("INSERT INTO asado_cortes (asado_id, corte) VALUES (?, ?)", (asado_id, corte))
    # Participants: points differ per person because Rol does.
    for user_id, _name, rol in participants:
        db.execute(
            "INSERT INTO participations (asado_id, user_id, rol, rol_weight, points) VALUES (?, ?, ?, ?, ?)",
            (asado_id, user_id, rol, get_rol_weight(rol),
             calculate_points(data.tipos_carne, data.coccion, data.superficie, data.local, rol)),
        )


def maybe_save_location(db, user_id, name, address, latitude, longitude):
    """
    The asado form's "Guardar esta ubicación" checkbox: adds this
    address to the reusable pool (the `locations` table) so it appears in
    the "Ubicación guardada" dropdown next time. Silently does nothing if:
      - `name` is blank;
      - address/latitude/longitude are missing - locations.* are NOT
        NULL, and the asado form's location can be free-typed without
        ever being geocoded; a pool entry without coordinates is
        useless, and the asado itself must still save;
      - a location with that name (case-insensitive) already exists -
        renaming/fixing saved locations is what /ubicaciones is for.
    """
    if not name or not address or latitude is None or longitude is None:
        return
    if db.execute("SELECT 1 FROM locations WHERE LOWER(name) = LOWER(?)", (name,)).fetchone():
        return
    db.execute(
        "INSERT INTO locations (name, address, latitude, longitude, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (name, address, latitude, longitude, user_id, now_timestamp()),
    )


def _scalar_values(data, shared_weights):
    """The asados row's columns, in one fixed order shared by the
    INSERT and the UPDATE below - one list, so the two can't drift."""
    return (data.date, data.nombre, data.description, data.coccion,
            data.superficie, data.local, data.location, data.latitude, data.longitude,
            data.people, data.total_weight,
            shared_weights["carne"], shared_weights["coccion"],
            shared_weights["superficie"], shared_weights["local"])


_SCALAR_COLUMNS = ("date", "nombre", "description", "coccion", "superficie", "local",
                   "location", "latitude", "longitude", "people", "total_weight",
                   "tipo_carne_weight", "coccion_weight", "superficie_weight", "local_weight")


# ---------------------------------------------------------------------
# THE INTERFACE
# ---------------------------------------------------------------------
def create(db, data, actor):
    """
    Saves a NEW asado with all its child rows, logs it, and commits.
    Returns the new asado's id. Raises AsadoInvalid (nothing written).
    """
    participants, cortes = _validate(db, data)
    # "carne" is the MAX weight among the selected Tipos de Carne - the
    # one that feeds the formula (multiple types never stack).
    shared_weights = get_shared_weights(data.tipos_carne, data.coccion, data.superficie, data.local)
    placeholders = ", ".join("?" for _ in _SCALAR_COLUMNS)
    cursor = db.execute(
        f"INSERT INTO asados ({', '.join(_SCALAR_COLUMNS)}) VALUES ({placeholders})",
        _scalar_values(data, shared_weights),
    )
    asado_id = cursor.lastrowid
    _write_children(db, asado_id, data, participants, cortes)
    # Before commit(): the log entry and the asado are one transaction.
    log_create(db, actor.user_id, actor.name, asado_id, data.nombre, data.date)
    if data.save_location:
        maybe_save_location(db, actor.user_id, data.location_name, data.location, data.latitude, data.longitude)
    db.commit()
    return asado_id


def update(db, asado_id, data, actor):
    """
    Replaces an existing asado's details and ALL its child rows with
    `data`, re-freezing every weight from the CURRENT config.py, logs
    exactly which fields changed, and commits.
    Raises AsadoNotFound or AsadoInvalid (nothing written either way).
    """
    old_asado = db.execute("SELECT * FROM asados WHERE id = ?", (asado_id,)).fetchone()
    if old_asado is None:
        raise AsadoNotFound(asado_id)
    participants, cortes = _validate(db, data)

    # The "before" picture for the activity-log diff, captured BEFORE the
    # wholesale replace below deletes the old child rows.
    old_tipos = [r["tipo_carne"] for r in db.execute(
        "SELECT tipo_carne FROM asado_tipo_carne WHERE asado_id = ? ORDER BY id", (asado_id,))]
    old_cortes = [r["corte"] for r in db.execute(
        "SELECT corte FROM asado_cortes WHERE asado_id = ? ORDER BY id", (asado_id,))]
    old_participants = [f"{r['name']} ({r['rol']})" for r in db.execute(
        """SELECT users.name, participations.rol FROM participations
           JOIN users ON participations.user_id = users.id
           WHERE participations.asado_id = ? ORDER BY participations.id""", (asado_id,))]

    shared_weights = get_shared_weights(data.tipos_carne, data.coccion, data.superficie, data.local)
    assignments = ", ".join(f"{col} = ?" for col in _SCALAR_COLUMNS)
    db.execute(f"UPDATE asados SET {assignments} WHERE id = ?",
               _scalar_values(data, shared_weights) + (asado_id,))
    for table in CHILD_TABLES:  # wholesale replace, see the header
        db.execute(f"DELETE FROM {table} WHERE asado_id = ?", (asado_id,))
    _write_children(db, asado_id, data, participants, cortes)

    changes = diff_asado(
        old_asado,
        {"date": data.date, "nombre": data.nombre, "description": data.description,
         "coccion": data.coccion, "superficie": data.superficie, "local": data.local,
         "location": data.location, "people": data.people, "total_weight": data.total_weight},
        old_tipos, data.tipos_carne,
        old_participants, [f"{name} ({rol})" for _uid, name, rol in participants],
        old_cortes, cortes,
    )
    log_edit(db, actor.user_id, actor.name, asado_id, data.nombre, data.date, changes)
    if data.save_location:
        maybe_save_location(db, actor.user_id, data.location_name, data.location, data.latitude, data.longitude)
    db.commit()


def delete(db, asado_id, actor):
    """
    Permanently deletes an asado and every child row, logs it, commits.
    Raises AsadoNotFound. (Who may delete - admins only - is the
    route's decision, not this module's.)
    """
    asado = db.execute("SELECT id, nombre, date FROM asados WHERE id = ?", (asado_id,)).fetchone()
    if asado is None:
        raise AsadoNotFound(asado_id)
    # Log FIRST, while asado_id still points at a real row: activity_log
    # .asado_id is a real foreign key, nulled by ON DELETE SET NULL only
    # once the asado row below is gone.
    log_delete(db, actor.user_id, actor.name, asado_id, asado["nombre"], asado["date"])
    for table in CHILD_TABLES:
        db.execute(f"DELETE FROM {table} WHERE asado_id = ?", (asado_id,))
    db.execute("DELETE FROM asados WHERE id = ?", (asado_id,))
    db.commit()
