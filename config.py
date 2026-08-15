# =====================================================================
# config.py
# This file centralizes all the "tunable" values used to calculate
# Points, so you can edit them in ONE place instead of hunting through
# the app's logic. Think of it as a settings panel for the formula.
#
# THE FORMULA IS WRITTEN BELOW AS ACTUAL TEXT (see FORMULA), using the
# 5 variable names: carne, coccion, superficie, local, rol. You can
# rewrite it into ANY algebraic shape you want — different groupings,
# different coefficients, extra terms — and that single line is the
# ONLY thing you ever need to change. Both the real calculation AND
# the live on-screen preview read from this exact same string, so they
# can never disagree with each other.
#
# Example shapes you could paste in here later:
#   "(0.6 * carne + 0.4 * coccion) * superficie * local * rol"
#   "carne + (0.4 * coccion + 0.3 * superficie) * local * rol"
# =====================================================================

FORMULA = "(0.6 * carne + 0.4 * coccion) * superficie * local * rol"

# Human-readable label for each variable used in FORMULA. Used ONLY for
# display (the live preview on the "New Asado" page shows the formula
# using these names instead of the raw variable names above). Keeping
# this here too means renaming a label is also a single, one-place edit.
VARIABLE_LABELS = {
    "carne": "Tipo Carne",
    "coccion": "Tipo Cocción",
    "superficie": "Superficie",
    "local": "Local",
    "rol": "Rol",
}

# --- Weights for "Tipo de Carne" (type of meat) -----------------------
TIPO_CARNE_WEIGHTS = {
    "Corte de Vacuno (Lomo, Tira, Vacío)": 1,
    "Cordero": 1,
    "Corte de Cerdo": 0.7,
    "Bifes Vacuno o similar": 1,
    "Chuleta de Cerdo o similar": 0.7,
    "Pollo": 0.3,
    "Embutidos (Chori, Morcilla)": 0.3,
    "Hamburguesa casera": 0.3,
    "Pescados": 0.2
}

# --- Weights for "Cocción" (cooking method) ---------------------------
COCCION_WEIGHTS = {
    "Leña y/o Carbón": 1,
    "Ahumado": 0.8,
    "Gas": 0.7
}

# --- Multipliers for "Superficie" (cooking surface) --------------------
SUPERFICIE_WEIGHTS = {
    "Parrilla": 1,
    "Espada estática": 1,
    "Kanka": 1,
    "Plancha o Sartén": 0.7,
    "Disco": 0.5,
    "Horno de barro": 0,
}

# --- Multipliers for "Local" (where it happened) -----------------------
LOCAL_WEIGHTS = {
    "Casa o Particular": 1,
    "Restaurante o Parrilla comercial": 0.5,
}

# --- Multipliers for "Rol" (the participant's role) ---------------------
ROL_WEIGHTS = {
    "Asador": 1,          # the person who actually grills gets the most points
    "Co-parrillero": 0.8,   # the host
    "Comensal": 0.7         # helper
}


def get_tipo_carne_weights(tipo_carne_list):
    """
    Looks up the weight for EVERY selected "Tipo de Carne" (an asado can
    have more than one, minimum one — e.g. both "Cordero" and "Pollo" at
    the same event), returned as a {category_name: weight} dict so the
    caller can freeze each one individually (see schema.sql's
    asado_tipo_carne table) while ALSO knowing which one is the max.

    .get(key, default) looks up the weight; if a category isn't found in
    our dictionary (e.g. a typo), it falls back to 1 instead of crashing
    the whole app. This is a safety net for Phase 1.
    """
    return {tc: TIPO_CARNE_WEIGHTS.get(tc, 1) for tc in tipo_carne_list}


def get_shared_weights(tipo_carne_list, coccion, superficie, local):
    """
    Looks up the 4 weights that are shared by every participant of the
    SAME asado (everything except Rol, which is per-participant — see
    get_rol_weight() below). Split out from calculate_points() so both
    it AND app.py can use the exact same lookups: app.py needs these
    numbers on their own to FREEZE them onto the asados row at creation
    time (see schema.sql's tipo_carne_weight/coccion_weight/etc.
    columns) — otherwise, if a weight in this file changes later,
    there'd be no record of what weight actually produced an old
    entry's stored points, even though the points themselves stay
    frozen.

    "carne" specifically is the MAX weight across every selected Tipo de
    Carne in tipo_carne_list (a deliberate rule: multiple meat types
    don't stack or average, only the single biggest one counts toward
    points) — max(..., default=1) falls back the same safe way as the
    .get(key, default) lookups below if tipo_carne_list somehow ends up
    empty (shouldn't happen — the form requires at least one — but this
    avoids a crash rather than assuming it can't).
    """
    tipo_carne_weights = get_tipo_carne_weights(tipo_carne_list)
    return {
        "carne": max(tipo_carne_weights.values(), default=1),
        "coccion": COCCION_WEIGHTS.get(coccion, 1),
        "superficie": SUPERFICIE_WEIGHTS.get(superficie, 1),
        "local": LOCAL_WEIGHTS.get(local, 1),
    }


def get_rol_weight(rol):
    """The one weight that's per-participant rather than per-asado (see
    get_shared_weights() above) — frozen onto participations.rol_weight
    at creation time for the same reason."""
    return ROL_WEIGHTS.get(rol, 1)


def calculate_points(tipo_carne_list, coccion, superficie, local, rol):
    """
    Calculates the Points for ONE participant of ONE asado, by
    EVALUATING the FORMULA string above as real math.

    THIS IS THE ONLY PLACE THE FORMULA IS CALCULATED. The browser asks
    this function for the answer (via the /api/points route in app.py),
    and it ALSO reads the same FORMULA string for the on-screen preview
    text — so editing FORMULA above is the ONLY change ever needed,
    anywhere in the project, no matter how you restructure the algebra.

    tipo_carne_list is a LIST of category names (an asado can have more
    than one meat type — only the highest-weight one counts, see
    get_shared_weights() above); coccion/superficie/local/rol are each a
    single CATEGORY NAME (string, e.g. "Disco"). This function looks up
    their numeric weight from the dictionaries above before evaluating
    the formula.

    Returns a float (the calculated points).
    """
    variables = get_shared_weights(tipo_carne_list, coccion, superficie, local)
    variables["rol"] = get_rol_weight(rol)

    # eval() runs a STRING as if it were real Python code. We give it a
    # small "variables" dictionary as its only vocabulary — it can ONLY
    # see carne/coccion/superficie/local/rol and basic math operators
    # (+, -, *, /, parentheses), nothing else. The empty "__builtins__"
    # blocks access to anything dangerous (like file access) as an
    # extra safety habit — though note this is safe here specifically
    # because FORMULA is a line YOU write in your own source code, never
    # something typed by a website visitor. eval() would be dangerous
    # if it ran text submitted through a web form; it's not dangerous
    # here because the text only ever comes from this file.
    points = eval(FORMULA, {"__builtins__": {}}, variables)

    # round() to 2 decimals just for a cleaner number to display/store.
    return round(points, 2)
