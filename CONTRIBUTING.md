# Contributing to Asados

How we work on this app in parallel without stepping on each other.
Written for anyone contributing alongside the owner (nlopezk). If you
use Claude Code, it reads `CLAUDE.md` and knows these rules too.

## Who does what

| | Contributor | Owner (nlopezk) |
|---|---|---|
| Works on a branch, opens pull requests | ✅ | ✅ |
| Reviews and approves pull requests | ✅ (the owner's, if asked) | ✅ |
| Merges into `main` | after approval | ✅ |
| Releases a version (`/release`, version number, CHANGELOG, tag) | ❌ | ✅ |
| Deploys to the live site (PythonAnywhere) | ❌ | ✅ |

`main` is **protected on GitHub**: it only changes through a pull request
with one approval, and nobody can force-push to it or delete it. Your
work reaches the live site only when the owner releases and deploys it.

## The rules that matter most

1. **Never commit real data.** This repository is **public**, and the
   app holds a real friend group's names, home addresses and GPS
   coordinates. `.gitignore` already keeps `*.db`, the historical CSVs,
   `backups/` and the secret files out - don't work around it. Work with
   a **test group** full of made-up data (setup below), and never paste
   real data into an issue, a pull request or a screenshot.
2. **One task, one branch, one pull request.** Never work on `main`.
3. **Don't touch the version number or the CHANGELOG** (`VERSION` in
   `app.py`, `CHANGELOG.md`, "Currently at" in `CLAUDE.md`). The owner's
   `/release` sets all of them on `main`. If both of us edited those
   lines on our branches, every pull request would conflict.
4. **Changing the database shape** (a table, a column, an index) only
   through the `/new-migration` Claude skill, never by editing a
   database by hand. Tell the owner first - two migrations made in
   parallel need agreeing on their order.
5. **Run the smoke test before opening a pull request.**
6. Code, comments and docs in **English**; everything the users see
   (labels, buttons, messages) in **Spanish**. Comments explain *why*,
   in detail - this project is also how its owner is learning.

## One-time setup

```powershell
git clone https://github.com/nlopezk/asados.git
cd asados
python -m venv venv                  # a private Python for this project (venv/ is gitignored)
venv\Scripts\activate                # Mac/Linux: source venv/bin/activate
pip install -r requirements.txt

# A TEST group with made-up asados - never a copy of the real data:
python manage_groups.py create prueba "Prueba" prueba "prueba" "Prueba Admin"
python seed_random_asados.py prueba 60
python app.py                        # http://127.0.0.1:5000, log in as prueba / prueba
```

If you want more people in the test group (to see the standings, the
chart, several participants):
`python create_user.py prueba otro "otro" "Otro Nombre"`, then seed again.

Tell Git who you are, once: `git config --global user.name "Your Name"`
and `git config --global user.email "you@example.com"`.

## The cycle, step by step

### 1. Pick something

All work starts from a **GitHub issue**
(https://github.com/nlopezk/asados/issues). Assign it to yourself so
nobody else builds the same thing:
```powershell
gh issue edit 12 --add-assignee @me
```
No issue for what you want to do? Open one first, so it can be agreed on.

### 2. Start a branch from an up-to-date main

```powershell
git switch main
git pull
git switch -c augusto/12-calendario      # your name / issue number - short description
```

### 3. Work and commit

Small commits with a message that says what changed. Name the files you
add - **never `git add .`**, which is how data files nearly got published
twice:
```powershell
git status                                # what changed?
git add -- templates/calendario.html static/style.css
git commit -m "Calendario: month grid of asados (#12)"
```

### 4. Stay up to date with main

The owner keeps merging things while you work. Bring them into your
branch often, at least before opening the pull request:
```powershell
git pull origin main
```
If Git reports a **conflict**, see "Conflicts" below.

### 5. Check it

```powershell
python .claude/skills/smoke-test/smoke_test.py          # ~80 checks, a few seconds
python .claude/skills/smoke-test/smoke_test.py --all    # also layout on phone/desktop - use it if you touched templates or CSS
```
Look at your change in the browser too, including on a phone-sized
window (browser DevTools → the phone icon).

### 6. Push and open the pull request

```powershell
git push -u origin augusto/12-calendario
gh pr create --fill                       # or use the "Compare & pull request" button on GitHub
```
GitHub fills the description with a short checklist - answer it. Write
`Closes #12` in the description and the issue closes itself on merge.

### 7. Review

The owner reviews: reads the changes, runs the smoke test, looks at the
app. If something needs changing, just make more commits **on the same
branch** and push again - the pull request updates itself. Once
approved, it gets merged with "Squash and merge" (your commits become
one commit on `main`), and GitHub deletes the branch.

### 8. After the merge

```powershell
git switch main
git pull
git branch -D augusto/12-calendario       # -D because a squash merge looks "unmerged" to your local Git
```

## Conflicts

A conflict means you and someone else changed **the same lines** of a
file. Git stops and marks them in the file:

```
<<<<<<< HEAD
your version of the lines
=======
the version from main
>>>>>>> main
```

Edit the file to keep what's right (often a bit of both), delete the
three marker lines, then:
```powershell
git add -- the/file.html
git commit                                 # finishes the merge
```
Not sure? Stop and ask - `git merge --abort` puts everything back the way
it was before the pull. Claude Code can also walk you through it ("help
me resolve this merge conflict").

**The files most likely to conflict here:** `static/style.css` (one big
file - add new rules near the component they belong to, not all at the
end), `app.py`, `CLAUDE.md`, and README's list of migrations.

## If you use Claude Code

It reads `CLAUDE.md`, which holds the project's rules and the reasons
behind them. Useful here:

- `/smoke-test` - check the whole app still works.
- `/new-migration` - the only way to change the database shape.
- `/code-review high` - a bug hunt on your changes before you commit.
- `WORKFLOW.md` is the owner's step-by-step guide; its sections 3-5
  (making a change, checking it, the database) apply to you too.
- **Not for you:** `/release`, the PythonAnywhere steps, and anything in
  `WORKFLOW.md` section 8 (the live data).
