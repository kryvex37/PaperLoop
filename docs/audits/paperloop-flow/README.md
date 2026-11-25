# Connected Paper Flow UI

Implemented in the existing landing-page visualization in `templates/accounts/landing.html`. The existing theme manager remains the source of truth: it sets the effective `data-theme` on `<html>`, and the flow reads the semantic theme tokens. System mode therefore follows the current OS preference and updates through the existing listener without page reloads.

## Visual behavior

- The central node and all five surrounding information cards share `--color-primary` exactly in each effective theme.
- Card and node text use `--color-button-text`; icon tiles use the same foreground as their background and the primary green for the icon. Their measured contrast ranges from **6.56:1 to 7.35:1** across themes.
- Light mode uses a glass-mint board surface (`#EAF5EE`) with theme-aware dots, rings, connectors, soft border, and shadow.
- Dark and Forest modes use deep green board surfaces, with lighter theme-aware patterns and connectors. No white board background remains.
- Theme-sensitive backgrounds, borders, foregrounds and shadows transition over 300ms. Existing global reduced-motion rules disable transitions and animations for users who request reduced motion.
- Existing card sizing and positioning rules remain intact. On mobile, the pre-existing hidden line break in the center label is restored so “Connected” and “paper flow” remain separated.

## Browser measurements

Captured the landing page at 1440, 1280, 768 and 390px in Light, Dark, Forest, System with a Light OS preference, and System with a Dark OS preference. The audit checked all five card backgrounds against the central node and measured heading, description, label and icon colors. Every theme case returned five matching card surfaces, and text/icon contrast passed 4.5:1. System resolved to Light and Dark respectively. Mobile captures showed the five cards stacked below the central node with no overlap.

| Theme case | Effective theme | Board | Center and five cards | Text/icon contrast |
| --- | --- | --- | --- | ---: |
| Light | Light | `#EAF5EE` | `#176B3A` | 6.56:1 |
| Dark | Dark | `#17291F` | `#55B77A` | 6.74:1 |
| Forest | Forest | `#124433` | `#8BD4A3` | 7.35:1 |
| System, Light OS | Light | `#EAF5EE` | `#176B3A` | 6.56:1 |
| System, Dark OS | Dark | `#17291F` | `#55B77A` | 6.74:1 |

## Screenshots

Each theme case has desktop, laptop, tablet and mobile full-page captures, plus a mobile navigation-state screenshot. Computed styles and theme persistence/sequence results are in [computed-styles.json](computed-styles.json).

| Theme | Desktop | Mobile |
| --- | --- | --- |
| Light | [View](light-desktop.png) | [View](light-mobile.png) |
| Dark | [View](dark-desktop.png) | [View](dark-mobile.png) |
| Forest | [View](forest-desktop.png) | [View](forest-mobile.png) |
| System, Light OS | [View](system-light-desktop.png) | [View](system-light-mobile.png) |
| System, Dark OS | [View](system-dark-desktop.png) | [View](system-dark-mobile.png) |

## Files changed

- `static/css/paperloop-themes.css` — flow surface tokens, theme-aware board, node/cards, icons and transitions.
- `templates/base.html` and `templates/admin/base_site.html` — stylesheet cache version update.
- `scripts/audit_landing_visual.mjs` — computed-style coverage for the connected flow and disabled browser cache for repeatable audit runs.
- `docs/audits/paperloop-flow/` — responsive/theme captures and computed style results.

No backend behavior, route, interaction, package, or dependency was changed.

## Checks

- `node --check scripts/audit_landing_visual.mjs` — passed.
- `node scripts/test_theme_system.mjs` — passed (initial theme, live selection, persistence and OS preference changes).
- `python manage.py check` — passed.
- `python manage.py test accounts.test_theme_system --keepdb` — passed (3 tests).
- Chrome browser capture/audit — 20 theme/viewport combinations plus 5 mobile-menu states; all cards matched the center-node color in all cases.
- `git diff --check` — passed for the changed implementation and audit files.

System Light/Dark behavior was verified using Chrome’s `prefers-color-scheme` emulation. The repository has no configured npm build or lint script; the targeted browser and Django checks were run instead.
