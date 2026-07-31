# =====================================================================
# config.py
# This file centralizes all the "tunable" values used to calculate
# Points, so you can edit them in ONE place instead of hunting through
# the app's logic. Think of it as a settings panel for the formula.
#
# CURRENT FORMULA:
#   Points = (CARNE_COEF * TipoCarne + COCCION_COEF * Coccion) * Superficie * Local * Rol
#
# Each variable on the right side is a CATEGORY (like "Vacío" or
# "Parrilla"), not a number — so below we assign a numeric WEIGHT to
# each possible category value. These are placeholder numbers you
# should feel free to rename/replace with your real categories.
# =====================================================================

# --- The two coefficients in the formula, as their own named values.
# Pulling these out (instead of leaving them as bare numbers inside the
# formula below) means we can also SEND them to the browser as data, so
# the live preview can label things without hardcoding numbers twice.
CARNE_COEF = 0.6
COCCION_COEF = 0.4

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
    Calculates the Points for ONE participant of ONE asado.

    THIS IS THE ONLY PLACE THE FORMULA IS CALCULATED. The browser asks
    this function for the answer (via the /api/points route in app.py)
    instead of re-implementing the math in JavaScript — so changing the
    formula's weights, coefficients, OR STRUCTURE here is the ONLY edit
    needed, anywhere in the project.

    Parameters are the CATEGORY NAMES (strings, e.g. "Vacío"), and this
    function looks up their numeric weight from the dictionaries above
    before doing the math.

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

    points = (CARNE_COEF * carne_w + COCCION_COEF * coccion_w) * superficie_w * local_w * rol_w

    # round() to 2 decimals just for a cleaner number to display/store.
    return round(points, 2)
