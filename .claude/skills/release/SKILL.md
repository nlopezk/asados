---
name: release
description: Cut a new version of the asados app and prepare its deploy to PythonAnywhere - preflight checks, version bump in every place, CHANGELOG entry, commit, tag, push, and the exact server checklist. Only when the user explicitly runs /release.
argument-hint: "[version, e.g. 2.1.0 - or 'patch' / 'minor' / 'major']"
disable-model-invocation: true
---

# Release: version, commit, tag, and the deploy checklist

The requested version: **$ARGUMENTS** (if empty, propose one in step 3 and ask).

There's no CI/CD. A release is a commit and a tag on `main`, pushed to GitHub
(`nlopezk/asados`). The user then pulls it on PythonAnywhere by hand. **You do the local
half; the user does the server half** with the checklist you print at the end. You have no
access to the server, so never claim the site is updated.

The repo is **public** and the data is personal, and the live database is ahead of the local
one. Treat every step that leaves this machine as something to confirm first.

## Step 1: Preflight (stop at the first real problem)
1. `python .claude/skills/release/release_check.py` checks for data files or secrets that
   are tracked or committable, confirms you're on `main`, prints every version number, and
   confirms every `migrate_*.py` is in README's deploy list. **Any PROBLEM line blocks the
   release.** Fix it, or explain it to the user, before going on.
2. Look at what's going out: `git log v<last>..HEAD --oneline`, plus the working-tree changes
   the check listed. If there are uncommitted changes, ask whether they belong in this release.
3. Run the `smoke-test` skill:
   `python .claude/skills/smoke-test/smoke_test.py --all`.
   Any functional FAIL blocks the release. A browser-layout FAIL is the user's call: show it
   and ask whether it ships anyway.
4. Offer (don't force) `/security-review` if this release touches routes, login, the export
   token, CSRF, or anything that renders user-typed text.

## Step 2: Is there a migration in this release?
The check prints `NEW/CHANGED since v<last>` for migration scripts. If there is one:
- it must be at the END of README's step-3 list (the `new-migration` skill does this),
- the CHANGELOG entry must say so, and
- the deploy checklist in step 7 must make "run it BEFORE Reload" impossible to miss.

## Step 3: Pick the number
Versions here are informal, but follow the pattern so far: **patch** (2.0.0→2.0.1) for fixes
only, **minor** (2.0→2.1) for new features, **major** (→3.0) for a change in how the app is
structured or deployed (2.0 was the move to groups). Propose a number with a one-line reason,
and let the user confirm it.

## Step 4: Bump every place (four of them, nothing syncs them)
1. `VERSION = "x.y.z"` in `app.py`. It's shown in the footer and busts the CSS cache.
2. `CHANGELOG.md`: a new `## [x.y.z] - YYYY-MM-DD` section (today's date) directly ABOVE the
   previous release and BELOW the "Next Features" note (which now just points at GitHub
   Issues). Use `### Added` / `### Changed` / `### Fixed` the way earlier entries do, written
   for the group (what changed for them), with the reasoning left to CLAUDE.md. Draft it from
   the commits and diff, then **show it to the user for edits**. Mention any GitHub issue this
   release resolves as `(#N)`. After the push in step 6, close each one with
   `gh issue close N --comment "Shipped in vx.y.z."` (ask first, since it's public).
3. `CLAUDE.md`: the `**Currently at vX.Y.Z: ...**` line in "Roadmap / phase status".
4. The git tag `vx.y.z` (step 6).

Then run `python .claude/skills/release/release_check.py x.y.z`. It must pass, with all three
files agreeing and the tag not existing yet.

## Step 5: Docs drift
Skim README's feature list and CLAUDE.md for anything this release made untrue: a new route
in the Architecture list, a new command, a changed count. The v1.0 audit found the README
months out of date. Fix what's wrong, and tell the user what you changed.

## Step 6: Commit, tag, push (confirm before each outward step)
1. Stage **explicit paths only**. Never `git add .` or `git add -A`; that's how data files
   nearly reached GitHub twice. Show `git status` and `git diff --cached --stat`, and get a yes.
2. Commit in the house style: subject `vx.y.z: <short summary>`, then a body explaining the
   reasoning in plain prose (see `git log -3` for the tone), ending with the attribution
   line the session asks for.
3. `git tag -a vx.y.z -m "vx.y.z: <short summary>"`.
4. **Ask before pushing.** Then `git push` and `git push origin vx.y.z`.

## Step 7: Hand over the server checklist
Print this for the user to follow in a PythonAnywhere **Bash console**, filling in the
version and copying the migration list **exactly from README's deploy step 3**:

```bash
cd ~/asados
python3 backup_db.py          # 1. your own backup first - accounts.db + every group
git pull                      # 2. new code arrives; the OLD code keeps serving
python3 migrate_add_cortes.py # 3. EVERY migration, oldest first (copy from README)
python3 migrate_fix_schema_drift.py
python3 migrate_to_groups.py
#    ... any newer ones, in README order
```
Then:
- **Read each migration's output.** Every group must end in `Migration OK` (or `ALREADY`
  present/migrated). If any doesn't: **STOP, don't Reload**, and restore from the backup path
  it printed.
- **4. Web tab → Reload.** This is the moment the new version goes live. It comes last, so
  visitors never hit a page whose table doesn't exist yet.
- **5. Check:** the footer on https://asados.pythonanywhere.com shows `vx.y.z`. If it shows the
  old number, Reload again. If a style change looks missing, hard refresh (Ctrl+Shift+R).
- Only if `requirements.txt` changed in this release: `pip install -r requirements.txt`
  inside the virtualenv, before Reload.
- If this release changes the schema and they want their local copy in step too, the local
  real files need the migrations as well (no sync), with their OK.

## Step 8: Afterwards
When the user says it's deployed, offer to confirm from here:
`curl -s https://asados.pythonanywhere.com/login | grep -o "v[0-9]*\.[0-9]*\.[0-9]*" | head -1`
(the footer shows the version on every page, including login). Report what it says.
