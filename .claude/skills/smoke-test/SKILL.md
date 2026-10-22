---
name: smoke-test
description: Verify the asados Flask app still works end to end - run it after ANY change to app.py, config.py, templates, static/style.css, schema or accounts code, before calling the change done, and before every release. Checks every route's login protection, login/next-redirect safety, CSRF, points vs config.py, asado create/edit/delete, double-submit and duplicate-participant guards, group isolation, the export token, every page rendering against a copy of the real data, and (optionally) mobile/desktop layout in a real browser. Never touches the real databases.
argument-hint: "[--real-copy] [--browser] [--all] [--keep]"
---

# Smoke test: "is it really done?"

This project has no test suite. Changes used to be checked with one-off `test_client()`
scripts that were rewritten each time. This skill replaces those with **one script**,
`smoke_test.py` in this folder, that grows a little each time something new needs checking.

## Running it
From the repo root:

| Command | What it adds | When |
|---|---|---|
| `python .claude/skills/smoke-test/smoke_test.py` | ~80 functional checks on a throwaway two-group site (~5 s) | After every change |
| `... --real-copy` | Every page loaded for every group against a **read-only snapshot** of the real local data | After changes to queries, templates, or the schema |
| `... --browser` | Playwright sweep from 320px to 1600px: no page-level sideways scroll, the navbar breakpoint, plus screenshots | After any template/CSS change |
| `... --all` | Everything | Before a release |
| `--keep` | Keeps the throwaway folder so you can inspect it | When debugging a failure |

Run it with `$ARGUMENTS` if given. Otherwise pick the layers that fit what changed, and
default to `--all` if unsure. Exit code 0 means everything passed.

## Why it's safe to run at any time
It `chdir()`s into a fresh temp folder **before** importing `app.py`, and it repoints
`app.ACCOUNTS_DATABASE` / `GROUPS_DIR` / `BACKUP_ROOT` at that folder. `--real-copy` snapshots
the real files with SQLite's backup API (opened `mode=ro`) and only sends GET requests. At the
end it compares a SHA-256 of every real database file from before and after, and **fails
loudly if one changed**. If that last check ever fails, stop everything and look at
`backups/` first.

## Reading the result
- `[PASS]` / `[FAIL]` lines are grouped by section, and every FAIL is repeated at the bottom
  with what was expected versus what came back.
- `[NOTE]` isn't a failure. It usually means a route has a URL argument the script has no
  sample value for, so that route went **untested**. Fix it by adding the argument to the
  `samples` dicts in `run_functional()`.
- Browser screenshots (375px and 1600px for each page) are saved to a folder printed at the
  end. **Look at them** after a visual change: an overflow check can't tell you something is
  ugly, only that it's too wide.
- When something fails, report it to the user exactly as printed. Never weaken a check to
  make it pass. If a check itself is wrong, say why before changing it.

## What each section protects (and the incident behind it)
1. **Every route is protected.** It's built from Flask's own route map, so a NEW route is
   checked automatically. The only routes allowed to answer without a login are
   `PUBLIC_ENDPOINTS` (/login, /logout, the token export, /static). The v1.0 audit found
   `/api/points` unprotected.
2. **Login.** Wrong password, case-insensitive usernames, and `?next=` never leaving the site
   (the open redirect fixed in 2.0).
3. **CSRF.** A POST without the token, or with a wrong one, gets a 400.
4. **Points.** `/api/points` must equal `config.calculate_points()` for every role. Category
   names are read from `config.py`, so renaming one can't leave the test passing on stale names.
5. **Create.** Frozen weights (the max Tipo de Carne, each type's own weight), comma decimals
   (`2,5`), cortes, activity log, and the automatic backup.
6. **Double submit.** A replayed `form_token` and a duplicate participant are both refused
   (the 1.7.4 bug: one asado saved twice).
7. **Every GET page** renders 200, plus the CSV's BOM.
8. **Group isolation.** Group B can't see group A's asado on any page, in the CSV, or through
   the export, and a logged-in user of A using B's token gets B's data (`use_group()`).
9. **Permissions.** Edit is open to everyone, delete is admin-only, and after a delete no child
   rows are left behind.
10. **`asado_record` directly (no HTTP).** `CHILD_TABLES` matches schema.sql's foreign keys;
    create/update/delete, every validation rule (each refusal must write nothing), and the
    seed script saving through the module.

The browser layer (`--browser`) also plants a display name containing markup and checks no
page runs it (the stored XSS fixed in 2.1.0).

## Extending it (do this as part of the change, not later)
- **New feature or route:** add a check for its core behaviour to the matching section, in the
  same style: `check("what should be true", condition, "what you got instead")`.
- **New rule about what makes an asado valid:** test it in section 10 against `asado_record`
  directly, not through a form POST. That's the module's interface and its test surface.
- **New URL argument** (like `<int:foo_id>`): add a sample value for it in `run_functional()`.
- **New child table of `asados`:** add it to the "empty after the delete" loop in section 9.
- **New nav link:** re-measure the breakpoint (see the comment above the navbar `@media`
  block in `style.css`) and update the number there. The script reads the breakpoint from
  `style.css` and tests it with a worst-case long name, so the script itself needs no change.
- **New page:** add it to the `pages` list in `run_browser()`.
- After changing the script, prove a new check can actually fail. Break the app on purpose
  in a **scratch copy of the code** (never the working tree), run the script there, and
  confirm the FAIL appears.

## Limits (be honest about these when reporting)
- The browser layer needs Playwright + Chromium (`pip install playwright`,
  `playwright install chromium`) and an internet connection for the CDN fonts and scripts.
- The navbar check runs with a display name longer than `.nav-username`'s 14ch cap, so it
  tests the worst case on THIS machine's Chromium. Other browsers and operating systems render
  fonts slightly differently, which is what the ~20px margin in `style.css` is for.
- It checks behaviour and layout, not looks. Screenshots are still for a human (or Claude) to
  look at.
