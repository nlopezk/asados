Rama nueva: augustohechem/brand-guide-v2  →  main

Título:
Add Brasa brand guide v2.0 for web and app (docs/brand)

Descripción:
## What
A usable brand guide for the web and app, so every change follows the same colors, type and logo rules. NALK asked for this: "un manual de uso y aplicación de colores… en un .md… que lo lea cada vez que se haga alguna modificación". This is v2.0, "old money Texas", with burgundy as the brand color (it replaces the first orange draft in #21, which was closed).

- `docs/brand/BRAND.md`: a short **design spirit** section (how "old money Texas" should feel: a family ranch, not a costume; warm, not luxurious; burgundy only for what matters; readable at the grill), the palette (Burdeo Montura, Pergamino, Nogal, Cuero Crudo, Verde Potrero, Gris Ceniza) with HEX/RGB, CSS tokens and shares; UI tints; a WCAG contrast table; **UI patterns** (burgundy header, burgundy for what's active, podium medals, green only for add/success); Besley + Libre Franklin type scale; logo and app-icon rules; a suggested mapping onto the current `style.css` variables; a checklist for UI PRs.
- `docs/brand/logo/`: 15 master SVGs (logo, isotipo and logotipo in burdeo, pergamino, nogal, cuero and blanco).
- `docs/adr/0002-brasa-brand-is-the-target-visual-system.md`: why the brand becomes the target and the CSS migration is a separate issue.
- `CLAUDE.md`: a short section near the top. CLAUDE.md is loaded automatically, so every Claude Code session will read BRAND.md before a visual change without being asked.

Good news for the migration: the brand keeps the app's burgundy and the green "Añadir Asado", so it's mostly lighter surfaces, new fonts and a burgundy header.

## What it does NOT do
No code, CSS or template changes. The app keeps its current look. Moving `style.css` to the brand should be its own issue. One thing to talk about before building: BRAND.md proposes a bottom menu (Inicio, Ranking, Registrar, Grupo, Tú), which changes navigation.

## To check
- Read BRAND.md sections 1 (colors and the variable mapping), 2 (contrast) and 3 (UI patterns).
- Open any SVG in `docs/brand/logo/` in the browser.
- Nothing to deploy and no migrations.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01HQsU2hQmA2vZvhGtbmaKU7
