# =====================================================================
# release_check.py  (part of the `release` Claude skill)
# The mechanical half of cutting a release: everything that can be
# checked by reading files and asking git, with no judgement involved.
#
#   python .claude/skills/release/release_check.py           # before bumping
#   python .claude/skills/release/release_check.py 2.1.0     # after bumping: is 2.1.0 everywhere?
#
# Exit code 0 = all clear, 1 = something to fix (each one printed).
# Read-only: it never edits a file, stages, commits or tags anything.
#
# Every check here is a mistake this project has made, or nearly made:
#   * the version number lives in FOUR hand-maintained places (VERSION
#     in app.py, CHANGELOG.md, the "Currently at vX" line in CLAUDE.md,
#     and the git tag), and nothing keeps them in sync. The footer has
#     shown a stale number before.
#   * real data (*.db, Base Histórica*.csv) and secrets (secret_key.txt,
#     export_token.txt) sitting one `git add .` away from a PUBLIC repo
#     - it happened twice with the historical CSV.
#   * a migration script added to the repo but missing from the README's
#     every-deploy list, so it would never be run on the live server.
# =====================================================================

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Never committable, whatever .gitignore says. Patterns are matched
# against repo-relative paths (fnmatch-style via Path.match).
FORBIDDEN = ["*.db", "Base Hist*rica*.csv", "secret_key.txt", "export_token.txt", "backups/*", "config beta.py"]

problems = []
warnings = []


def git(*args):
    out = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8")
    return out.stdout


def forbidden(path):
    p = Path(path)
    return any(p.match(pattern) or path.startswith("backups/") for pattern in FORBIDDEN)


def versions_in_files():
    found = {}
    m = re.search(r'^VERSION\s*=\s*"([^"]+)"', (REPO_ROOT / "app.py").read_text(encoding="utf-8"), re.M)
    found["app.py VERSION"] = m.group(1) if m else None
    m = re.search(r"^## \[(\d+\.\d+\.\d+)\]", (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), re.M)
    found["CHANGELOG.md newest entry"] = m.group(1) if m else None
    m = re.search(r"Currently at v(\d+\.\d+\.\d+)", (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8"))
    found["CLAUDE.md 'Currently at'"] = m.group(1) if m else None
    tags = [t for t in git("tag", "--sort=-v:refname").split() if re.fullmatch(r"v\d+\.\d+\.\d+", t)]
    found["newest git tag"] = tags[0][1:] if tags else None
    return found


def main():
    target = sys.argv[1].lstrip("v") if len(sys.argv) > 1 else None

    # --- 1. data and secrets ------------------------------------------
    print("1. Data files and secrets")
    tracked = [f for f in git("ls-files").splitlines() if forbidden(f)]
    for f in tracked:
        problems.append(f"TRACKED BY GIT (must not be): {f}  -> `git rm --cached \"{f}\"`")
    status = git("status", "--porcelain", "--untracked-files=all").splitlines()
    for line in status:
        path = line[3:].strip('"')
        if forbidden(path):
            problems.append(f"about to be committable: {line.strip()}  -> add a .gitignore PATTERN for it")
    for f in ("accounts.db", "groups/parrilla-y-alma.db", "secret_key.txt", "export_token.txt", "asados.db"):
        if (REPO_ROOT / f).exists() and not git("check-ignore", f).strip():
            problems.append(f"NOT IGNORED: {f} (check .gitignore for leading spaces: `git check-ignore -v \"{f}\"`)")
    print("   ok" if not any("TRACKED" in p or "committable" in p or "IGNORED" in p for p in problems) else "   PROBLEMS - see below")

    # --- 2. working tree ------------------------------------------------
    print("2. Working tree")
    branch = git("rev-parse", "--abbrev-ref", "HEAD").strip()
    if branch != "main":
        warnings.append(f"on branch '{branch}', not main - PythonAnywhere pulls main")
    changed = [l for l in status if not forbidden(l[3:].strip('"'))]
    print(f"   branch {branch}; {len(changed)} changed/untracked file(s) that would go into the release:")
    for l in changed:
        print(f"     {l}")

    # --- 3. version numbers ---------------------------------------------
    print("3. Version numbers")
    found = versions_in_files()
    for where, v in found.items():
        print(f"   {where:<28} {v}")
    if target:
        for where, v in found.items():
            if where == "newest git tag":
                if v == target:
                    problems.append(f"tag v{target} already exists - pick the next number")
            elif v != target:
                problems.append(f"{where} says {v}, release is {target}")
        prev = found["newest git tag"]
        if prev and tuple(map(int, target.split("."))) <= tuple(map(int, prev.split("."))):
            problems.append(f"{target} is not newer than the last tag v{prev}")
    else:
        file_versions = {v for k, v in found.items() if k != "newest git tag"}
        if len(file_versions) > 1:
            warnings.append(f"the files disagree with each other already: {found}")

    # --- 4. migrations listed for the deploy ----------------------------
    print("4. Migrations in the every-deploy list")
    scripts = sorted(p.name for p in REPO_ROOT.glob("migrate_*.py"))
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    deploy = readme.split("## Deploying an update", 1)[-1].split("### Why the order matters", 1)[0]
    listed = re.findall(r"python3? (migrate_\w+\.py)", deploy)
    print(f"   in repo: {', '.join(scripts)}")
    print(f"   README deploy step 3 (in order): {', '.join(listed)}")
    for s in scripts:
        if s not in listed:
            problems.append(f"{s} is NOT in README's deploy step 3 - the live server would never run it")
    since = found["newest git tag"]
    if since:
        new = [l for l in git("diff", "--name-status", f"v{since}", "--").splitlines() if re.search(r"migrate_\w+\.py$", l)]
        new += [f"?? {l[3:]}" for l in status if re.search(r"migrate_\w+\.py$", l)]
        if new:
            print(f"   NEW/CHANGED since v{since}: {new}  <- the deploy MUST run these before Reload")

    # --- summary --------------------------------------------------------
    print()
    for w in warnings:
        print(f"WARNING: {w}")
    for p in problems:
        print(f"PROBLEM: {p}")
    print("RELEASE CHECK " + ("FAILED" if problems else "PASSED"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
