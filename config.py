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
    "Bifes Vacuno o similar": 0.7,
    "Chuleta de Cerdo o similar": 0.3,
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
    "Kanka": 0.8,
    "Plancha o Sartén": 0.7,
    "Disco": 0.5,
    "Horno de barro": 0.3,
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


def calculate_points(tipo_carne, coccion, superficie, local, rol):
    """
    Calculates the Points for ONE participant of ONE asado, by
    EVALUATING the FORMULA string above as real math.

    THIS IS THE ONLY PLACE THE FORMULA IS CALCULATED. The browser asks
    this function for the answer (via the /api/points route in app.py),
    and it ALSO reads the same FORMULA string for the on-screen preview
    text — so editing FORMULA above is the ONLY change ever needed,
    anywhere in the project, no matter how you restructure the algebra.

    Parameters are the CATEGORY NAMES (strings, e.g. "Vacío"), and this
    function looks up their numeric weight from the dictionaries above
    before evaluating the formula.

    Returns a float (the calculated points).
    """
    # .get(key, default) looks up the weight; if the category isn't found
    # in our dictionary (e.g. a typo), it falls back to 1 instead of
    # crashing the whole app. This is a safety net for Phase 1.
    carne_w = TIPO_CARNE_WEIGHTS.get(tipo_carne, 1)
    coccion_w = COCCION_WEIGHTS.get(coccion, 1)
    superficie_w = SUPERFICIE_WEIGHTS.get(superficie, 1)
    local_w = LOCAL_WEIGHTS.get(local, 1)
    rol_w = ROL_WEIGHTS.get(rol, 1)

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
    variables = {
        "carne": carne_w,
        "coccion": coccion_w,
        "superficie": superficie_w,
        "local": local_w,
        "rol": rol_w,
    }
    points = eval(FORMULA, {"__builtins__": {}}, variables)

    # round() to 2 decimals just for a cleaner number to display/store.
    return round(points, 2)
