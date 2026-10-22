# Workflow: what to do, step by step

Your checklist for working on this app. When you forget how something
goes, start here. Every command is copy-paste ready and labelled with
**where** to type it:

| Label | Where that is |
|---|---|
| **Claude** | The Claude Code chat in VS Code. Commands start with `/`. |
| **PowerShell** | A terminal on your PC, opened in this folder (`D:\jackie\As_app`). In VS Code: *Terminal → New Terminal*. |
| **PythonAnywhere** | A **Bash console** on pythonanywhere.com (*Consoles → Bash*), logged in as `asados`. |

Commands are `python` on your PC and `python3` on PythonAnywhere.

> **Not sure which command or skill fits?** In Claude, type `/ask-matt`
> and describe what you want to do, or just describe it in plain words.
> Claude knows this project's procedures.

---

## Quick index: "I want to..."

| I want to... | Go to |
|---|---|
| Start working for the day | [1](#1-start-a-session) |
| See what's on the to-do list / add an idea or bug | [2](#2-the-to-do-list-github-issues) |
| Build a feature or fix a bug | [3](#3-make-a-change-with-claude) |
| Check that nothing broke | [4](#4-check-that-it-works) |
| Change the database (new table/column) | [5](#5-changing-the-database-shape) |
| Save my work without releasing | [6](#6-save-your-work-commit-without-a-release) |
| Put a new version on the live site | [7](#7-release-and-deploy) |
| Get the live data onto my PC, back up, add a person or group | [8](#8-data-chores) |
| Fix something that went wrong | [9](#9-when-something-goes-wrong) |
| Remember what I must never do | [10](#10-never-do-these) |
| See every command at once | [11](#11-cheat-sheet) |

---

## 1. Start a session

**PowerShell:**
```powershell
git status          # anything left over from last time? (should say "nothing to commit")
git pull            # only matters if you edited something on github.com
python app.py       # run the app locally -> open http://127.0.0.1:5000
```

Your local data is a snapshot from the last time you copied it down,
and the live site is always ahead of it. That's fine for development.
To test against current data, see [8.1](#81-copy-the-live-data-to-your-pc).

---

## 2. The to-do list: GitHub Issues

All ideas and bugs live at **https://github.com/nlopezk/asados/issues**,
not in `CHANGELOG.md` (that file only records what has shipped).

### 2.1 See what's there

**Claude:**
```
/triage show me what needs attention
```

**PowerShell** (the same list, without Claude):
```powershell
gh issue list                         # all open issues
gh issue list --label needs-triage    # not looked at yet
gh issue view 5                       # read issue #5
```

### 2.2 Add an idea or a bug

The easy way. **Claude:**
```
File an issue: <describe the idea or the bug in a sentence or two>
```

Or by hand. **PowerShell:**
```powershell
gh issue create --title "Short title" --label enhancement --label needs-triage
#   (use --label bug instead of enhancement for something broken)
```

> ⚠️ **The repo is PUBLIC, so issues are too.** Never paste a real
> address, coordinates, an export token, a screenshot of real data, or
> anything from a database or CSV into an issue. Use made-up examples
> ("an asado at Calle Falsa 123").

### 2.3 What the labels mean

Every issue gets one **category** (`bug` or `enhancement`) and one **state**:

| State | Meaning | Who acts next |
|---|---|---|
| `needs-triage` | New, nobody has looked at it properly yet | You, with `/triage` |
| `needs-info` | A question is waiting for an answer (read the issue) | You |
| `ready-for-agent` | Fully specified; Claude can build it on its own | Claude |
| `ready-for-human` | Needs your judgement, manual testing, or server access | You |
| `wontfix` | Decided not to do it (the issue gets closed) | Nobody |

`/triage` moves issues between these states. Talk to it in plain words:
`/triage let's look at #3`, `/triage move #5 to ready-for-agent`,
`/triage what's ready for agents?`.

---

## 3. Make a change with Claude

### 3.1 The usual way (most changes)

**Claude:**
```
Work on #5
```
Claude reads the issue, makes the change, runs the smoke test, and
tells you what it did. You then look at it yourself
([4.2](#42-look-at-it-yourself)) and either save it
([6](#6-save-your-work-commit-without-a-release)) or release it ([7](#7-release-and-deploy)).

### 3.2 A bug you don't understand yet

**Claude:**
```
Diagnose this: <what you saw, on which page, and what you expected instead>
```
This makes Claude reproduce the bug before changing anything.

### 3.3 A big or fuzzy feature (e.g. the Groups work, #8)

Do it in stages, so the decisions get made before any code is written:

| Step | Claude command | What happens |
|---|---|---|
| 1 | `/grill-with-docs` + your idea | Claude interviews you until the plan is clear |
| 2 | `/to-spec` | Turns that conversation into a spec issue |
| 3 | `/to-tickets` | Splits the spec into small issues, in order |
| 4 | `/implement #N` | Builds one ticket at a time |

For something too big for one session, `/wayfinder` plans it as a map of
issues you work through over several sessions.

---

## 4. Check that it works

### 4.1 The smoke test

Claude runs this itself after making changes, but you can too.

**PowerShell:**
```powershell
python .claude/skills/smoke-test/smoke_test.py          # quick: ~80 checks, a few seconds
python .claude/skills/smoke-test/smoke_test.py --all    # full: + your real data (a COPY) + phone/desktop layout
```

- The last line says `SMOKE TEST PASSED` or `FAILED`. Each failure is
  listed at the bottom with what it expected and what it got.
- It **never touches your real data**, and it proves this: the
  "byte-identical" check at the end compares your real files before
  and after the run.
- `--all` prints a folder of screenshots (375px phone, 1600px desktop).
  Open a couple and look at them.

### 4.2 Look at it yourself

**PowerShell:** `python app.py`, then open http://127.0.0.1:5000. Click
through whatever changed, and check it on a phone-sized window too
(browser DevTools → the phone icon). If the change touches styles and
looks unchanged, hard refresh with **Ctrl+Shift+R**.

---

## 5. Changing the database shape

New table, new column, new index, or a new rule like "must be unique":

**Claude:**
```
/new-migration <what you want, e.g. "add a photos table for asado pictures">
```

Claude writes `schema.sql` (for new groups) **and** a `migrate_*.py`
script (for existing groups), tests it on copies, and adds it to the
deploy list. Your part:

- **Say yes or no** when it asks to run the migration on your local
  real data.
- **On release day**, the migration runs on the server as part of
  [7.2](#72-your-part-on-pythonanywhere).

To check that the databases still match `schema.sql` (they should
report "identical"), run in **PowerShell**:
```powershell
python .claude/skills/new-migration/compare_schema.py
```

---

## 6. Save your work (commit) without a release

**When:** the change doesn't affect the live site: docs, notes, Claude
skills, this file. Anything that changes what the group SEES is a release
([7](#7-release-and-deploy)) instead.

**Claude:**
```
Commit this (and push)
```

By hand. **PowerShell:**
```powershell
git status                               # see what changed
git add -- WORKFLOW.md README.md         # name each file - NEVER "git add ." (see 10)
git commit -m "Docs: what changed"
git push
```

---

## 7. Release and deploy

### 7.1 Your part on your PC

**Claude:**
```
/release
```
(Or `/release 2.0.2` if you already know the number.) Claude:

1. checks that no data files or secrets would be committed, and runs
   the full smoke test,
2. suggests the version number:
   - **patch** (2.0.1 → 2.0.2): fixes only
   - **minor** (2.0 → 2.1): new features
   - **major** (→ 3.0): a change in how the whole app is structured or deployed
3. updates it in all four places (`app.py`, `CHANGELOG.md`, `CLAUDE.md`,
   and the git tag) and writes the CHANGELOG entry **for you to review**,
4. **asks you** before committing, tagging and pushing,
5. prints the exact server commands below, and offers to close the
   issues the release fixed.

### 7.2 Your part on PythonAnywhere

**PythonAnywhere** (Bash console):
```bash
cd ~/asados
python3 backup_db.py                       # 1. your own backup first
git pull                                   # 2. new code arrives (the site keeps running the OLD code)
python3 migrate_add_cortes.py              # 3. EVERY migration, every time, in this order
python3 migrate_fix_schema_drift.py
python3 migrate_to_groups.py
python3 migrate_locations_unique_name.py
```
(If Claude's printed list has more migrations than this, use Claude's
list: it's read from README, which is always current.)

**Read the migrations' output.** Every group must end with
`Migration OK`, or say it was already done. **If anything says FAILED
or STOPPED: don't Reload.** Read [9.1](#91-a-migration-says-failed-or-stopped).

**Then:** *Web* tab → green **Reload** button. That's the moment the new
version goes live.

### 7.3 Check it

1. Open https://asados.pythonanywhere.com. The small number in the
   footer must show the new version.
2. Old number? Click Reload again.
3. Looks unchanged? Hard refresh (Ctrl+Shift+R).
4. Tell Claude "it's deployed": it can confirm the live version and
   close the issues this release fixed.

**Why this order:** pulling doesn't restart the site, so visitors keep
getting the old, working version while you run the migrations. Reload
comes last, so nobody ever hits new code before its database is ready.

---

## 8. Data chores

### 8.1 Copy the live data to your PC

1. On PythonAnywhere, *Files* tab: download `asados/accounts.db` **and**
   `asados/groups/parrilla-y-alma.db`, both together (a group file
   without its `accounts.db` has nobody who can log in).
2. On your PC, **rename** (don't delete) your current `accounts.db` and
   `groups` folder, e.g. to `accounts_old_2026-10-22.db` and `groups_old_2026-10-22`.
3. Put the downloaded files in their places, then run every migration
   from [7.2](#72-your-part-on-pythonanywhere), in **PowerShell**, with `python`.

**Never upload your PC's files to the live site.** The live files are the real copy.

### 8.2 Back up on demand

Every new asado already triggers an automatic backup of that group.
Backups are kept 14 days, in `backups/<group>/`. For an extra one
before something risky, run in **PowerShell** (or **PythonAnywhere**
with `python3`):
```powershell
python backup_db.py
```
These backups sit on the same disk as the data, so they don't protect
against losing the whole server (that's issue #2).

### 8.3 Add a person to a group

The group's admin does it on the site: **Configuración → Crear Nuevo
Usuario**. Or from a terminal, in **PythonAnywhere**:
```bash
python3 create_user.py parrilla-y-alma <username> <password> "<Display Name>" normal
```
(`admin` instead of `normal` for an admin. Usernames are unique across the whole site.)

### 8.4 Create a new group

**PythonAnywhere** (no Reload needed):
```bash
cd ~/asados
python3 manage_groups.py create <slug> "<Group Name>" <admin_username> <admin_password> "<Admin Display Name>"
#   e.g.  python3 manage_groups.py create los-del-sur "Los del Sur" pedro "a-real-password" "Don Pedro"
python3 manage_groups.py list      # all groups, member counts, export tokens
```
The slug is the group's permanent short id: lowercase letters, digits
and single hyphens. It can never change; the display name can
(`python3 manage_groups.py rename <slug> "<New Name>"`).

### 8.5 The Google Sheets / Looker Studio link

Each group has its own export token. Find it in **PythonAnywhere** with
`python3 manage_groups.py list`, then put this formula in a Sheet cell:
```
=IMPORTDATA("https://asados.pythonanywhere.com/export/base-asados.csv?token=PASTE_TOKEN_HERE")
```
Treat the token like a password: anyone with that link can read the
group's data.

---

## 9. When something goes wrong

**First rule: don't panic-click.** Take a backup (`python3 backup_db.py`)
before trying fixes, then ask Claude. Describe exactly what you see and
paste any error text **without** real data in it.

### 9.1 A migration says FAILED or STOPPED

- **Don't Reload.** Visitors are still on the old code, so nothing is
  broken for them yet.
- **STOPPED** means the script refused on purpose and changed nothing.
  It prints why (e.g. two saved locations with the same name). Fix
  that on the site, then re-run the same migration.
- **FAILED** means it printed the path of the backup it took just
  before. Copy that path and the output to Claude.

### 9.2 The live site shows an error after a Reload

1. *Web* tab → **Log files** → **Error log**. The last lines say what
   broke. Copy them to Claude.
2. To get back to the previous version while it gets fixed, run in
   **PythonAnywhere**:
   ```bash
   cd ~/asados
   git checkout v2.0.0      # <- the PREVIOUS version's tag (see the CHANGELOG)
   ```
   then **Reload**. Every migration only ever *adds* things, so older
   code still runs fine on a newer database. When the fix is released,
   run `git checkout main` before the usual `git pull`.

   ⚠️ **Never go back to a 1.x version** (anything before `v2.0.0`).
   Those read the old `asados.db`, which stopped receiving data at the
   2.0 upgrade, so everything saved since would seem to vanish, and
   anything saved while rolled back would be lost.

### 9.3 Wrong data got saved (bad edit, deleted asado)

For a single asado, it's usually simplest to just fix it on the site,
since anyone can edit. Check **Actividad** first: it shows who changed
what, with old and new values.

To roll the whole group back to a backup (this loses everything saved
**after** that backup):

1. Write down what was added after the backup time (**Actividad** page),
   so it can be re-entered.
2. *Web* tab → **Disable** the web app. This stops anyone saving while you restore.
3. **PythonAnywhere:**
   ```bash
   cd ~/asados
   python3 backup_db.py                         # a backup of the CURRENT state, so this is undoable
   ls -l backups/parrilla-y-alma/               # pick the file from just before the problem
   cp backups/parrilla-y-alma/asados_2026-10-22_103923.db groups/parrilla-y-alma.db   # <- your chosen file
   ```
   (Group backups are named `asados_<date>_<time>.db`, newest last.)
4. *Web* tab → **Enable**, then **Reload**.

If people were **added to the group** after that backup, ask Claude
before restoring: their logins live in `accounts.db` and would point at
members that no longer exist.

### 9.4 A style change doesn't show up

Hard refresh (Ctrl+Shift+R). The stylesheet's URL changes with every
version, so this is rare, but a browser can still hold an old copy.

---

## 10. Never do these

| Never | Because |
|---|---|
| `git add .` or `git add -A` | It can publish the group's real data (`*.db`, the CSV, secrets) to the public repo. It nearly happened twice. Name the files, or let Claude/`/release` stage them. |
| Run `schema.sql` on an existing database | It starts with `DROP TABLE`, which deletes the group's whole history. Schema changes go through `/new-migration`. |
| Upload a database from your PC to PythonAnywhere | The live files are ahead of yours; you'd erase what the group added. |
| Click Reload before the migrations finish OK | New code would run against an old database and pages would error. |
| Put real data in a GitHub issue | Issues are public. |
| Run `seed_random_asados.py` on a real group | Random asados count in the standings like real ones. |
| Edit `templates/_cow_svg.html` by hand | It's generated from `vaca_svg.svg`; edit the drawing and re-run `build_cow_partial.py`. |
| Share an export token or `secret_key.txt` | The token opens a group's data without a login; the key forges logins. |

---

## 11. Cheat sheet

### In Claude

| Command | Use it to |
|---|---|
| `Work on #N` | Build or fix issue N |
| `File an issue: ...` | Add an idea or bug to the list |
| `/triage ...` | Review and sort the issue list |
| `Diagnose this: ...` | Hunt down a bug before fixing it |
| `/grill-with-docs` → `/to-spec` → `/to-tickets` → `/implement` | Plan and build something big |
| `/smoke-test` | Check the whole app still works |
| `/new-migration ...` | Change the database shape |
| `/release` | Ship a new version (then do 7.2) |
| `/code-review` · `/security-review` | Get a second look at changes before committing |
| `/ask-matt` | "Which of these do I need?" |

### In PowerShell (your PC, this folder)

| Command | Does |
|---|---|
| `python app.py` | Run the app at http://127.0.0.1:5000 |
| `python .claude/skills/smoke-test/smoke_test.py [--all]` | Smoke test |
| `python .claude/skills/new-migration/compare_schema.py` | Do the databases match `schema.sql`? |
| `python .claude/skills/release/release_check.py` | Pre-release safety scan (read-only) |
| `python backup_db.py` | Back up everything now |
| `gh issue list` · `gh issue view N` | Read the to-do list |
| `git status` | What changed? |

### On PythonAnywhere (Bash console, after `cd ~/asados`)

| Command | Does |
|---|---|
| `python3 backup_db.py` | Back up everything now |
| `git pull` + every `python3 migrate_*.py` + Reload | Deploy (section 7.2) |
| `python3 manage_groups.py list` | Groups, member counts, export tokens |
| `python3 manage_groups.py create ...` | New group (8.4) |
| `python3 create_user.py <group> <user> <pass> "<Name>" [admin]` | New person (8.3) |

---

*Keep this file in step with reality: when a procedure changes (a new
migration, a new command), update it in the same change. Claude's
`/release` checks it for drift.*
