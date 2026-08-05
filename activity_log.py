# =====================================================================
# activity_log.py
# Helper functions for the "Registro de Actividad" (activity log)
# feature: who created/edited/deleted which asado, and when — see the
# activity_log / activity_log_changes tables in schema.sql for the
# reasoning behind their shape (frozen actor/asado names, ON DELETE
# SET NULL foreign keys, a separate table for field-level diffs,
# instead of one JSON/string blob column).
#
# Every function here INSERTs into the given db connection WITHOUT
# calling db.commit() itself — app.py's new_asado()/edit_asado()/
# delete_asado() call these BEFORE their own db.commit(), so a log
# entry and the asado change it describes are always part of the SAME
# transaction: either both are saved, or (if something fails first)
# neither is. Mirrors how backup_database() is called AFTER commit for
# a different reason (see CLAUDE.md) — logging is the opposite: it
# must NOT be its own separate commit, or a crash between the two
# commits could save one without the other.
# =====================================================================

from datetime import datetime


def now_timestamp():
    """Plain 'YYYY-MM-DD HH:MM:SS' timestamp — same plain-text-date
    approach the rest of this app already uses for asados.date, rather
    than SQLite's own datetime type (it doesn't really have one). Not
    just used internally here — app.py also imports this directly for
    locations.created_at, so there's exactly one place that decides
    what a "timestamp" looks like across the whole app."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log_create(db, user_id, actor_name, asado_id, asado_nombre, asado_date):
    """Records a brand-new asado. No field-level diff rows — everything
    about a new asado is "new", so comparing it against nothing isn't
    useful; the single activity_log row (action='create') already says
    who/what/when, which is the whole point."""
    db.execute(
        """
        INSERT INTO activity_log (timestamp, user_id, actor_name, asado_id, asado_nombre, asado_date, action)
        VALUES (?, ?, ?, ?, ?, ?, 'create')
        """,
        (now_timestamp(), user_id, actor_name, asado_id, asado_nombre, asado_date),
    )


def log_delete(db, user_id, actor_name, asado_id, asado_nombre, asado_date):
    """Records a deleted asado. Must be called BEFORE the actual
    DELETE FROM asados (see delete_asado() in app.py) — asado_id still
    needs to point at a real row when this INSERT runs, since
    activity_log.asado_id is a real FOREIGN KEY. Its ON DELETE SET NULL
    then nulls that reference out automatically the moment the asado
    row is actually removed a few lines later — leaving the frozen
    asado_nombre/asado_date as the only remaining record of what
    existed, which is exactly the point of freezing them."""
    db.execute(
        """
        INSERT INTO activity_log (timestamp, user_id, actor_name, asado_id, asado_nombre, asado_date, action)
        VALUES (?, ?, ?, ?, ?, ?, 'delete')
        """,
        (now_timestamp(), user_id, actor_name, asado_id, asado_nombre, asado_date),
    )


def log_edit(db, user_id, actor_name, asado_id, asado_nombre, asado_date, changes):
    """Records an edited asado, plus one activity_log_changes row per
    (field_label, old_value, new_value) tuple in `changes` — see
    diff_asado() below for how that list gets built. If `changes` is
    empty (the form was submitted but nothing actually differed — e.g.
    clicking "Guardar Cambios" with no real edits made), the action
    itself is still logged, just with zero changes rows attached."""
    cursor = db.execute(
        """
        INSERT INTO activity_log (timestamp, user_id, actor_name, asado_id, asado_nombre, asado_date, action)
        VALUES (?, ?, ?, ?, ?, ?, 'edit')
        """,
        (now_timestamp(), user_id, actor_name, asado_id, asado_nombre, asado_date),
    )
    log_id = cursor.lastrowid
    for field_label, old_value, new_value in changes:
        db.execute(
            "INSERT INTO activity_log_changes (log_id, field_label, old_value, new_value) VALUES (?, ?, ?, ?)",
            (log_id, field_label, old_value, new_value),
        )


# ---------------------------------------------------------------------
# DIFF BUILDING
# ---------------------------------------------------------------------
# Maps each asados column the edit form can change to its human-
# readable Spanish label — one place to add a new field's diff support
# later, instead of hand-writing a comparison per field inside
# diff_asado(). latitude/longitude are DELIBERATELY not included: a
# small pin-drag with the same typed location text would otherwise show
# a noisy "Latitud: -33.42 → -33.41" line with no real explanatory
# value on its own — "Ubicación" (the text field) already covers the
# meaningful case of an actual location change.
SCALAR_FIELDS = [
    ("date", "Fecha"),
    ("nombre", "Nombre"),
    ("description", "Descripción"),
    ("coccion", "Cocción"),
    ("superficie", "Superficie"),
    ("local", "Local"),
    ("location", "Ubicación"),
    ("people", "Cantidad de Personas"),
    ("total_weight", "Peso Total (kg)"),
]


def diff_asado(old_row, new_values, old_tipo_carne, new_tipo_carne, old_participants, new_participants):
    """
    Builds the list of (field_label, old_value, new_value) tuples for
    everything that actually CHANGED between an asado's state right
    before an edit and what was just submitted — used by log_edit()
    above. Fields whose value didn't change are skipped entirely, so
    the resulting log entry only ever shows what's actually different,
    not a full restatement of the whole form.

    old_row: the asados row fetched BEFORE the UPDATE (sqlite3.Row) —
        caller must fetch this first; edit_asado() deletes/replaces
        participations and asado_tipo_carne wholesale, so their old
        state has to be captured before those DELETEs too.
    new_values: dict of the newly submitted scalar fields, using the
        SAME keys as SCALAR_FIELDS above (date, nombre, description, ...).
    old_tipo_carne / new_tipo_carne: lists of tipo_carne strings.
    old_participants / new_participants: lists of "Nombre (Rol)"
        strings, already resolved from user_id to display name by the
        caller — this module has no db access to look names up itself.
    """
    changes = []

    for field_key, label in SCALAR_FIELDS:
        old_value = old_row[field_key]
        new_value = new_values.get(field_key)
        # Normalize None/"" as equivalent ("was empty" either way) so an
        # edit that happens to go from NULL to "" (or vice versa) isn't
        # reported as a change — that's not a meaningful difference to
        # a human reading the log, just an artifact of how the form
        # submitted an empty optional field.
        if (old_value or None) != (new_value or None):
            changes.append((label, old_value, new_value))

    old_tc_joined = "; ".join(old_tipo_carne)
    new_tc_joined = "; ".join(new_tipo_carne)
    if old_tc_joined != new_tc_joined:
        changes.append(("Tipo de Carne", old_tc_joined, new_tc_joined))

    # Sorted so the comparison (and the displayed text) doesn't depend
    # on submission order — adding the same two participants in a
    # different order shouldn't register as a "change".
    old_participants_joined = ", ".join(sorted(old_participants))
    new_participants_joined = ", ".join(sorted(new_participants))
    if old_participants_joined != new_participants_joined:
        changes.append(("Participantes", old_participants_joined, new_participants_joined))

    return changes
