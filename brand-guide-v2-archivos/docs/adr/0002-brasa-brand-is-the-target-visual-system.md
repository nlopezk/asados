# The Brasa brand is the target visual system; style.css migrates to it in its own issue

The committee approved a visual identity for the app, "Brasa" (manual v2.0, November 2026, "old money Texas"): a B-with-flame logo, a light palette with Burdeo Montura as the brand color (plus Pergamino, Nogal, Cuero Crudo, Verde Potrero and Gris Ceniza) and two fonts (Besley, Libre Franklin). v2.0 replaced a first orange version (v1.0) before anything was built on it. From now on, `docs/brand/BRAND.md` is the reference for any change to colors, type, logo or icons, and the master logo files live in `docs/brand/logo/`. The current 2.1.0 look (dark walnut, burgundy, EB Garamond + Inter) stays in `static/style.css` until a dedicated migration issue moves the whole app at once.

## Considered Options

- **Restyle the app in the same pull request as the guide.** Rejected: it would mix a documentation change with a visual change touching every page, and that is hard to review. The move from dark to light also needs its own check of contrast, the Plotly charts, the cow diagram and the calendar.
- **Restyle page by page as other work touches each page.** Rejected: for weeks the app would show two visual systems side by side.
- **Keep the brand only in the slide manual, outside the repo.** Rejected: Claude Code and contributors read the repo, not the deck. A guide that has to be remembered and pasted in each time gets skipped.

## Consequences

- `CLAUDE.md` points to `BRAND.md`, so every Claude Code session sees the rule without being told.
- Until the migration, the "Visual design" and "UI refresh (2.1.0)" notes in `CLAUDE.md` still describe what is live. `BRAND.md` describes where the app is going.
- `style.css` already routes every color and size through `:root` variables, so most of the migration is re-pointing them. `BRAND.md` proposes the mapping.
- The brand keeps the app's burgundy and its green "Añadir Asado", so the migration is mostly lighter surfaces, new fonts and the header in burgundy.
- Open for the migration: re-validating the per-user chart palette on a light surface, and whether to adopt the bottom menu that BRAND.md proposes (a navigation change).
- Pantone references are not defined yet. They get chosen with the printer for merchandise and don't affect the app.
