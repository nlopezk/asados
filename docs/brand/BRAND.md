# Brasa brand guide for the web and app

The usable, code-side version of the Brasa visual identity manual
(v1.0, November 2026, approved by the Brasa committee). The full manual,
with drawings and mockups, lives outside the repo as a slide deck; this
file is what code follows. **If this file and a design disagree, this
file wins until the committee changes it** (see
`docs/adr/0002-brasa-brand-is-the-target-visual-system.md`).

Color and logo names stay in Spanish on purpose: they are the names the
group uses (Naranjo Brasa, Crema, Carbón...).

> **Status:** `static/style.css` still uses the 2.1.0 "old money"
> palette (walnut, burgundy, EB Garamond + Inter). Moving the app to
> this brand is its own issue. Don't restyle pages piecemeal inside
> unrelated pull requests; when the migration happens, it follows this
> file.

---

## 1. Colors

| Token name | Name | HEX | RGB | Role |
|---|---|---|---|---|
| `--brasa-naranjo` | Naranjo Brasa | `#E75613` | 231 86 19 | The brand: logo, big numbers, headings ≥ 24 px |
| `--brasa-crema` | Crema | `#FBF5E8` | 251 245 232 | Page background |
| `--brasa-papel` | Papel | `#FFFBF3` | 255 251 243 | Cards, inputs, raised surfaces |
| `--brasa-carbon` | Carbón | `#2A2220` | 42 34 32 | Text, dark surfaces |
| `--brasa-amarillo` | Amarillo Choclo | `#FFC21A` | 255 194 26 | Records and awards only, on Carbón |
| `--brasa-ladrillo` | Ladrillo | `#B83A1E` | 184 58 30 | Primary buttons, links, small orange-ish text |
| `--brasa-texto` | Texto secundario | `#54453F` | 84 69 63 | Body text where Carbón is too heavy |
| `--brasa-suave` | Texto suave | `#6E5C54` | 110 92 84 | Meta, labels, hints |
| `--brasa-linea` | Línea | `#DCCDB9` | 220 205 185 | Borders and dividers (decorative only) |

Papel, Texto secundario, Texto suave and Línea are UI tints derived from
the five brand colors. They are not brand colors, so never use them for
the logo.

**Share of a screen** (rough guide, not a rule to measure): Crema 55 %,
Naranjo 25 %, Carbón 12 %, Amarillo 5 %, Ladrillo 3 %.

### Ready-to-paste CSS

```css
:root {
    /* Brasa brand colors - docs/brand/BRAND.md */
    --brasa-naranjo: #E75613;
    --brasa-crema: #FBF5E8;
    --brasa-carbon: #2A2220;
    --brasa-amarillo: #FFC21A;
    --brasa-ladrillo: #B83A1E;
    /* UI tints derived from them */
    --brasa-papel: #FFFBF3;
    --brasa-texto: #54453F;
    --brasa-suave: #6E5C54;
    --brasa-linea: #DCCDB9;
}
```

### Suggested mapping onto the existing variables (for the migration)

`style.css` already routes every color through role variables, so the
migration is mostly re-pointing them. The values below are a proposal,
not yet applied:

| Existing variable | Brand value | Note |
|---|---|---|
| `--color-bg` | Crema `#FBF5E8` | The app becomes light: `color-scheme: light` |
| `--color-surface` | Papel `#FFFBF3` | |
| `--color-surface-alt` | `#F1E6D6` | Stripes, hover |
| `--color-border` | Línea `#DCCDB9` | |
| `--color-text` | Carbón `#2A2220` | 14.3:1 on Crema |
| `--color-text-muted` | Texto suave `#6E5C54` | 5.8:1 on Crema |
| `--color-accent` (fills) | Ladrillo `#B83A1E` | Crema text on it: 5.3:1 |
| `--color-accent-text` (links) | Ladrillo `#B83A1E` | 5.3:1 on Crema. Never Naranjo for small text |
| `--color-gold` (trim) | Naranjo `#E75613` | Navbar rail, current-page underline |
| `--color-green` ("Añadir Asado") | Ladrillo `#B83A1E` | The brand has no green; to be decided in the migration |

The per-user colors (chart lines and dots) are data, not brand, so they stay.

---

## 2. Contrast: which text goes on which background

WCAG 2.1 ratios, calculated. AA for normal text needs 4.5:1; "large
only" means text ≥ 24 px, or ≥ 19 px bold, and also logos and icons
(3:1).

| Text ↓ / Background → | Crema | Naranjo | Carbón | Ladrillo | Amarillo |
|---|---|---|---|---|---|
| **Crema** | - | 3.4 large only | 14.3 AAA | 5.3 AA | 1.5 never |
| **Naranjo** | 3.4 large only | - | 4.3 large only | 1.6 never | 2.3 never |
| **Carbón** | 14.3 AAA | 4.3 large only | - | 2.7 never | 9.6 AAA |
| **Ladrillo** | 5.3 AA | 1.6 never | 2.7 never | - | 3.5 large only |
| **Amarillo** | 1.5 never | 2.3 never | 9.6 AAA | 3.5 large only | - |

Rules that come out of it:

- Reading text is **Carbón on Crema** (or Papel).
- **Small text never goes in Naranjo.** If it has to look orange, use Ladrillo.
- Primary buttons are **Ladrillo with Crema text**.
- Amarillo appears **only on Carbón** (e.g. a record badge). Never Amarillo on Naranjo.
- Línea (`#DCCDB9`) is 1.4:1 on Crema: fine for a divider, never for an
  input border that must be seen (use Texto suave for that, 5.8:1).

---

## 3. Typography

| Use | Font | Weights | Fallback |
|---|---|---|---|
| Titles, numbers, rankings, records | **Gabarito** | Black 900, Bold 700 (Regular 400 only when big) | `Arial Black`, `Arial`, sans-serif |
| Text, forms, UI, data | **Atkinson Hyperlegible Next** | Regular 400, Bold 700 | `Verdana`, `Arial`, sans-serif |

Both are free on Google Fonts (SIL Open Font License 1.1):

```html
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible+Next:wght@400;700&family=Gabarito:wght@400;700;900&display=swap">
```

### Type scale (app, px / line height)

| Level | Font | Size / line height | Print |
|---|---|---|---|
| Title 1 (page title) | Gabarito Black | 32 / 38 | 28 pt |
| Title 2 (section, card title) | Gabarito Bold | 24 / 30 | 18 pt |
| Big number (points, stats) | Gabarito Black | 40 / 44 | 36 pt |
| Body | Atkinson Regular | 16 / 24 | 10 pt |
| Label | Atkinson Bold, UPPERCASE, `letter-spacing: 0.08em` | 13 / 16 | 8 pt |
| Note | Atkinson Regular | 13 / 18 | 8 pt |

Use at most four levels on one screen. The repo's rule still applies:
every font size goes through a token, never a raw number.

---

## 4. Logo

Master files: `docs/brand/logo/` (SVG, use these; never redraw the logo
or retype "BRASA" in a font).

| File | Use |
|---|---|
| `brasa-logo-<color>.svg` | Main logo (B + BRASA). Default whenever there is room. |
| `brasa-isotipo-<color>.svg` | The B alone: favicon, app icon, avatar, small spaces. |
| `brasa-logotipo-<color>.svg` | The word alone: very wide, low spaces. |

`<color>` is `naranjo`, `crema`, `carbon` or `blanco`; those are the
only logo colors.

- **Allowed:** Naranjo on Crema (preferred), Crema on Naranjo, Naranjo
  on Carbón, Carbón on a light background, Crema/Blanco on a dark and
  even part of a photo.
- **Clear space:** the module `u` = 1/32 of the B's height. Leave
  **X = 5 u** (the height of the BRASA letters) free on all four sides.
  In CSS terms: the logo's box gets a padding of about 12 % of its width.
- **Minimum size:** main logo 120 px wide; B alone 24 px tall.
- **Never:** stretch, rotate, recolor, add shadows or outlines, put it
  on Ladrillo or Amarillo, or rebuild a horizontal version.

### App icon and favicon

- B in Crema on a Naranjo square, the B about 50 % of the icon's height.
- Android adaptive icon: the B stays inside the 66 × 66 dp safe zone of
  the 108 × 108 dp icon.
- iOS: a 1024 × 1024 px square master; the system rounds the corners
  (check Apple's current guidance before publishing).
- `static/favicon.svg` and `templates/_brand.html` currently hold the
  old hand-drawn flame. They change to the isotipo in the migration,
  together.

---

## 5. Checklist for any UI change

Before opening a pull request that touches how something looks:

- [ ] Colors come from variables, not hex codes in the markup or CSS rules.
- [ ] Text/background pairs are in the "AA" or "AAA" cells above
      (or "large only", if the text really is large).
- [ ] No small text in Naranjo; no Amarillo outside a record/award.
- [ ] Font sizes use the scale tokens.
- [ ] The logo, if present, is a file from `docs/brand/logo/` with its
      clear space and at least its minimum size.
- [ ] Checked on a phone width (the group logs asados from the phone).
