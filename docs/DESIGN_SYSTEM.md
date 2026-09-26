# UI Design System — Craft AI inspired

The app deliberately avoids the generic dark "AI dashboard" look. It follows
Craft AI's warm, editorial, card-based visual language (see their site) so the
pitch demo feels on-brand.

## Palette

| Token | Hex | Use |
| --- | --- | --- |
| `cream` (bg) | `#F7F3ED` | Page background |
| `surface` | `#FFFFFF` | Cards / panels |
| `ink` | `#2B2622` | Primary text |
| `muted-ink` | `#6B6259` | Secondary text |
| `brick` (primary) | `#C6482B` | Primary accent, buttons, CRITICAL |
| `terracotta` | `#D97A5A` | Hover / secondary accent |
| `soft-pink` | `#F3D9D2` | Tile background |
| `sand` | `#EBD9BE` | Tile background / WARNING |
| `sage` | `#C7D2C0` | Tile background / COMPLIANT |
| `maroon` | `#5E2A2A` | Deep tile / headers |
| `border` | `#E4DBCF` | Card borders / dividers |

## Status colors

- `COMPLIANT` → sage green (`#4F7A52` text on `#E3ECDD`)
- `REVIEW` → sand/amber (`#9A7B2E` text on `#F3E7C9`)
- `NON_COMPLIANT` → brick (`#C6482B` text on `#F3D9D2`)
- Severity: `CRITICAL` brick · `WARNING` sand · `INFO` muted-ink

## Type & shape

- Sans-serif system stack; large, calm headings; sentence case.
- Cards: 16px radius, soft 1px border (`border` token), generous padding,
  subtle shadow only on hover.
- Small round icon chips on tiles (like the Craft AI feature cards).
- Whitespace-forward. No neon, no glassmorphism, no gradients-on-black.

## Streamlit implementation notes

- Inject a single CSS block (`assets/theme.css` loaded via
  `st.markdown(..., unsafe_allow_html=True)`) that restyles the app container,
  buttons, metric cards, and file uploader to the palette above.
- Set `.streamlit/config.toml` `[theme]` to the base palette (primaryColor
  `#C6482B`, backgroundColor `#F7F3ED`, secondaryBackgroundColor `#FFFFFF`,
  textColor `#2B2622`).
- Build reusable HTML card helpers (status pill, violation card, metric tile)
  rather than relying on default Streamlit widgets for the hero surfaces.
- Dashboard tiles mirror Craft AI's colored feature cards; deep-dive uses a
  two-column split (raw transcript | violation cards).
