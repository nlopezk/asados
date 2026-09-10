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


# =====================================================================
# NON-SCORING DATA BELOW THIS LINE
# =====================================================================
# Everything from here down is DESCRIPTIVE ONLY. Unlike the *_WEIGHTS
# dicts above, none of it has a number, none of it is read by FORMULA,
# calculate_points(), get_shared_weights() or get_rol_weight(), and
# none of it can change anyone's points — not now, and not by accident
# later. Adding fifty cuts to CORTES_VACUNO below leaves every stored
# `points` value in the database byte-identical.
#
# This is the same separation schema.sql makes physically: the
# asado_cortes table deliberately has NO `corte_weight` column, where
# asado_tipo_carne has one. Two files, one rule — if you ever find
# yourself wanting to give a corte a number, that's a deliberate new
# decision with its own migration, not something to slip in here.
# =====================================================================

# Which Tipo de Carne category opens the cow diagram / cut picker.
#
# A LIST, not a single string, deliberately: adding a second beef
# category is then a one-line edit with zero code or schema impact.
# That matters here specifically — "Bifes Vacuno o similar" is actually
# this group's MOST-used category (117 of 247 recorded types, 47%, vs.
# 86 for the one below), and it's beef from the same animal, so it's
# the obvious candidate if the cow ever feels like it shows up too
# rarely. Scoped to just the one for now, at the user's explicit call.
CATEGORIAS_CON_DESPIECE = [
    "Corte de Vacuno (Lomo, Tira, Vacío)",
]

# Every individual beef cut, in the order it appears in the picker.
#   key   = the cut's display name, exactly as it is STORED in
#           asado_cortes.corte and shown on screen (the full text, not
#           a slug -- same convention as asado_tipo_carne.tipo_carne).
#   value = the `data-corte` of the matching region in the cow diagram
#           (templates/_cow_diagram.html), or None for a cut with no
#           drawn region.
#
# THE SLUGS ARE THE DRAWING'S OWN ELEMENT IDS, COPIED VERBATIM --
# underscores and all, including the slightly-misspelled
# "estomagillo_palanca". That is deliberate: the SVG was hand-drawn in
# Inkscape, and matching it exactly means the artwork can be reopened,
# edited and re-exported without anyone having to remember a renaming
# step in between. A prettier slug here would be one more thing to keep
# in sync, and a mismatch fails SILENTLY -- the region simply never
# lights up, with nothing in the console to say why.
#
# The five None entries are cuts with no region on the diagram, and
# they are still FULLY SELECTABLE from the dropdown -- the dropdown is
# the complete list, the diagram is a visual shortcut into it. Two of
# them can never be drawn on a side view because they are internal
# cuts (Asado Carnicero, which the reference chart itself labels
# "Corte Interno", and Entrana, the diaphragm). The other three simply
# were not on the chart the diagram was drawn from. Malaya WAS one of
# them -- it appears on four of the five reference charts and is this
# group's 5th most-used cut name -- and it got its region in 1.7.1,
# which is the worked example of how cheap that is: draw the shape in
# vaca_svg.svg, re-run build_cow_partial.py, swap the None here for
# the new id. No other code changed.
#
# One region covers TWO cuts: "estomagillo_palanca". The reference
# chart groups them ("Estomaguillo, Coluda y Palanca"), so the drawing
# does too. Palanca owns the region because it's the more-used name of
# the two (3 mentions vs 1); Estomaguillo stays dropdown-only. Hover
# and click therefore agree -- the region says "Palanca" and adds
# Palanca -- rather than being ambiguous about which one you get.
#
# Names are CHILEAN, and that is not incidental. This group's own 239
# asado titles are full of Punta de Ganso, Lomo Vetado, Punta Picana,
# Malaya, Plateada, Tapabarriga, Sobrecostilla, Palanca and Abastero --
# not Argentine "Bife de Chorizo", not US "Ribeye"/"Brisket". If you
# extend this list, stay in that vocabulary; a well-meaning swap to a
# US or Argentine cut chart would be wrong for these users.
#
# The order here is ANATOMICAL, front to back, with section comments
# matching the groupings a butcher's chart uses -- which is what makes
# this list readable side by side with the drawing when you're checking
# that every region has a home.
#
# It is NOT the order anyone sees. The picker and the reference page
# both sort alphabetically (app.py's cortes_alfabeticos()), because
# anatomical order is useless for finding a cut whose name you already
# know. Storage order and display order are deliberately different; if
# you reorder this list, nothing on screen moves.
CORTES_VACUNO = {
    # --- Cuarto delantero: cuello, paleta, pecho ---
    "Huachalomo":         "huachalomo",
    "Cogote":             "cogote",
    "Charchas":           "charchas",
    "Punta Paleta":       "punta_paleta",
    "Posta Paleta":       "posta_paleta",
    "Choclillo":          "choclillo",
    "Tapapecho":          "tapa_pecho",
    "Lagarto de Mano":    "lagarto_mano",
    # --- Lomo (la linea del espinazo) ---
    "Lomo Vetado":        "lomo_vetado",
    "Lomo Liso":          "lomo_liso",
    "Filete":             "filete",
    # --- Costillar y falda ---
    "Sobrecostilla":      "sobrecostilla",
    "Asado de Tira":      "asado_tira",
    "Plateada":           "plateada",
    "Pollo Barriga":      "pollo_barriga",
    "Malaya":             "malaya",
    "Tapabarriga":        "tapa_barriga",
    "Palanca":            "estomagillo_palanca",
    "Coludas":            "coludas",
    # --- Cuarto trasero: pierna y cadera ---
    "Punta Picana":       "punta_picana",
    "Asiento":            "asiento",
    "Ganso":              "ganso",
    "Punta de Ganso":     "punta_ganso",
    "Pollo Ganso":        "pollo_ganso",
    "Posta Rosada":       "posta_rosada",
    "Abastero":           "abastero",
    # --- Patas ---
    "Osobuco de Mano":    "osobuco_mano",
    "Osobuco de Pierna":  "osobuco_pierna",
    # --- Sin region en el diagrama (ver el comentario de arriba) ---
    "Entraña":       None,
    "Estomaguillo":       None,
    "Posta Negra":        None,
    "Asado Carnicero":    None,
}

# A small icon for each NON-beef Tipo de Carne, shown beside (or
# instead of) the cow. Emoji rather than eight sourced image files:
# zero new assets, zero licences to check, nothing to cache-bust, and
# it matches the UI language this app already speaks (the navbar runs
# on 🔥📋📍⚙️🕓🏆).
#
# Emoji render differently across Android/iOS/Windows, and a few of
# these are genuinely ambiguous on their own (🍖 vs 🥩 vs 🐖). So the
# icon NEVER carries the meaning alone — every one is rendered with a
# visible caption and a title tooltip. Same rule CLAUDE.md already
# states for the per-user colour dots: the dot supplements the name,
# it never replaces it.
#
# Every key here must exist in TIPO_CARNE_WEIGHTS above. The beef
# categories in CATEGORIAS_CON_DESPIECE deliberately have no entry —
# they get the full diagram instead.
ICONOS_TIPO_CARNE = {
    "Cordero": "🐑",
    "Corte de Cerdo": "🐖",
    "Bifes Vacuno o similar": "🥩",
    "Chuleta de Cerdo o similar": "🍖",
    "Pollo": "🍗",
    "Embutidos (Chori, Morcilla)": "🌭",
    "Hamburguesa casera": "🍔",
    "Pescados": "🐟",
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
