# =====================================================================
# smoke_test.py  (part of the `smoke-test` Claude skill)
# One reusable "is it really done?" check for the whole app, replacing
# the ad-hoc test_client() scripts that used to be rewritten from
# scratch after every change.
#
#   python .claude/skills/smoke-test/smoke_test.py              # functional checks
#   python .claude/skills/smoke-test/smoke_test.py --real-copy  # + every page against a COPY of your real data
#   python .claude/skills/smoke-test/smoke_test.py --browser    # + Playwright layout sweep
#   python .claude/skills/smoke-test/smoke_test.py --all        # everything
#   (--keep leaves the throwaway folder behind so you can poke at it)
#
# Exit code 0 = every check passed, 1 = at least one FAIL.
#
# ---------------------------------------------------------------------
# THE ONE RULE THIS FILE IS BUILT AROUND: IT NEVER TOUCHES REAL DATA
# ---------------------------------------------------------------------
# CLAUDE.md says "a new script -> never import app". This file HAS to
# import app (that's the only way to drive it with test_client()), so
# it's the one deliberate exception, and it earns it like this:
#   1. Before importing anything from the project, it chdir()s into a
#      brand-new empty temp folder. app.py finds accounts.db, groups/,
#      backups/ and secret_key.txt by RELATIVE path (see CLAUDE.md,
#      "How the live deployment is actually wired up"), so from in
#      there every one of them resolves to a throwaway file.
#   2. It ALSO overwrites app.py's module-level path settings with
#      absolute temp paths (app.py keeps them module-level precisely so
#      a test can do this) - belt and braces, in case a path ever stops
#      being relative.
#   3. --real-copy never opens your real files for writing: it copies
#      them with SQLite's own backup API (same reason as backup_db.py -
#      a consistent snapshot, not a raw file copy) into the temp folder
#      and only ever runs GET requests against the copy.
#   4. At the very end it fingerprints (size + SHA-256) every real
#      database file it can see and FAILS LOUDLY if any changed during
#      the run. That's the proof, rather than trusting points 1-3.
# =====================================================================

import argparse
import contextlib
import hashlib
import io
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import threading
import traceback
from pathlib import Path
from urllib.parse import urlparse

# .claude/skills/smoke-test/smoke_test.py -> up three folders is the repo.
REPO_ROOT = Path(__file__).resolve().parents[3]

# Windows consoles default to a legacy code page and would crash on the
# Spanish text (ñ, á) that app.py prints or that error messages contain.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Routes that are allowed to answer WITHOUT a login. Exactly the three
# legitimate exceptions CLAUDE.md lists (plus Flask's own /static).
# Anything else that answers an anonymous request is a bug - the v1.0.0
# audit found /api/points sitting unprotected exactly like that.
PUBLIC_ENDPOINTS = {"static", "login", "logout", "base_asados_csv_export"}

# Viewport widths for the --browser sweep. The navbar breakpoint and the
# pixel just above it are ADDED at run time (navbar_breakpoint() reads
# the number out of style.css), so this list can't go stale when the
# breakpoint moves - a hard-coded 1168/1169 here did exactly that.
SWEEP_WIDTHS = [320, 375, 480, 768, 1024, 1280, 1440, 1600]

# The browser sweep runs with this as the logged-in display name: longer
# than .nav-username's 14ch cap, i.e. the WORST case for the navbar's
# width. The 1168px breakpoint was once measured with a 4-letter name
# and failed for everyone with a longer one.
LONG_DISPLAY_NAME = "Administrador Con Un Nombre Larguisimo"


def navbar_breakpoint():
    """The max-width of the @media block that turns on .nav-toggle (the
    hamburger) - i.e. the navbar's breakpoint, read from style.css."""
    css = (REPO_ROOT / "static" / "style.css").read_text(encoding="utf-8")
    blocks = re.split(r"(?=@media\s*\()", css)
    for block in blocks:
        m = re.match(r"@media\s*\(max-width:\s*(\d+)px\)", block)
        if m and re.search(r"\.nav-toggle\s*\{\s*display:\s*block", block):
            return int(m.group(1))
    raise RuntimeError("couldn't find the navbar's @media block in style.css")


# ---------------------------------------------------------------------
# REPORTING - every check goes through check(), so the summary at the
# end can't miss one.
# ---------------------------------------------------------------------
RESULTS = []  # (status, section, name, detail)
SECTION = ["setup"]


def section(name):
    SECTION[0] = name
    print(f"\n== {name} " + "=" * max(0, 60 - len(name)))


def check(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    RESULTS.append((status, SECTION[0], name, detail))
    line = f"  [{status}] {name}"
    if detail and not ok:
        line += f"\n         -> {detail}"
    print(line)
    return ok


def note(name, detail=""):
    """Not a failure - something worth a human glance (e.g. a route this
    script doesn't know how to build a URL for yet)."""
    RESULTS.append(("NOTE", SECTION[0], name, detail))
    print(f"  [NOTE] {name}" + (f" - {detail}" if detail else ""))


# ---------------------------------------------------------------------
# SAFETY NET: fingerprint the real files before and after
# ---------------------------------------------------------------------
def real_data_files():
    files = [REPO_ROOT / "accounts.db", REPO_ROOT / "asados.db"]
    files += sorted((REPO_ROOT / "groups").glob("*.db")) if (REPO_ROOT / "groups").exists() else []
    return [f for f in files if f.exists()]


def fingerprint(paths):
    out = {}
    for p in paths:
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        out[str(p)] = (p.stat().st_size, h)
    return out


# ---------------------------------------------------------------------
# BUILDING THE THROWAWAY SITE
# ---------------------------------------------------------------------
def build_throwaway_site():
    """Two groups (so isolation can be tested), each with an admin, and
    group A also gets a normal user (so admin-only can be tested).
    Uses the project's OWN creation code (manage_groups.create and
    accounts.create_member_account) rather than hand-written INSERTs,
    so this also exercises the real "new group" path."""
    import manage_groups
    from accounts import connect_existing, create_member_account, find_group_by_slug, group_db_path
    from werkzeug.security import generate_password_hash

    quiet = io.StringIO()  # manage_groups prints friendly messages; keep the report readable
    with contextlib.redirect_stdout(quiet):
        rc_a = manage_groups.create("grupo-a", "Grupo A", "admin_a", "pw-a", "Admin A")
        rc_b = manage_groups.create("grupo-b", "Grupo B", "admin_b", "pw-b", "Admin B")
    check("manage_groups.py create works for two fresh groups", rc_a == 0 and rc_b == 0, quiet.getvalue())

    accounts_db = connect_existing("accounts.db")
    group_a = find_group_by_slug(accounts_db, "grupo-a")
    group_db = connect_existing(group_db_path("grupo-a"))
    _, normal_member_id = create_member_account(
        accounts_db, group_db, group_a["id"], "normal_a",
        generate_password_hash("pw-n"), "Normal A", "normal",
    )
    admin_a_member = group_db.execute("SELECT id FROM users WHERE username = 'admin_a'").fetchone()["id"]
    tokens = {r["slug"]: r["export_token"] for r in accounts_db.execute("SELECT slug, export_token FROM asado_groups")}
    group_db.close()
    accounts_db.close()
    return {"admin_a": admin_a_member, "normal_a": normal_member_id, "tokens": tokens}


def import_app(tmp):
    """Import app.py from INSIDE the temp folder, then pin its paths to
    absolute temp paths as well (point 2 of the header)."""
    sys.path.insert(0, str(REPO_ROOT))
    import app as app_module
    app_module.ACCOUNTS_DATABASE = os.path.join(tmp, "accounts.db")
    app_module.GROUPS_DIR = os.path.join(tmp, "groups")
    app_module.BACKUP_ROOT = os.path.join(tmp, "backups")
    app_module.app.config["TESTING"] = True
    # The Secure cookie flag is switched on by an env var (see CLAUDE.md);
    # the test client talks plain http, where a Secure cookie would never
    # be sent back and every login would silently "not stick".
    app_module.app.config["SESSION_COOKIE_SECURE"] = False
    for p in (app_module.ACCOUNTS_DATABASE, app_module.GROUPS_DIR, app_module.BACKUP_ROOT):
        if not os.path.abspath(p).startswith(os.path.abspath(tmp)):
            raise SystemExit(f"REFUSING TO RUN: {p} is outside the temp folder")
    return app_module


# ---------------------------------------------------------------------
# SMALL HTTP HELPERS
# ---------------------------------------------------------------------
def csrf(client):
    """The current session's CSRF token. login() calls session.clear(),
    which throws the old token away, so this always makes one cheap
    request first (any request runs ensure_csrf_token()) and then reads
    whatever the session holds now."""
    client.get("/login")
    with client.session_transaction() as s:
        return s["csrf_token"]


def login(client, username, password, next_url=None):
    client.get("/login")
    url = "/login" + (f"?next={next_url}" if next_url else "")
    return client.post(url, data={"username": username, "password": password, "csrf_token": csrf(client)})


def form_token(client):
    """The one-shot token /asado/new embeds in its form (see
    issue_form_token() in app.py). Read out of the rendered HTML, exactly
    as a browser would submit it."""
    html = client.get("/asado/new").get_data(as_text=True)
    m = re.search(r'name="form_token"\s+value="([^"]+)"', html) or re.search(r'value="([^"]+)"\s+name="form_token"', html)
    return m.group(1) if m else None


def url_for_rule(flask_app, rule, samples):
    """Builds a real URL for a route, filling <int:...> arguments from
    `samples`. Returns None if the route needs an argument we have no
    sample for - reported as a NOTE so a brand-new route shape gets
    noticed instead of silently skipped."""
    from flask import url_for
    args = {}
    for arg in rule.arguments:
        if arg not in samples:
            return None
        args[arg] = samples[arg]
    with flask_app.test_request_context():
        return url_for(rule.endpoint, **args)


def is_login_redirect(resp):
    return resp.status_code == 302 and urlparse(resp.headers.get("Location", "")).path == "/login"


def group_db(tmp, slug):
    conn = sqlite3.connect(os.path.join(tmp, "groups", f"{slug}.db"))
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------
# THE FUNCTIONAL CHECKS
# ---------------------------------------------------------------------
def run_functional(app_module, tmp, ids):
    import config
    flask_app = app_module.app
    rules = [r for r in flask_app.url_map.iter_rules()]

    # ---- 1. Every route except the known public ones needs a login ----
    section("1. every route is protected")
    anon = flask_app.test_client()
    token = csrf(anon)
    samples = {"asado_id": 1, "user_id": 1, "location_id": 1}
    for rule in sorted(rules, key=lambda r: r.rule):
        if rule.endpoint in PUBLIC_ENDPOINTS:
            continue
        url = url_for_rule(flask_app, rule, samples)
        if url is None:
            note(f"{rule.rule}", f"unknown argument(s) {sorted(rule.arguments)} - add a sample to this script")
            continue
        if "GET" in rule.methods:
            resp = anon.get(url)
        else:
            # WITH a valid CSRF token, so this tests the login check,
            # not the CSRF check (that one has its own test below).
            resp = anon.post(url, data={"csrf_token": token})
        check(f"anonymous {sorted(rule.methods - {'HEAD', 'OPTIONS'})[0]} {rule.rule} -> login page",
              is_login_redirect(resp), f"got {resp.status_code} - missing @login_required/@admin_required?")
    resp = anon.get("/export/base-asados.csv")
    check("export CSV with no token -> 403", resp.status_code == 403, f"got {resp.status_code}")
    resp = anon.get("/export/base-asados.csv?token=wrong")
    check("export CSV with a wrong token -> 403", resp.status_code == 403, f"got {resp.status_code}")

    # ---- 2. Login ----
    section("2. login")
    c = flask_app.test_client()
    resp = login(c, "admin_a", "not-the-password")
    check("wrong password is refused", resp.status_code == 200 and "incorrectos" in resp.get_data(as_text=True))
    resp = login(c, "ADMIN_A", "pw-a")
    check("username is case-insensitive (COLLATE NOCASE)", resp.status_code == 302, f"got {resp.status_code}")
    for evil in ("https://evil.example/x", "//evil.example/x", "/\\evil.example/x"):
        c = flask_app.test_client()
        resp = login(c, "admin_a", "pw-a", next_url=evil)
        loc = resp.headers.get("Location", "")
        check(f"?next={evil} does NOT leave the site", resp.status_code == 302 and "evil" not in loc, f"redirected to {loc}")
    c = flask_app.test_client()
    resp = login(c, "admin_a", "pw-a", next_url="/resumen")
    check("?next=/resumen (a real page) IS followed", resp.headers.get("Location", "").endswith("/resumen"))

    # ---- 3. CSRF ----
    section("3. CSRF")
    admin = flask_app.test_client()
    login(admin, "admin_a", "pw-a")
    resp = admin.post("/config/profile", data={"name": "Hacked"})
    check("logged-in POST with no csrf_token -> 400", resp.status_code == 400, f"got {resp.status_code}")
    resp = admin.post("/config/profile", data={"name": "Hacked", "csrf_token": "wrong"})
    check("logged-in POST with a wrong csrf_token -> 400", resp.status_code == 400, f"got {resp.status_code}")

    # ---- 4. Points ----
    # Category values are taken FROM config.py rather than typed here,
    # so renaming a category can't make this test quietly pass on stale
    # names - it always tests whatever config.py says today.
    section("4. points match config.py")
    beef = config.CATEGORIAS_CON_DESPIECE[0]
    other_carne = next(k for k in config.TIPO_CARNE_WEIGHTS if k != beef and config.TIPO_CARNE_WEIGHTS[k] < config.TIPO_CARNE_WEIGHTS[beef]) \
        if any(v < config.TIPO_CARNE_WEIGHTS[beef] for v in config.TIPO_CARNE_WEIGHTS.values()) \
        else next(k for k in config.TIPO_CARNE_WEIGHTS if k != beef)
    coccion = list(config.COCCION_WEIGHTS)[-1]
    superficie = list(config.SUPERFICIE_WEIGHTS)[0]
    local = list(config.LOCAL_WEIGHTS)[0]
    roles = list(config.ROL_WEIGHTS)
    corte = sorted(config.CORTES_VACUNO)[0]
    tipo_list = [beef, other_carne]
    for rol in roles:
        resp = admin.get("/api/points", query_string={
            "tipo_carne": tipo_list, "coccion": coccion, "superficie": superficie, "local": local, "rol": rol})
        expected = config.calculate_points(tipo_list, coccion, superficie, local, rol)
        got = resp.get_json()["points"] if resp.is_json else None
        check(f"/api/points == calculate_points() for rol={rol}", got == expected, f"api={got} config={expected}")

    # ---- 5. Creating an asado ----
    section("5. create an asado")
    payload = {
        "date": "2026-01-15", "nombre": "Smoke Test Asado", "description": "creado por smoke_test.py",
        "tipo_carne": tipo_list, "corte": [corte],
        "coccion": coccion, "superficie": superficie, "local": local,
        "location": "Calle Falsa 123", "latitude": "-33,45", "longitude": "-70,66",  # comma decimals on purpose
        "people": "2", "total_weight": "2,5",
        "participant_user_id": [str(ids["admin_a"]), str(ids["normal_a"])],
        "participant_rol": [roles[0], roles[-1]],
    }
    ftoken = form_token(admin)
    check("/asado/new renders a one-shot form_token", ftoken is not None)
    resp = admin.post("/asado/new", data={**payload, "csrf_token": csrf(admin), "form_token": ftoken})
    check("POST /asado/new redirects (saved)", resp.status_code == 302, f"got {resp.status_code}")

    db = group_db(tmp, "grupo-a")
    asado = db.execute("SELECT * FROM asados").fetchone()
    check("exactly one asado was created", db.execute("SELECT COUNT(*) FROM asados").fetchone()[0] == 1)
    if asado is None:
        db.close()
        return
    asado_id = asado["id"]
    shared = config.get_shared_weights(tipo_list, coccion, superficie, local)
    check("comma decimals parsed (2,5 -> 2.5, -33,45 -> -33.45)",
          asado["total_weight"] == 2.5 and asado["latitude"] == -33.45, f"{asado['total_weight']}, {asado['latitude']}")
    check("frozen tipo_carne_weight is the MAX of the selected types",
          asado["tipo_carne_weight"] == shared["carne"], f"{asado['tipo_carne_weight']} vs {shared['carne']}")
    check("frozen coccion/superficie/local weights match config.py",
          (asado["coccion_weight"], asado["superficie_weight"], asado["local_weight"])
          == (shared["coccion"], shared["superficie"], shared["local"]))
    check("every selected Tipo de Carne stored with its OWN weight",
          sorted((r["tipo_carne"], r["tipo_carne_weight"]) for r in db.execute("SELECT * FROM asado_tipo_carne"))
          == sorted((t, config.TIPO_CARNE_WEIGHTS[t]) for t in tipo_list))
    check("the selected corte was stored", [r["corte"] for r in db.execute("SELECT corte FROM asado_cortes")] == [corte])
    for p in db.execute("SELECT * FROM participations"):
        expected = config.calculate_points(tipo_list, coccion, superficie, local, p["rol"])
        check(f"stored points for rol={p['rol']} == calculate_points()", p["points"] == expected, f"{p['points']} vs {expected}")
    check("activity log recorded the create",
          db.execute("SELECT COUNT(*) FROM activity_log WHERE action = 'create'").fetchone()[0] == 1)
    check("automatic backup landed in backups/grupo-a/ (inside the temp folder)",
          any(Path(tmp, "backups", "grupo-a").glob("*.db")))

    # ---- 6. Duplicates ----
    section("6. double-submit and duplicate participants")
    resp = admin.post("/asado/new", data={**payload, "csrf_token": csrf(admin), "form_token": ftoken})
    check("replaying the SAME form (spent form_token) creates nothing",
          db.execute("SELECT COUNT(*) FROM asados").fetchone()[0] == 1)
    dup = {**payload, "participant_user_id": [str(ids["admin_a"])] * 2}
    admin.post("/asado/new", data={**dup, "csrf_token": csrf(admin), "form_token": form_token(admin)})
    check("the same user twice among participants is refused",
          db.execute("SELECT COUNT(*) FROM asados").fetchone()[0] == 1)

    # ---- 7. Every page renders ----
    section("7. every page renders for a logged-in user")
    samples = {"asado_id": asado_id, "user_id": ids["admin_a"]}
    for rule in sorted(rules, key=lambda r: r.rule):
        if "GET" not in rule.methods or rule.endpoint in PUBLIC_ENDPOINTS:
            continue
        url = url_for_rule(flask_app, rule, samples)
        if url is None:
            note(f"{rule.rule}", f"no sample for {sorted(rule.arguments)} - add one to this script")
            continue
        resp = admin.get(url)
        check(f"GET {url} -> 200", resp.status_code == 200, f"got {resp.status_code}")
    csv_text = admin.get("/base-asados/csv").get_data(as_text=True)
    check("Base de Asados CSV contains the asado", "Smoke Test Asado" in csv_text)
    check("CSV starts with a UTF-8 BOM (Excel on Windows)", csv_text.startswith("﻿"))

    # ---- 8. Group isolation ----
    section("8. group isolation")
    other = flask_app.test_client()
    login(other, "admin_b", "pw-b")
    check("group B's home page doesn't show group A's asado",
          "Smoke Test Asado" not in other.get("/").get_data(as_text=True))
    check(f"group B gets 404 for group A's /asado/{asado_id}", other.get(f"/asado/{asado_id}").status_code == 404)
    check("group B's CSV doesn't contain group A's asado",
          "Smoke Test Asado" not in other.get("/base-asados/csv").get_data(as_text=True))
    resp = anon.get(f"/export/base-asados.csv?token={ids['tokens']['grupo-a']}")
    check("group A's export token -> group A's data", resp.status_code == 200 and "Smoke Test Asado" in resp.get_data(as_text=True))
    resp = anon.get(f"/export/base-asados.csv?token={ids['tokens']['grupo-b']}")
    check("group B's export token -> NOT group A's data", resp.status_code == 200 and "Smoke Test Asado" not in resp.get_data(as_text=True))
    # A logged-in user of A using B's token: the route must SWITCH groups
    # (use_group() closing A's connection), not keep serving A's file.
    resp = admin.get(f"/export/base-asados.csv?token={ids['tokens']['grupo-b']}")
    check("logged into A + B's token -> B's data (use_group switches)", "Smoke Test Asado" not in resp.get_data(as_text=True))

    # ---- 9. Permissions ----
    section("9. edit is open, delete is admin-only")
    normal = flask_app.test_client()
    login(normal, "normal_a", "pw-n")
    resp = normal.post(f"/asado/{asado_id}/delete", data={"csrf_token": csrf(normal)})
    check("normal user cannot delete an asado (403)", resp.status_code == 403, f"got {resp.status_code}")
    resp = normal.post("/config/users/create", data={"csrf_token": csrf(normal), "username": "x", "password": "x", "name": "x"})
    check("normal user cannot create accounts (403)", resp.status_code == 403, f"got {resp.status_code}")
    resp = normal.post(f"/asado/{asado_id}/edit", data={**payload, "nombre": "Smoke Test Editado", "csrf_token": csrf(normal)})
    db.commit()  # end our read snapshot so we see the app's write
    renamed = db.execute("SELECT nombre FROM asados WHERE id = ?", (asado_id,)).fetchone()
    check("normal user CAN edit any asado", resp.status_code == 302 and renamed and renamed["nombre"] == "Smoke Test Editado")
    check("activity log recorded the edit, with the changed field",
          db.execute("SELECT COUNT(*) FROM activity_log_changes").fetchone()[0] >= 1)

    resp = admin.post(f"/asado/{asado_id}/delete", data={"csrf_token": csrf(admin)})
    check("admin can delete it (and its child rows don't cause a 500)", resp.status_code == 302, f"got {resp.status_code}")
    for table in ("asados", "participations", "asado_tipo_carne", "asado_cortes"):
        n = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        check(f"{table} is empty after the delete", n == 0, f"{n} row(s) left")
    db.close()


# ---------------------------------------------------------------------
# --real-copy: every page against a SNAPSHOT of the real data
# ---------------------------------------------------------------------
def run_real_copy(app_module, tmp):
    """Catches the bugs a two-row test site can't: a page that breaks on
    a NULL that only old imported rows have, a query that's fine with 1
    asado and slow with 300, a template choking on a long address.
    GET requests only, against copies - see the header."""
    section("real-copy: every page against a snapshot of your real data")
    src_accounts = REPO_ROOT / "accounts.db"
    if not src_accounts.exists():
        note("no accounts.db in the repo - nothing to copy (fresh checkout?)")
        return
    real = Path(tmp, "real")
    (real / "groups").mkdir(parents=True)

    def snapshot(src, dst):
        # Opened READ-ONLY (mode=ro) - the real file can't be written
        # through this connection even by mistake.
        s = sqlite3.connect(f"file:{src.as_posix()}?mode=ro", uri=True)
        d = sqlite3.connect(dst)
        s.backup(d)
        s.close()
        d.close()

    snapshot(src_accounts, real / "accounts.db")
    acc = sqlite3.connect(real / "accounts.db")
    acc.row_factory = sqlite3.Row
    groups = acc.execute("SELECT id, slug, name FROM asado_groups ORDER BY id").fetchall()
    for g_row in groups:
        snapshot(REPO_ROOT / "groups" / f"{g_row['slug']}.db", real / "groups" / f"{g_row['slug']}.db")

    app_module.ACCOUNTS_DATABASE = str(real / "accounts.db")
    app_module.GROUPS_DIR = str(real / "groups")
    app_module.BACKUP_ROOT = str(real / "backups")
    flask_app = app_module.app

    for g_row in groups:
        gdb = group_db(str(real), g_row["slug"])
        counts = {t: gdb.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("asados", "participations", "users")}
        print(f"  -- group '{g_row['name']}' ({g_row['slug']}): {counts}")
        # Log in WITHOUT a password: we don't know real passwords (and
        # shouldn't), so set the session's account_id directly - exactly
        # what login() itself stores - for one of the group's admins.
        m = acc.execute("""
            SELECT memberships.account_id, memberships.member_id FROM memberships
            WHERE group_id = ? ORDER BY id""", (g_row["id"],)).fetchall()
        admin_row = next((r for r in m if gdb.execute(
            "SELECT role FROM users WHERE id = ?", (r["member_id"],)).fetchone()["role"] == "admin"), m[0] if m else None)
        if admin_row is None:
            note(f"group {g_row['slug']} has no members - skipped")
            continue
        client = flask_app.test_client()
        with client.session_transaction() as s:
            s["account_id"] = admin_row["account_id"]

        newest = gdb.execute("SELECT id FROM asados ORDER BY date DESC, id DESC LIMIT 1").fetchone()
        oldest = gdb.execute("SELECT id FROM asados ORDER BY date ASC, id ASC LIMIT 1").fetchone()
        urls = []
        for rule in flask_app.url_map.iter_rules():
            if "GET" not in rule.methods or rule.endpoint in PUBLIC_ENDPOINTS or rule.arguments:
                continue
            urls.append(url_for_rule(flask_app, rule, {}))
        urls += [f"/?page={p}" for p in (2, 999)]
        urls += [f"/base-asados?page={p}" for p in (2, 999)]
        urls += [f"/resumen?sort={s}&dir={d}" for s, d in (("points", "asc"), ("1; DROP TABLE users--", "desc"))]
        for a in (newest, oldest):
            if a:
                urls.append(f"/asado/{a['id']}")
        urls += [f"/usuario/{r['id']}" for r in gdb.execute("SELECT id FROM users")]
        for url in sorted(set(urls)):
            try:
                resp = client.get(url)
                check(f"[{g_row['slug']}] GET {url} -> 200", resp.status_code == 200, f"got {resp.status_code}")
            except Exception as e:
                check(f"[{g_row['slug']}] GET {url} -> 200", False, f"raised {type(e).__name__}: {e}")
        after = {t: gdb.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("asados", "participations", "users")}
        check(f"[{g_row['slug']}] row counts unchanged by browsing (GET never writes)", after == counts, f"{counts} -> {after}")
        gdb.close()
    acc.close()


# ---------------------------------------------------------------------
# --browser: Playwright layout sweep
# ---------------------------------------------------------------------
def run_browser(app_module, tmp):
    """The checks CLAUDE.md keeps doing by hand: no page-level sideways
    scroll at any width, and the navbar breakpoint still sitting where
    the links actually stop fitting. Each width gets a FRESH page.goto()
    - resizing an already-loaded page doesn't re-run inline scripts like
    the Resumen chart's isNarrow, which once made a sweep "pass" a bug it
    never actually tested (see CLAUDE.md)."""
    section("browser: layout sweep (Playwright)")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        note("playwright not installed - `pip install playwright` then `playwright install chromium`")
        return
    from werkzeug.serving import make_server

    # Point the app back at the throwaway site and give it something to
    # show: a couple of asados so cards, tables and the chart all render.
    app_module.ACCOUNTS_DATABASE = os.path.join(tmp, "accounts.db")
    app_module.GROUPS_DIR = os.path.join(tmp, "groups")
    app_module.BACKUP_ROOT = os.path.join(tmp, "backups")
    seed_db = group_db(tmp, "grupo-a")
    has_asados = seed_db.execute("SELECT COUNT(*) FROM asados").fetchone()[0]
    seed_db.close()
    if not has_asados:
        import config
        c = app_module.app.test_client()
        login(c, "admin_a", "pw-a")
        for i, date in enumerate(("2025-11-02", "2026-02-14", "2026-06-20")):
            c.post("/asado/new", data={
                "date": date, "nombre": f"Asado de prueba con un nombre bastante largo {i}",
                "tipo_carne": [list(config.TIPO_CARNE_WEIGHTS)[i]], "coccion": list(config.COCCION_WEIGHTS)[0],
                "superficie": list(config.SUPERFICIE_WEIGHTS)[0], "local": list(config.LOCAL_WEIGHTS)[0],
                "location": "Avenida Libertador Bernardo O'Higgins 1234, Santiago, Región Metropolitana, Chile",
                "latitude": "-33.44", "longitude": "-70.65", "people": "4",
                "participant_user_id": ["1", "2"], "participant_rol": list(config.ROL_WEIGHTS)[:2],
                "csrf_token": csrf(c), "form_token": form_token(c)})

    # Worst-case display name for every page in the sweep (see LONG_DISPLAY_NAME).
    name_db = group_db(tmp, "grupo-a")
    name_db.execute("UPDATE users SET name = ? WHERE username = 'admin_a'", (LONG_DISPLAY_NAME,))
    name_db.commit()
    name_db.close()
    bp = navbar_breakpoint()
    widths = sorted(set(SWEEP_WIDTHS) | {bp, bp + 1})

    server = make_server("127.0.0.1", 0, app_module.app, threaded=True)
    port = server.server_port
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    # Screenshots go in their OWN temp folder, outside the throwaway site,
    # so they survive its cleanup - they're for looking at afterwards.
    shots = Path(tempfile.mkdtemp(prefix="asados-smoke-shots-"))
    pages = ["/", "/asado/new", "/resumen", "/base-asados", "/ubicaciones", "/config", "/actividad", "/cortes", "/usuario/1"]

    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as e:
                note("chromium not installed for Playwright - run `playwright install chromium`", str(e).splitlines()[0])
                return
            ctx = browser.new_context()
            page = ctx.new_page()
            page.goto(base + "/login")
            page.fill('input[name="username"]', "admin_a")
            page.fill('input[name="password"]', "pw-a")
            page.click('button[type="submit"], input[type="submit"]')
            page.wait_for_load_state("networkidle")

            for width in widths:
                page.set_viewport_size({"width": width, "height": 900})
                for path in pages:
                    page.goto(base + path, wait_until="networkidle")
                    overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
                    check(f"{width}px {path}: no page-level sideways scroll", overflow <= 0, f"{overflow}px too wide")
                    if width in (375, 1600):
                        page.screenshot(path=str(shots / f"{width}{path.replace('/', '_') or '_home'}.png"), full_page=True)
                if width in (bp, bp + 1):
                    page.goto(base + "/", wait_until="networkidle")
                    toggle = page.is_visible(".nav-toggle")
                    height = page.evaluate("document.querySelector('.navbar').getBoundingClientRect().height")
                    if width == bp + 1:
                        check(f"{width}px (just above the breakpoint), longest name: links in one row",
                              not toggle and height < 80,
                              f"toggle visible={toggle}, navbar {height:.0f}px - re-measure the breakpoint (see style.css)")
                    else:
                        check(f"{width}px (the breakpoint): hamburger menu takes over", toggle,
                              f"the {bp}px media query isn't applying")
            browser.close()
    finally:
        server.shutdown()
    print(f"  screenshots (375px and 1600px): {shots}")


# ---------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Smoke-test the asados app against throwaway data.")
    parser.add_argument("--real-copy", action="store_true", help="also browse every page against a COPY of the real data")
    parser.add_argument("--browser", action="store_true", help="also run the Playwright layout sweep")
    parser.add_argument("--all", action="store_true", help="everything")
    parser.add_argument("--keep", action="store_true", help="don't delete the temp folder afterwards")
    args = parser.parse_args()
    if args.all:
        args.real_copy = args.browser = True

    before = fingerprint(real_data_files())
    original_cwd = os.getcwd()
    tmp = tempfile.mkdtemp(prefix="asados-smoke-")
    print(f"Throwaway site: {tmp}")
    os.chdir(tmp)  # point 1 of the header - BEFORE any project import
    crashed = False
    try:
        sys.path.insert(0, str(REPO_ROOT))
        section("setup")
        ids = build_throwaway_site()
        app_module = import_app(tmp)
        run_functional(app_module, tmp, ids)
        if args.browser:
            run_browser(app_module, tmp)
        if args.real_copy:
            run_real_copy(app_module, tmp)
    except Exception:
        crashed = True
        traceback.print_exc()
        check("the smoke test itself ran to completion", False, "crashed - see traceback above")
    finally:
        os.chdir(original_cwd)

    section("safety: real data untouched")
    after = fingerprint(real_data_files())
    check(f"{len(before)} real database file(s) byte-identical before and after", before == after,
          "A REAL DATABASE CHANGED DURING THE TEST - check backups/ before doing anything else")

    if args.keep or crashed:
        print(f"\nKept the throwaway folder: {tmp}")
    else:
        shutil.rmtree(tmp, ignore_errors=True)

    fails = [r for r in RESULTS if r[0] == "FAIL"]
    notes = [r for r in RESULTS if r[0] == "NOTE"]
    passes = sum(1 for r in RESULTS if r[0] == "PASS")
    print("\n" + "=" * 64)
    print(f"{passes} passed, {len(fails)} failed, {len(notes)} note(s)")
    for status, sec, name, detail in fails:
        print(f"  FAIL [{sec}] {name}" + (f"\n       -> {detail}" if detail else ""))
    print("SMOKE TEST " + ("FAILED" if fails else "PASSED"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
