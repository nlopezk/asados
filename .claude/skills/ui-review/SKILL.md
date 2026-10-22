---
# ── Frontmatter: the settings Claude Code reads to register this skill ──

name: ui-review
# The command you type: /ui-review
# It should match the folder name: .claude/skills/ui-review/SKILL.md

description: Review the app's existing screens for UI/UX problems, then improve them after approval. Run only when the user types /ui-review.
# The short label shown in the "/" menu.

disable-model-invocation: true
# "true" = Claude never starts this by itself. It only runs when YOU type /ui-review.
---

# UI review

<!-- $ARGUMENTS is replaced with whatever you type after /ui-review.
     Example: "/ui-review templates/new_asado.html" makes the target that file. -->
Target: $ARGUMENTS

If no target was given, review every file in `templates/` and `static/`.

## Phase 1: Review only (do not edit any files yet)

<!-- Phase 1 never changes anything, so you see the problems before any code is touched. -->

1. Load the **web-design-guidelines** skill and check the target against its rules:
   accessibility, forms, mobile and touch, performance, and general UX.
2. Load the **frontend-design** skill and judge the visual side: typography, color,
   spacing, consistency between pages, and whether the design looks generic.
3. Check each main flow on a phone-sized screen: can the task be done comfortably
   with one thumb, in as few steps as possible?

Report the findings as a table with these columns:
issue | file and line | why it matters | suggested fix

Sort the table by severity (High, then Medium, then Low).
Explain every point in plain language: the user is learning front-end development.

## Phase 2: Improve (only after the user approves)

<!-- Phase 2 waits for your answer, so you decide what gets changed. -->

Ask the user which issues to fix. Then, while fixing them:

- Keep the existing layout, flows, colors and wording unless the user agreed to change them.
- Keep it simple: plain HTML, CSS and JavaScript. No new frameworks or libraries.
- Add comments to every change, explaining what the code does and why.
- Only touch front-end files (`templates/` and `static/`). Never change Python code,
  routes, or the database.
