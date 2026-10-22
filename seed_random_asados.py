# =====================================================================
# seed_random_asados.py
# A small command-line script (NOT a web page) that fills the database
# with X randomly-generated asados + participations, so you can try out
# filters, Base de Asados, CSV export, etc. without typing in real data
# by hand every time.
#
# Each random asado is saved through asado_record.create() — the SAME
# module the real "Añadir Asado" form uses — so the rows get the same
# validation, correctly-frozen points and weights, child rows and
# activity-log entry as a real submission. (Before 2.1.0 this script
# had its own copy of the INSERTs, which had already drifted: it wrote
# no cortes and no activity log.)
#
# It does NOT touch existing data: it only INSERTs new rows on top of
# whatever's already in the group's database. Safe to run more than
# once if you want even more data.
#
# ⚠️ It writes into ONE GROUP'S REAL DATABASE — the group you name.
# Random asados count in that group's standings like real ones. Point it
# at a throwaway test group (`python manage_groups.py create prueba ...`),
# never at a group whose standings matter. That's why the group is a
# REQUIRED argument rather than defaulting to anything: before v2.0 this
# script silently wrote into the only database there was.
#
# REQUIRES: the group already created (manage_groups.py) with at least
# one member — random asados are assigned to that group's EXISTING
# members, never fake/made-up ones, since participants must be
# registered accounts (see CLAUDE.md).
#
# USAGE (from the project folder):
#   python seed_random_asados.py <group-slug> <count>
#
# Example:
#   python seed_random_asados.py prueba 15
# =====================================================================

import sys
import random
from datetime import date, timedelta

import asado_record
from config import (
    TIPO_CARNE_WEIGHTS, COCCION_WEIGHTS, SUPERFICIE_WEIGHTS, LOCAL_WEIGHTS,
    ROL_WEIGHTS, CATEGORIAS_CON_DESPIECE, CORTES_VACUNO,
)

from accounts import ACCOUNTS_DATABASE, GROUPS_DIR, connect_existing, find_group_by_slug, group_db_path

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


def seed_random_asados(group_slug, count):
    accounts_db = connect_existing(ACCOUNTS_DATABASE)
    try:
        group = find_group_by_slug(accounts_db, group_slug)
    finally:
        accounts_db.close()
    if group is None:
        print(f"Error: no group with slug '{group_slug}' (`python manage_groups.py list`).")
        return
    # connect_existing() sets row_factory and foreign_keys, and refuses
    # to create a missing file.
    conn = connect_existing(group_db_path(group["slug"], GROUPS_DIR))

    user_ids = [row["id"] for row in conn.execute("SELECT id FROM users").fetchall()]
    if not user_ids:
        print("Error: no users exist yet. Create at least one with create_user.py first.")
        conn.close()
        return

    total_participations = 0

    for _ in range(count):
        # 1 to 3 Tipo de Carne per asado (minimum one, same rule the
        # real form enforces), no duplicates within the same asado.
        tipo_carne_list = random.sample(
            list(TIPO_CARNE_WEIGHTS.keys()), random.randint(1, 3)
        )
        coccion = random.choice(list(COCCION_WEIGHTS.keys()))
        superficie = random.choice(list(SUPERFICIE_WEIGHTS.keys()))
        local = random.choice(list(LOCAL_WEIGHTS.keys()))

        # Location is optional in the real form too, so leave it empty
        # about a third of the time rather than always filling it in.
        if random.random() < 0.7:
            location, latitude, longitude = random.choice(SAMPLE_LOCATIONS)
        else:
            location, latitude, longitude = "", None, None

        # A few cuts when a beef category with a despiece was picked, so
        # /cortes-related views have something to show. (asado_record
        # drops cuts for any other category anyway.)
        cortes = []
        if any(tc in CATEGORIAS_CON_DESPIECE for tc in tipo_carne_list):
            cortes = random.sample(list(CORTES_VACUNO), random.randint(0, 3))

        # Between 1 participant and everyone you have registered, each
        # member appearing at most once (random.sample never repeats).
        participant_ids = random.sample(user_ids, random.randint(1, len(user_ids)))

        asado_record.create(
            conn,
            asado_record.AsadoInput(
                date=random_date_within_last_years(),
                nombre=f"{random.choice(NAME_ADJECTIVES)} {random.choice(NAME_NOUNS)}",
                description="Asado de prueba generado automáticamente.",
                tipos_carne=tipo_carne_list,
                cortes=cortes,
                coccion=coccion,
                superficie=superficie,
                local=local,
                location=location,
                latitude=latitude,
                longitude=longitude,
                people=random.randint(4, 20),
                total_weight=round(random.uniform(2.0, 12.0), 1),
                participants=[(uid, random.choice(list(ROL_WEIGHTS.keys()))) for uid in participant_ids],
            ),
            # Not a person: user_id None (activity_log.user_id allows
            # it), and a name that says plainly where the entry came from.
            asado_record.Actor(user_id=None, name="Datos de prueba (seed_random_asados.py)"),
        )
        total_participations += len(participant_ids)

    conn.close()  # asado_record.create() commits each asado itself
    print(f"Created {count} random asados with {total_participations} total participations.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python seed_random_asados.py <group-slug> <count>")
        sys.exit(1)

    try:
        count_arg = int(sys.argv[2])
    except ValueError:
        print("Error: <count> must be a whole number.")
        sys.exit(1)

    if count_arg < 1:
        print("Error: <count> must be at least 1.")
        sys.exit(1)

    seed_random_asados(sys.argv[1], count_arg)
