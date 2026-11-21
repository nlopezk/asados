# Brasa brand guide for the web and app

The usable, code-side version of the Brasa visual identity manual
(v2.0, November 2026, approved by the Brasa committee). The full manual,
with drawings and mockups, lives outside the repo as a slide deck; this
file is what code follows. **If this file and a design disagree, this
file wins until the committee changes it** (see
`docs/adr/0002-brasa-brand-is-the-target-visual-system.md`).

The direction is "old money Texas": ranch, leather, walnut wood and
old poster lettering. Burgundy is the brand color.

Color and logo names stay in Spanish on purpose: they are the names the
group uses (Burdeo Montura, Pergamino, Nogal...).

> **Status:** `static/style.css` still uses the 2.1.0 palette (dark
> walnut, burgundy, EB Garamond + Inter). Moving the app to this brand
> is its own issue. Don't restyle pages piecemeal inside unrelated pull
> requests; when the migration happens, it follows this file.

## Design spirit: "old money Texas", read as a family ranch, not a costume

- **Inherited, not new.** It should feel like something that's been in
  the family for years: worn leather, walnut, a well-kept logbook.
  Solid, calm, never flashy.
- **Warm, not luxurious.** It's a group of friends around a fire. No
  gold, no gloss, no "premium" effects.
- **Plain-spoken.** Serif titles like an old poster, plain sans text,
  short words. No ornaments, textures, cowboy clichés (hats, lassos,
  wanted posters) or fake leather backgrounds.
- **One color says "this matters".** Burgundy marks what's active or
  important. If everything is burgundy, nothing is.
- **Earned color.** Extra color is for things the group earns: medals,
  records, streaks.
- **Readable at the grill.** High contrast, big tap targets, one hand,
  outdoors.

**Ask before shipping a screen:** would this look right printed on the
cover of the group's logbook?

**Minimum bar for any screen.** This is the contrast, readability and
UX level every screen should reach: a burgundy header, light surfaces,
the brand color only on what's active, and color with a meaning
(medals, success, add).

---

## 1. Colors

### Brand colors

| Token | Name | HEX | RGB | Level | Share | Role |
|---|---|---|---|---|---|---|
| `--brasa-burdeo` | Burdeo Montura | `#6B1D1A` | 107 29 26 | Primary | 25 % | Logo, app header, titles, numbers, links, primary button, active state |
| `--brasa-pergamino` | Pergamino | `#F3EBDC` | 243 235 220 | Base | 55 % | Page background; text on burgundy, walnut or green |
| `--brasa-nogal` | Nogal | `#2B2019` | 43 32 25 | Secondary | 10 % | Body text; dark surfaces in print and merch |
| `--brasa-cuero` | Cuero Crudo | `#D6BE98` | 214 190 152 | Accent | 5 % | Highlights **only on burgundy or walnut**: logo in the header, "Líder"/"Récord" badges, active tab, 1st-place medal |
| `--brasa-verde` | Verde Potrero | `#2F4A36` | 47 74 54 | Accent | 3 % | "Añadir asado" and success, nothing else |
| `--brasa-ceniza` | Gris Ceniza | `#D9D3CA` | 217 211 202 | Neutral | 2 % | Dividers, card borders, secondary text on dark, 2nd-place medal |

### UI tints (derived, never used for the logo)

| Token | Name | HEX | Use | Contrast |
|---|---|---|---|---|
| `--brasa-papel` | Papel | `#FBF7EF` | Cards, inputs, bottom menu | Nogal on it 14.9:1 |
| `--brasa-banda` | Banda | `#ECE6DC` | Highlighted sections, unselected icon circles | Nogal on it 12.8:1 |
| `--brasa-burdeo-claro` | Burdeo claro | `#F1E1DC` | Background of a selected chip/option | Burdeo on it 9.1:1 |
| `--brasa-ceniza-oscura` | Ceniza oscura | `#6B635C` | Secondary text, input and chip borders | 5.0:1 on Pergamino, 5.5:1 on Papel |
| `--brasa-verde-claro` | Verde claro | `#E3EAE2` | Success message background | Verde on it 8.0:1 |
| `--brasa-cobre` | Cobre | `#A9653A` | 3rd-place medal only | Icon in Pergamino 3.9:1 |
| `--brasa-texto` | Texto secundario | `#4E443D` | Long secondary text | 8.0:1 on Pergamino |

### Ready-to-paste CSS

```css
:root {
    /* Brasa brand colors - docs/brand/BRAND.md */
    --brasa-burdeo: #6B1D1A;
    --brasa-pergamino: #F3EBDC;
    --brasa-nogal: #2B2019;
    --brasa-cuero: #D6BE98;
    --brasa-verde: #2F4A36;
    --brasa-ceniza: #D9D3CA;
    /* UI tints derived from them */
    --brasa-papel: #FBF7EF;
    --brasa-banda: #ECE6DC;
    --brasa-burdeo-claro: #F1E1DC;
    --brasa-ceniza-oscura: #6B635C;
    --brasa-verde-claro: #E3EAE2;
    --brasa-cobre: #A9653A;
    --brasa-texto: #4E443D;
}
```

### Suggested mapping onto the existing variables (for the migration)

`style.css` already routes every color through role variables, so the
migration is mostly re-pointing them. The values below are a proposal,
not yet applied:

| Existing variable | Brand value | Note |
|---|---|---|
| `--color-bg` | Pergamino `#F3EBDC` | The app becomes light: `color-scheme: light` |
| `--color-surface` | Papel `#FBF7EF` | |
| `--color-surface-alt` | Banda `#ECE6DC` | Stripes, hover, highlighted sections |
| `--color-border` | Gris Ceniza `#D9D3CA` | Dividers only. Input borders use Ceniza oscura |
| `--color-text` | Nogal `#2B2019` | 13.4:1 on Pergamino |
| `--color-text-muted` | Ceniza oscura `#6B635C` | 5.0:1 on Pergamino |
| `--color-accent` (fills) | Burdeo `#6B1D1A` | Pergamino text on it: 9.8:1. Navbar background |
| `--color-accent-text` (links) | Burdeo `#6B1D1A` | 9.8:1 on Pergamino |
| `--color-gold` (trim) | Cuero Crudo `#D6BE98` | Current-page underline in the burgundy navbar (6.4:1) |
| `--color-green` ("Añadir Asado") | Verde Potrero `#2F4A36` | Same role as today |

The per-user colors (chart lines and dots) are data, not brand, and stay.
They were validated on today's dark surface, so they need re-validating
on Pergamino during the migration.

---

## 2. Contrast: which text goes on which background

WCAG 2.1 ratios, calculated. AA for normal text needs 4.5:1; "large
only" means text ≥ 24 px, or ≥ 19 px bold, and also logos and icons
(3:1).

| Text ↓ / Background → | Pergamino | Burdeo | Nogal | Cuero | Verde |
|---|---|---|---|---|---|
| **Pergamino** | - | 9.8 AAA | 13.4 AAA | 1.5 never | 8.2 AAA |
| **Burdeo** | 9.8 AAA | - | 1.4 never | 6.4 AA | 1.2 never |
| **Nogal** | 13.4 AAA | 1.4 never | - | 8.8 AAA | 1.6 never |
| **Cuero** | 1.5 never | 6.4 AA | 8.8 AAA | - | 5.4 AA |
| **Verde** | 8.2 AAA | 1.2 never | 1.6 never | 5.4 AA | - |
| **Ceniza** | 1.3 never | 7.8 AAA | 10.7 AAA | 1.2 never | 6.6 AA |

Rules that come out of it:

- Reading text is **Nogal on Pergamino** (or Papel). Titles and numbers
  are **Burdeo**.
- On Burdeo, Nogal or Verde, text is **Pergamino**; highlights are
  **Cuero Crudo**; secondary text is **Gris Ceniza**.
- **Cuero Crudo and Gris Ceniza never go on a light background** as text
  or as a border that has to be seen.
- **Never Burdeo on Nogal** (1.4:1) or Verde on Burdeo (1.2:1).
- **Errors:** no new red (it would fight the brand burgundy). Show errors
  in Burdeo with an icon and a clear message.

---

## 3. UI patterns

The reference is how Strava uses one brand color for what's active and
colored medals for records.

- **Header:** Burdeo, with the isotipo in Cuero Crudo and the group name
  or page title in Pergamino. The current section in the header is
  marked in Cuero Crudo.
- **Active state:** the selected filter, chip, option, bottom-menu item
  and the primary button are Burdeo. A selected chip is a Burdeo border
  and text on Burdeo claro. Everything else stays neutral.
- **Selectable icons** (meat type, cooking method): a 60 px circle in
  Banda with a Nogal line icon. When selected, the circle turns Burdeo
  claro with a Burdeo icon, a Burdeo ring and a small check badge.
- **Podium:** medals in Cuero Crudo (1st), Gris Ceniza (2nd) and Cobre
  (3rd), each with a line icon. The leader gets a Banda section with the
  big number in Besley Black.
- **Add and success:** Verde Potrero for "Añadir asado". The success
  message is Verde text on Verde claro with a check icon.
- **Bottom menu** (proposal, to discuss before building since it changes
  navigation): Inicio, Ranking, Registrar, Grupo, Tú. Line icons; the
  active item is Burdeo.
- **Icons:** keep the Lucide line icons already in `templates/_icons.html`.

---

## 4. Typography

| Use | Font | Weights | Fallback |
|---|---|---|---|
| Logotype, titles, numbers, rankings, records | **Besley** (a Clarendon revival) | ExtraBold 800, Black 900, Bold 700 | `Georgia`, `Rockwell`, serif |
| Text, buttons, forms, UI, data | **Libre Franklin** | Regular 400, SemiBold 600, Bold 700 | `Franklin Gothic Medium`, `Arial`, sans-serif |

Both are free on Google Fonts (SIL Open Font License 1.1):

```html
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Besley:wght@700;800;900&family=Libre+Franklin:wght@400;600;700&display=swap">
```

### Type scale (app, px / line height)

| Level | Font | Size / line height | Print |
|---|---|---|---|
| Title 1 (page title) | Besley ExtraBold, Burdeo | 28 / 32 | 26 pt |
| Title 2 (section, card title) | Besley Bold, Nogal | 18 / 24 | 16 pt |
| Big number (points, stats) | Besley Black, Burdeo | 40 / 44 | 36 pt |
| Body | Libre Franklin Regular, Nogal | 16 / 24 | 10 pt |
| Label | Libre Franklin Bold, UPPERCASE, `letter-spacing: 0.08em`, Ceniza oscura | 12 / 16 | 7.5 pt |
| Note | Libre Franklin Regular, Ceniza oscura | 13 / 18 | 8 pt |

Buttons are Libre Franklin Bold 15 px. Use at most four levels on one
screen. The repo's rule still applies: every font size goes through a
token, never a raw number.

---

## 5. Logo

Master files: `docs/brand/logo/` (SVG, use these; never redraw the logo
or retype "BRASA" in a font).

| File | Use |
|---|---|
| `brasa-logo-<color>.svg` | Main logo (B + BRASA). Default whenever there is room. |
| `brasa-isotipo-<color>.svg` | The B alone: favicon, app icon, header, avatar, small spaces. |
| `brasa-logotipo-<color>.svg` | The word alone: very wide, low spaces. |

`<color>` is `burdeo`, `pergamino`, `nogal`, `cuero` or `blanco`; those
are the only logo colors. The logotype is drawn on Besley Black.

- **Allowed:** Burdeo on Pergamino (preferred), Pergamino on Burdeo,
  Cuero on Nogal or on Burdeo, Nogal on a light background,
  Pergamino/Blanco on a dark and even part of a photo.
- **Clear space:** the module `u` = 1/32 of the B's height. Leave
  **X = 5 u** (the height of the BRASA letters) free on all four sides.
  In CSS terms: the logo's box gets a padding of about 12 % of its width.
- **Minimum size:** main logo 120 px wide; B alone 24 px tall.
- **Never:** stretch, rotate, recolor, add shadows or outlines, put
  Burdeo on Nogal, put Cuero on a light background, or build a
  horizontal version.

### App icon and favicon

- B in Pergamino on a Burdeo square, the B about 50 % of the icon's height.
- Android adaptive icon: the B stays inside the 66 × 66 dp safe zone of
  the 108 × 108 dp icon.
- iOS: a 1024 × 1024 px square master; the system rounds the corners
  (check Apple's current guidance before publishing).
- `static/favicon.svg` and `templates/_brand.html` currently hold the
  old hand-drawn flame. They change to the isotipo in the migration,
  together.

---

## 6. Checklist for any UI change

Before opening a pull request that touches how something looks:

- [ ] Colors come from variables, not hex codes in the markup or CSS rules.
- [ ] Text/background pairs are in the "AA" or "AAA" cells above
      (or "large only", if the text really is large).
- [ ] Burdeo marks what's active; Verde only for add/success; Cuero only
      on Burdeo or Nogal.
- [ ] Font sizes use the scale tokens.
- [ ] The logo, if present, is a file from `docs/brand/logo/` with its
      clear space and at least its minimum size.
- [ ] Checked on a phone width (the group logs asados from the phone).
