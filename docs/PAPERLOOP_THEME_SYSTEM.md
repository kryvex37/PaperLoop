# PaperLoop Theme System

## Architecture

PaperLoop remains a Django template application with Bootstrap and vanilla JavaScript. The single persisted preference is `paperloop.theme`; supported values are `light`, `dark`, `forest`, and `system`. `system` is stored as the preference, while the effective appearance on the document root resolves to `data-theme="light"` or `data-theme="dark"` according to `prefers-color-scheme`.

`templates/base.html` and the Django admin `extrastyle` block apply the saved preference synchronously in the document head, before body paint. Both load `static/css/paperloop-themes.css` and `static/js/theme-system.js`. The shared accessible switcher is `templates/accounts/components/theme_switcher.html`: public and workspace navigation use the dropdown presentation; institution and recycler profile settings use the inline settings presentation; the PaperLoop admin sidebar includes the dropdown.

`static/js/theme-system.js` owns theme selection, localStorage persistence, effective theme resolution, active control states, OS preference listeners, dropdown dismissal, keyboard Escape/arrow behavior, and the `paperloop:themechange` event. It applies changes immediately without navigating or reloading. Storage failures fall back to System.

## CSS tokens

`static/css/paperloop-themes.css` defines the required semantic `--color-*` tokens plus legacy `--pl-*` aliases. Light uses `#E3EDE3` page, `#DCE8DF` section, `#F0F5EF` card, `#D3E2D5` hover, `#174D31` primary text/heading, `#496653` secondary/muted text, `#176B3A` link/brand, `#C9D9CB` border, and white text on primary buttons. Dark uses `#111B16` page, `#17251D` section, `#1C2921` card, `#EDF5EF` primary text, `#BDCCBF` secondary, `#55B77A` brand, and `#34483A` border. Forest uses `#0D392C` page, `#124433` section, `#174A39` card, `#F0F8F1` primary text, `#C5DCCB` secondary, `#8BD4A3` brand, and `#35634D` border. System resolves to Light or Dark before paint. Existing PaperLoop and Bootstrap/Django admin aliases point to these semantic tokens.

The original `static/img/paperloop-logo.webp` remains the brand image; existing brand markup keeps the image immediately before “PaperLoop”. Its aspect ratio is preserved and the source is not recolored or recreated. The switcher icons are Lucide symbols generated into the existing SVG sprite.

Theme color transitions are limited to color, background, and border properties; initial transitions wait until `theme-ready` is added after paint. `prefers-reduced-motion: reduce` disables these transitions and animations.

## Contrast audit and corrections

The previous CSS assigned `--pl-text` to headings and several Bootstrap utilities through overlapping broad `:is()` rules, so muted labels and headings lost their intended hierarchy. Workspace and admin styles also contained later, more specific hardcoded colors (some marked `!important`), which took precedence over theme tokens. A few semantic variables such as the dark/forest primary button text and theme-specific links were not defined, leaving some combinations with insufficient contrast.

The final theme rules now apply separate heading, body, secondary, muted, and link colors with high-specificity overrides for legacy components; preserve light text on dark editorial sections; set a theme-aware button label color; adapt placeholders, focus rings, and disabled controls; and retain status meaning with distinct success, warning, danger, and info tokens. The digital certificate surface now uses the card token on screen and stays white for printing.

Hero-specific rules also give public, about, institution, and recycler hero surfaces the active section color. Public navigation, the open mobile menu, dropdown theme switcher, and public light editorial sections use semantic navbar, card, section, and page tokens. The current theme label remains visible on narrow screens. Dark editorial sections such as AI matching, sustainability, final calls to action, mission quotes, and admin callouts retain light foregrounds and a brighter eyebrow accent in all themes. Their decorative shapes remain behind the copy. Authentication story-panel eyebrows use the same contrast-safe accent.

## Verification

Run `node scripts/test_theme_system.mjs` for the isolated theme controller, required token, and WCAG AA foreground/background checks; run `python manage.py check` for Django configuration/template checks. The theme controller check covers startup restoration, active selection state, live switching without reload, saved preference persistence, and OS changes while System is selected. `accounts.test_theme_system` checks the shared theme controls and asset inclusion on public/auth, institution, recycler, settings, and admin templates.

The shared template switcher is included in public/authenticated navigation and the admin navigation; account profile settings expose the same four options inline. Browser-level visual checks for every role, viewport, and rendered contrast are not automated in this repository (no Playwright, Puppeteer, or jsdom dependency is present); CSS token mappings and responsive rules are in the shared stylesheet.
