# =====================================================================
# compare_schema.py  (part of the `new-migration` Claude skill)
# Answers ONE question: "does this database have the shape schema.sql
# says it should?" - tables, columns (type, NOT NULL, default, primary
# key), indexes and foreign keys.
#
#   python .claude/skills/new-migration/compare_schema.py                 # every registered group
#   python .claude/skills/new-migration/compare_schema.py path/to/copy.db # one specific file
#   python .claude/skills/new-migration/compare_schema.py --accounts      # accounts.db vs accounts_schema.sql
#
# Exit code 0 = identical, 1 = differences found (each one printed).
#
# WHY THIS EXISTS: migrate_fix_schema_drift.py was written because the
# v1.7.3 audit found real databases quietly NOT matching schema.sql -
# three missing indexes, and NOT NULL constraints that schema.sql
# promised but the live table never had. Nothing errored; the drift was
# only found by reading both by hand. This makes that check a command.
#
# HOW IT STAYS SAFE (it's pointed at real data by default):
#   * The REFERENCE is built by running schema.sql inside an in-memory
#     database (":memory:"). schema.sql starts with DROP TABLE - which
#     is exactly why it must never touch a real file - but dropping
#     tables in a database that only exists in RAM for a second costs
#     nothing.
#   * Every real file is opened READ-ONLY (SQLite URI "mode=ro"), so
#     even a bug in this script couldn't write to it.
#   * It never imports app.py (same rule as every script in this repo).
#
# WHAT IT CAN'T SEE: CHECK constraints and column ORDER. SQLite exposes
# neither through its PRAGMAs, and column order genuinely differs
# between a fresh table and one that grew via ALTER TABLE ADD COLUMN
# (new columns always land at the end) - which is harmless, since every
# query in this app names its columns. Compare CHECKs by eye if a
# migration touches one.
# =====================================================================

import argparse
import sqlite3
import sys
from pathlib import Path
from urllib.request import pathname2url

REPO_ROOT = Path(__file__).resolve().parents[3]


def open_read_only(path):
    if not Path(path).exists():
        raise FileNotFoundError(f"Database not found: {path}")
    uri = "file:" + pathname2url(str(Path(path).resolve())) + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def reference_from_sql(schema_file):
    """A brand-new in-memory database built from the schema file - the
    'what it SHOULD look like'."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(Path(schema_file).read_text(encoding="utf-8"))
    return conn


def describe(conn):
    """The parts of a schema worth comparing, as plain dicts/sets so two
    databases can be compared with ==. Read from PRAGMAs (SQLite's own
    parse of the schema), never by string-matching CREATE statements,
    which differ in whitespace and comments without meaning anything."""
    shape = {}
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    for t in tables:
        columns = {
            # PRAGMA table_info rows: (cid, name, type, notnull, default, pk)
            r[1]: {"type": r[2].upper(), "notnull": bool(r[3]), "default": r[4], "pk": r[5]}
            for r in conn.execute(f"PRAGMA table_info({t})")
        }
        foreign_keys = {
            # (from column, referenced table, referenced column, on delete)
            (r[3], r[2], r[4], r[6]) for r in conn.execute(f"PRAGMA foreign_key_list({t})")
        }
        indexes = {}
        for r in conn.execute(f"PRAGMA index_list({t})"):
            name, unique, origin = r[1], bool(r[2]), r[3]
            cols = tuple(c[2] for c in conn.execute(f"PRAGMA index_info({name})"))
            # How an index is KEYED decides what counts as "the same":
            #   * a PRIMARY KEY's auto-index (origin 'pk') -> by its columns;
            #   * ANY unique index - whether it came from a column's UNIQUE
            #     constraint (origin 'u', auto-named sqlite_autoindex_...)
            #     or from CREATE UNIQUE INDEX (origin 'c') -> by its
            #     columns. To SQLite these are the same thing: a UNIQUE
            #     constraint IS a unique index, enforced identically. It
            #     matters because a migration can't add a column-level
            #     UNIQUE without rebuilding the table, but CAN add a unique
            #     index (see migrate_locations_unique_name.py);
            #   * an ordinary index -> by its name, as written in schema.sql.
            if origin == "pk":
                key = f"(PRIMARY KEY on {', '.join(cols)})"
            elif unique:
                key = f"(UNIQUE on {', '.join(cols)})"
            else:
                key = name
            indexes[key] = (cols, unique)
        shape[t] = {"columns": columns, "foreign_keys": foreign_keys, "indexes": indexes}
    return shape


def diff(expected, actual):
    """Human-readable list of every way `actual` differs from `expected`."""
    problems = []
    for t in sorted(set(expected) - set(actual)):
        problems.append(f"MISSING TABLE      {t}")
    for t in sorted(set(actual) - set(expected)):
        problems.append(f"EXTRA TABLE        {t}  (not in the schema file - leftover, or schema file not updated?)")
    for t in sorted(set(expected) & set(actual)):
        e, a = expected[t], actual[t]
        for c in sorted(set(e["columns"]) - set(a["columns"])):
            problems.append(f"MISSING COLUMN     {t}.{c}")
        for c in sorted(set(a["columns"]) - set(e["columns"])):
            problems.append(f"EXTRA COLUMN       {t}.{c}")
        for c in sorted(set(e["columns"]) & set(a["columns"])):
            for prop in ("type", "notnull", "default", "pk"):
                if e["columns"][c][prop] != a["columns"][c][prop]:
                    problems.append(f"COLUMN DIFFERS     {t}.{c} {prop}: schema says "
                                    f"{e['columns'][c][prop]!r}, database has {a['columns'][c][prop]!r}")
        for fk in sorted(e["foreign_keys"] - a["foreign_keys"]):
            problems.append(f"MISSING FOREIGN KEY {t}.{fk[0]} -> {fk[1]}({fk[2]}) ON DELETE {fk[3]}")
        for fk in sorted(a["foreign_keys"] - e["foreign_keys"]):
            problems.append(f"EXTRA FOREIGN KEY  {t}.{fk[0]} -> {fk[1]}({fk[2]}) ON DELETE {fk[3]}")
        for i in sorted(set(e["indexes"]) - set(a["indexes"])):
            problems.append(f"MISSING INDEX      {i} on {t}({', '.join(e['indexes'][i][0])})")
        for i in sorted(set(a["indexes"]) - set(e["indexes"])):
            problems.append(f"EXTRA INDEX        {i} on {t}({', '.join(a['indexes'][i][0])})")
        for i in sorted(set(e["indexes"]) & set(a["indexes"])):
            if e["indexes"][i] != a["indexes"][i]:
                problems.append(f"INDEX DIFFERS      {i}: schema {e['indexes'][i]}, database {a['indexes'][i]}")
    return problems


def registered_groups(accounts_path):
    conn = open_read_only(accounts_path)
    try:
        slugs = [r[0] for r in conn.execute("SELECT slug FROM asado_groups ORDER BY id")]
    finally:
        conn.close()
    return [REPO_ROOT / "groups" / f"{s}.db" for s in slugs]


def main():
    parser = argparse.ArgumentParser(description="Compare databases against schema.sql (read-only).")
    parser.add_argument("paths", nargs="*", help="database files to check (default: every registered group)")
    parser.add_argument("--accounts", action="store_true", help="check accounts.db against accounts_schema.sql instead")
    args = parser.parse_args()

    if args.accounts:
        schema_file = REPO_ROOT / "accounts_schema.sql"
        targets = [Path(p) for p in args.paths] or [REPO_ROOT / "accounts.db"]
    else:
        schema_file = REPO_ROOT / "schema.sql"
        targets = [Path(p) for p in args.paths] or registered_groups(REPO_ROOT / "accounts.db")

    expected = describe(reference_from_sql(schema_file))
    worst = 0
    for target in targets:
        conn = open_read_only(target)
        try:
            problems = diff(expected, describe(conn))
        finally:
            conn.close()
        print(f"{target}  vs  {schema_file.name}")
        if problems:
            worst = 1
            for p in problems:
                print(f"  {p}")
        else:
            print("  identical (tables, columns, NOT NULL, defaults, keys, indexes)")
        print()
    return worst


if __name__ == "__main__":
    sys.exit(main())
