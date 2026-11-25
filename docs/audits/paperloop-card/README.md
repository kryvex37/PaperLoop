# Landing feature card consistency

Fixed the Transaction tracking card and decorative numbers in the existing landing page feature grid. The work is scoped to that section and reuses the current Light/Dark/Forest/System theme manager.

## Changes

- Transaction tracking now uses `var(--pl-surface)`, the same exact surface used by Collection management. Its border uses the same `var(--pl-border)` token. This resolves to `#F0F5EF` in Light, `#1C2921` in Dark, and `#174A39` in Forest. System resolves to the corresponding Light or Dark surface.
- Transaction tracking heading, supporting description, `04 / VERIFY` label and link use the same semantic heading, secondary-text, muted-text and link tokens as the other feature cards.
- All four card index labels now use the theme’s readable muted text token. Icon containers use the theme section surface with primary-green icons to keep their contrast in Dark and Forest as well as Light.
- Watermarks retain their size and placement and use a centralized theme color with restrained opacity: Light `--color-primary` at `.08`, Dark `--color-primary-hover` at `.10`, Forest `--color-text-secondary` at `.09`. System inherits the active effective theme. Their color and opacity transition with theme changes.
- Existing reduced-motion preferences are respected by the project’s global motion rules.

The central feature-card layout, card dimensions, links, icons, content order and responsive grid were preserved. No routes, backend behavior, dependencies or other sections were changed.

## Verification

Chrome browser audit captured 20 combinations: Light, Dark, Forest, System with Light OS, and System with Dark OS, each at 1440, 1280, 768 and 390px. Each case verified all four cards; Transaction tracking and Collection management had identical computed backgrounds and borders. Headings, descriptions, labels, links and icons all exceeded 4.5:1 computed contrast in the five effective theme cases. The theme sequence and refresh persistence check also passed.

| Theme case | Effective theme | Collection and Transaction surface | Watermark opacity | Lowest card text/icon contrast |
| --- | --- | --- | ---: | ---: |
| Light | Light | `#F0F5EF` | 0.08 | 5.20:1 |
| Dark | Dark | `#1C2921` | 0.10 | 6.40:1 |
| Forest | Forest | `#174A39` | 0.09 | 5.80:1 |
| System, Light OS | Light | `#F0F5EF` | 0.08 | 5.20:1 |
| System, Dark OS | Dark | `#1C2921` | 0.10 | 6.40:1 |

The report folder contains full-page desktop/laptop/tablet/mobile screenshots for each theme case, five mobile navigation captures, and computed measurements in [computed-styles.json](computed-styles.json).

| Theme | Desktop | Mobile |
| --- | --- | --- |
| Light | [View](light-desktop.png) | [View](light-mobile.png) |
| Dark | [View](dark-desktop.png) | [View](dark-mobile.png) |
| Forest | [View](forest-desktop.png) | [View](forest-mobile.png) |
| System, Light OS | [View](system-light-desktop.png) | [View](system-light-mobile.png) |
| System, Dark OS | [View](system-dark-desktop.png) | [View](system-dark-mobile.png) |

## Files modified

- `static/css/paperloop-themes.css` — exact shared card surface and border tokens, card text/icon contrast, theme-aware watermark tokens and transitions.
- `templates/base.html`, `templates/admin/base_site.html` — theme stylesheet cache version.
- `scripts/audit_landing_visual.mjs` — feature card computed-style capture.
- `docs/audits/paperloop-card/` — browser evidence and this report.

## Checks

- `node --check scripts/audit_landing_visual.mjs` — passed.
- `node scripts/test_theme_system.mjs` — passed (initial theme, live selection, persistence and OS preference changes).
- `python manage.py check` — passed.
- `python manage.py test accounts.test_theme_system --keepdb` — passed (3 tests).
- `git diff --check` — passed for changed implementation and audit files.

System Light/Dark was tested with Chrome color-scheme emulation. No frontend npm build or lint scripts are configured in this repository.
