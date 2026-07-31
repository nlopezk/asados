# =====================================================================
# seed_random_asados.py
# A small command-line script (NOT a web page) that fills the database
# with X randomly-generated asados + participations, so you can try out
# filters, Base de Asados, CSV export, etc. without typing in real data
# by hand every time.
#
# It reuses the SAME weight-lookup helpers app.py uses when you submit
# the real "New Asado" form (get_shared_weights/get_rol_weight/
# calculate_points from config.py), so the random rows end up with
# realistic, correctly-frozen points and weights — not fake numbers.
#
# It does NOT touch existing data: it only INSERTs new rows on top of
# whatever's already in the database (unlike init_db(), which wipes
# everything). Safe to run more than once if you want even more data.
#
# REQUIRES: the database already created (init_db()) and at least one
# user account already created (create_user.py) — random asados are
# assigned to your EXISTING users, never fake/made-up ones, since
# participants must be registered accounts (see CLAUDE.md).
#
# USAGE (from the project folder):
#   python seed_random_asados.py <count>
#
# Example:
#   python seed_random_asados.py 15
# =====================================================================

import sys
import random
import sqlite3
from datetime import date, timedelta

from config import (
    TIPO_CARNE_WEIGHTS, COCCION_WEIGHTS, SUPERFICIE_WEIGHTS, LOCAL_WEIGHTS,
    ROL_WEIGHTS, get_shared_weights, get_rol_weight, calculate_points,
)

DATABASE = "asados.db"

# A handful of fun combinations to build a random-ish "Nombre Asado"
# from, e.g. "Asado Legendario". Purely cosmetic — real users type
# whatever they want here, this just needs to look plausible.
NAME_ADJECTIVES = [
    "Épico", "Legendario", "Improvisado", "Histórico", "Clásico",
    "Espectacular", "Inolvidable", "Tranquilo", "Descontrolado", "Familiar",
]
NAME_NOUNS = ["Asado", "Junte", "Parrillada", "Comilona", "Reunión", "Festejo"]

# A few real-ish Santiago locations to pick from, so the map/location
# fields aren't always empty. (location text, latitude, longitude)
SAMPLE_LOCATIONS = [
    ("Providencia, Santiago, Chile", -33.4260, -70.6089),
    ("Ñuñoa, Santiago, Chile", -33.4570, -70.5990),
    ("Las Condes, Santiago, Chile", -33.4089, -70.5693),
    ("La Reina, Santiago, Chile", -33.4460, -70.5350),
    ("Vitacura, Santiago, Chile", -33.3820, -70.5730),
]


def random_date_within_last_years(years=2):
    """A random YYYY-MM-DD string, somewhere in the last `years` years up to today."""
    days_back = random.randint(0, 365 * years)
    return (date.today() - timedelta(days=days_back)).isoformat()


def seed_random_asados(count):
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row

    user_ids = [row["id"] for row in conn.execute("SELECT id FROM users").fetchall()]
    if not user_ids:
        print("Error: no users exist yet. Create at least one with create_user.py first.")
        conn.close()
        return

    total_participations = 0

    for _ in range(count):
        tipo_carne = random.choice(list(TIPO_CARNE_WEIGHTS.keys()))
        coccion = random.choice(list(COCCION_WEIGHTS.keys()))
        superficie = random.choice(list(SUPERFICIE_WEIGHTS.keys()))
        local = random.choice(list(LOCAL_WEIGHTS.keys()))

        # Same lookup helper app.py uses — keeps the "weights are looked
        # up and frozen once, at creation time" behavior consistent for
        # seeded data too (see the comment on these columns in schema.sql).
        shared_weights = get_shared_weights(tipo_carne, coccion, superficie, local)

        # Location is optional in the real form too, so leave it empty
        # about a third of the time rather than always filling it in.
        if random.random() < 0.7:
            location, latitude, longitude = random.choice(SAMPLE_LOCATIONS)
        else:
            location, latitude, longitude = "", None, None

        nombre = f"{random.choice(NAME_ADJECTIVES)} {random.choice(NAME_NOUNS)}"

        cursor = conn.execute(
            """
            INSERT INTO asados
                (date, nombre, description, tipo_carne, coccion,
                 superficie, local, location, latitude, longitude, people, total_weight,
                 tipo_carne_weight, coccion_weight, superficie_weight, local_weight)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                random_date_within_last_years(), nombre, "Asado de prueba generado automáticamente.",
                tipo_carne, coccion, superficie, local, location, latitude, longitude,
                random.randint(4, 20), round(random.uniform(2.0, 12.0), 1),
                shared_weights["carne"], shared_weights["coccion"],
                shared_weights["superficie"], shared_weights["local"],
            ),
        )
        asado_id = cursor.lastrowid

        # Between 1 participant and everyone you have registered, each
        # user appearing at most once (random.sample never repeats).
        num_participants = random.randint(1, len(user_ids))
        participant_ids = random.sample(user_ids, num_participants)

        for user_id in participant_ids:
            rol = random.choice(list(ROL_WEIGHTS.keys()))
            rol_weight = get_rol_weight(rol)
            points = calculate_points(tipo_carne, coccion, superficie, local, rol)

            conn.execute(
                """
                INSERT INTO participations (asado_id, user_id, rol, rol_weight, points)
                VALUES (?, ?, ?, ?, ?)
                """,
                (asado_id, user_id, rol, rol_weight, points),
            )
            total_participations += 1

    conn.commit()
    conn.close()
    print(f"Created {count} random asados with {total_participations} total participations.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python seed_random_asados.py <count>")
        sys.exit(1)

    try:
        count_arg = int(sys.argv[1])
    except ValueError:
        print("Error: <count> must be a whole number.")
        sys.exit(1)

    if count_arg < 1:
        print("Error: <count> must be at least 1.")
        sys.exit(1)

    seed_random_asados(count_arg)
