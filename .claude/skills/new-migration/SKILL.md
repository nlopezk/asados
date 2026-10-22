---
name: new-migration
description: Use whenever the asados app's DATABASE SHAPE has to change - a new table, a new column, a new index, a new foreign key, or a constraint change - in the per-group databases (groups/<slug>.db, schema.sql) or the registry (accounts.db, accounts_schema.sql). Also use to check whether existing databases still match schema.sql ("schema drift"). Never change a real database's schema any other way.
argument-hint: "[what the change is, e.g. 'add a fotos table for asado photos']"
---

# New migration: changing the database shape without losing anyone's history

The group databases hold **real, irreplaceable data**: years of asados, locally AND on
PythonAnywhere. The live files are ahead of the local ones and are the authoritative copy.
Every step below exists because skipping it has either already caused a problem in this
project or would destroy data without any error.

The change requested: **$ARGUMENTS**

## Non-negotiable rules
- **Never run `schema.sql` against an existing file.** It starts with `DROP TABLE`. Only
  `manage_groups.py create` runs it, and only on a file it has just checked doesn't exist.
- **Never edit a migration that has already shipped** (`migrate_add_cortes.py`,
  `migrate_fix_schema_drift.py`, `migrate_to_groups.py`, and any later one). Applied
  migrations stay applied and unedited; a new change gets a NEW script.
- **Additive only by default.** Adding a table, a NULLable column, a column with a DEFAULT, or
  an index is safe. Making an existing column NOT NULL, dropping or renaming a column, or
  changing a type needs a full **table rebuild** (see `rebuild_locations()` in
  `migrate_fix_schema_drift.py`). **Stop and explain the rebuild to the user before writing
  one**, since it moves every row of that table.
- Test only against **copies**. Before running anything on the real local files, ask the user.
  You never run anything on PythonAnywhere; the user does that during the release.

## Step 1: Pin down the change
Work out with the user, in plain words:
- Which database? Group data (asados, participations, locations...) → `schema.sql`.
  Logins/groups/memberships → `accounts_schema.sql`, which must stay `IF NOT EXISTS`
  throughout and never DROP anything.
- The exact columns: types, NOT NULL, defaults, foreign keys with their `ON DELETE` behaviour.
  Explain each choice the way CLAUDE.md does (for example, why `activity_log` uses
  `ON DELETE SET NULL` and not `CASCADE`).
- **Does it score?** If the new data could ever affect `points`, its weight must be FROZEN at
  save time like the others (see CLAUDE.md, "frozen weights"). If it must never score, say so
  in the schema comments, the way `asado_cortes` deliberately has no weight column.
- Run `python .claude/skills/new-migration/compare_schema.py` first, so you know whether the
  real databases already drift from `schema.sql` **before** your change. Report any existing
  drift to the user as its own issue, and don't fold a fix for it into this migration silently.

## Step 2: Update the schema file (what FRESH databases get)
In `schema.sql` (or `accounts_schema.sql`):
1. Add the `CREATE TABLE` / column, with the same style of explanatory `--` comments as the
   tables around it.
2. New table: add its `DROP TABLE IF EXISTS` line at the top, **children above parents**
   (`get_db()` turns foreign keys on, so dropping a parent first fails).
3. **Every new foreign key gets an index** in the index block at the bottom of the file.
   SQLite only auto-indexes PRIMARY KEY and UNIQUE columns; the v1.0.0 audit found every
   `WHERE asado_id = ?` doing a full table scan because of this.

## Step 3: Write the migration script
1. Copy `.claude/skills/new-migration/migration_template.py` to the repo root as
   `migrate_<what>.py` (e.g. `migrate_add_fotos.py`).
2. Fill in the header: the one-line summary and the WHY, written for the beginner who owns
   this repo.
3. Set `MIGRATION_NAME`, and replace the example `STEPS` with the real ones. Copy the SQL from
   what you just wrote in `schema.sql`, **character for character**. Every step needs a real
   `is_applied` check.
4. Leave the template's safety machinery alone: existence check, backup-or-refuse, one
   transaction, `foreign_key_check`, row counts discovered automatically, non-zero exit on
   failure, every registered group by default.

## Step 4: Update every place that depends on the table list
Go through the list and tell the user which ones applied:
- **New child table of `asados`** → add it to `CHILD_TABLES` in `asado_record.py`, the one
  list that delete() and the edit's wholesale replace both use. (Forget it and the first admin
  to delete such an asado gets a 500 - the smoke test's section 10 now fails first, because it
  compares `CHILD_TABLES` with schema.sql's foreign keys.) Then write and read the new rows in
  `asado_record.py` (`_write_children()`, `update()`'s before-state for the activity-log diff,
  and `AsadoInput`/`read_form()` if the form submits them).
- **New table with an `id` column** → add it to `GROUP_TABLES` in `migrate_to_groups.py`.
- If `edit_asado()` replaces children wholesale, the new child table probably needs the same
  delete-and-reinsert treatment.
- Should it appear in Base de Asados / the CSV export? Ask the user. `BASE_ASADOS_QUERY`, the
  on-screen `<th>` list and the CSV header row are three separate lists, and each must be
  updated and re-checked position by position.
- If `seed_random_asados.py` should fill it, update that too.

## Step 5: Prove it on copies
Make a scratch folder (the session scratchpad, never the repo) and snapshot each real
database into it **read-only**. Use SQLite's backup API, never a plain file copy:
```bash
python -c "import sqlite3,sys; s=sqlite3.connect('file:groups/<slug>.db?mode=ro',uri=True); d=sqlite3.connect(sys.argv[1]); s.backup(d)" <scratch>/copy.db
```
Then, from the repo root:
1. `python .claude/skills/new-migration/compare_schema.py <scratch>/copy.db`. **Before**
   migrating, this must show exactly your change as MISSING (plus any drift found in step 1),
   and nothing else.
2. `python migrate_<what>.py <scratch>/copy.db`: must end with `Migration OK`, every existing
   table `ok`, and the same row counts before and after.
3. Run it **again** on the same copy: it must say `already present` for every step and still
   end `Migration OK`.
4. `compare_schema.py <scratch>/copy.db` again. Your change must no longer be listed. If
   anything new appears, the migration's SQL and `schema.sql` disagree; fix whichever is wrong.
5. A FRESH database must match too: `python -c "import sqlite3; c=sqlite3.connect('<scratch>/fresh.db'); c.executescript(open('schema.sql',encoding='utf-8').read())"`,
   then run `compare_schema.py <scratch>/fresh.db` (it should report identical), and run the
   migration on it (every step should be `already present`).
6. Run the `smoke-test` skill (`python .claude/skills/smoke-test/smoke_test.py --real-copy`).

## Step 6: Wire it into the deploy
Every deploy runs **every** migration, oldest first, so nobody has to judge whether a release
"needs" one. Add the new script at the END of the list in all three places:
- `README.md` → "Deploying an update" → step 3 code block (the authoritative list the
  `release` skill reads).
- `CLAUDE.md` → the "Commands" block.
- `CHANGELOG.md` → the next version's entry, saying a migration is included and that it must
  run before Reload.

## Step 7: The real local files (ask first)
The local databases need the migration too; there is no sync between machines. With the
user's OK, run `python migrate_<what>.py` with no argument (every registered group; it backs
each one up first). Show the user the before/after table, then run `compare_schema.py` with
no argument.

## Step 8: Report back
Tell the user, in plain words: what changed in each file, what the copy tests printed, any
pre-existing drift found, and the one thing to remember on PythonAnywhere:
**backup → git pull → migrations → THEN Reload.**
