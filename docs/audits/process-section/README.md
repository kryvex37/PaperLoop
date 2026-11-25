# Three-step process section audit

Updated the existing “From surplus to next use.” section in the landing page. The three original steps, SVG icons, copy, animation attributes and order are unchanged.

## Findings and fixes

- **Icon contrast:** `.process-step-icon` used white strokes on `var(--paperloop-forest)`. That token resolves to the light heading color in Dark and Forest modes, so the white icon strokes blended into the bright circle. The circle now uses `--color-primary` with contrasting `--color-button-text` strokes, a token-based border, and a section-colored halo. The icon remains 58×58px and keeps its existing overlapping position.
- **Connector contrast:** the connector used a fixed pale green color and a separate light-only mobile color. It now derives from the active primary color, with a CSS mask for the dashed line; the color transitions with theme changes.
- **Card shape:** process cards previously had only right padding and no explicit border width, radius or consistent internal padding. They now share a bordered, rounded surface, token-based background and border, spacing, and shadow.
- **Text alignment:** different heading wraps caused the descriptions to start at different vertical positions. A shared grid row reserves room for two heading lines, aligning all heading and description starts. Step numbers share consistent top/right offsets.
- **Responsive behavior:** desktop and tablet use equal three-column tracks; mobile uses one column with a vertical dashed connector. Cards grow if copy needs more space; no fixed height clips content.

All three cards use `--color-card-bg`, `--color-border`, `--color-heading`, `--color-text-secondary`, and `--color-text-muted`. The icons use `--color-primary` and `--color-button-text`; the rings and connectors use `--color-section-bg` and a mix of the active primary token. System uses the existing theme manager’s resolved Light or Dark mode.

## Browser verification

Chrome captured all five effective theme cases—Light, Dark, Forest, System with Light OS preference, and System with Dark OS preference—at 1440, 1280, 768 and 390px (20 combinations). Browser measurements confirmed:

- At 1440px: three equal 403×250px cards, 35px gaps.
- At 1280px: three equal 364×250px cards, 35px gaps.
- At 768px: three equal 216×250px cards, about 21.5px gaps.
- At 390px: three vertically stacked 360×235px cards, 26px gaps.
- All icons remain 58×58px and overlap the card edge consistently.
- Heading boxes and description starts align across every card at desktop, laptop and tablet widths; mobile cards use the same internal positions.
- No heading or description overflow was reported. Computed text/icon contrast was at least 5.75:1 across all themes.
- Theme sequence and persistence check passed; System was separately captured with Light and Dark OS emulation.

Full-page screenshots of the completed section and computed browser measurements are in this folder:

| Theme | Desktop | Tablet | Mobile |
| --- | --- | --- | --- |
| Light | [After](light-desktop.png) | [After](light-tablet.png) | [After](light-mobile.png) |
| Dark | [After](dark-desktop.png) | [After](dark-tablet.png) | [After](dark-mobile.png) |
| Forest | [After](forest-desktop.png) | [After](forest-tablet.png) | [After](forest-mobile.png) |
| System, Light OS | [After](system-light-desktop.png) | [After](system-light-tablet.png) | [After](system-light-mobile.png) |
| System, Dark OS | [After](system-dark-desktop.png) | [After](system-dark-tablet.png) | [After](system-dark-mobile.png) |

See [computed-styles.json](computed-styles.json) for each card’s dimensions, text baselines, colors, overflow checks, and theme sequence. The folder also includes laptop captures and mobile navigation states.

## Files changed

- `static/css/paperloop-themes.css` — theme-aware card, icon, connector and text styles plus shared grid alignment.
- `templates/base.html` and `templates/admin/base_site.html` — stylesheet cache version update.
- `scripts/audit_landing_visual.mjs` — process-card layout and computed-color measurements.
- `docs/audits/process-section/` — screenshots, computed measurements and this report.

## Checks

- `node --check scripts/audit_landing_visual.mjs` — passed.
- `node scripts/test_theme_system.mjs` — passed (startup, live selection, persistence and OS preference changes).
- `python manage.py check` — passed.
- `python manage.py test accounts.test_theme_system --keepdb` — passed (3 tests).
- `git diff --check` — passed for changed implementation and audit files.

System Light/Dark was tested using Chrome’s color-scheme emulation. The project has no configured npm lint or build script.
