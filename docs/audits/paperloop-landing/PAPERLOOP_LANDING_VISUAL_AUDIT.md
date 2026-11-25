# PaperLoop Landing Page Visual Audit

**Page:** `/accounts/landing/`  
**Browser:** Headless Chrome (CDP), local Django server  
**Scope:** Theme contrast, heading/body typography, public navigation, hero and responsive layout. No backend or business logic was changed.

## Findings and fixes

| Finding | Before | Fix |
| --- | --- | --- |
| Light feature card heading was nearly invisible | “Transaction tracking” used `#F0F5EF` on a `#F0F5EF` surface (1.00:1). | Removed `.feature-editorial` from an overly broad Light surface selector. That selector contained `#changelist-filter` inside `:is()`, whose ID specificity unintentionally overrode the dark feature-card style. |
| AI preview heading disappeared on its pale mock interface | Pale/white text appeared on `#F8FAF7`: Light 1.05:1, Dark 1.06:1, Forest 1.03:1. | Scoped readable dark text and heading colors to the intentionally light AI mock preview, independent of the dark showcase panel around it. |
| Hero secondary action failed in dark themes | Its pale link color sat on a white button: Dark 2.49:1; Forest 1.74:1. | The action now uses the theme’s card surface, text and border tokens. Contrast is 13.62:1 in Dark and 9.35:1 in Forest. |
| Mobile menu icon exposed its screen-reader label | Bootstrap’s `.visually-hidden` utility was unavailable in the local page, so the label could render visibly. | Added the accessible clipping utility locally; the button remains labeled for assistive technology while the label is visually hidden. |
| Mobile feature link crowded the card copy | Link positioning could overlap the description at narrow widths. | Feature cards use a vertical flex layout on mobile and keep the action in normal flow. |
| Public current-page state was not explicit | Active Home state was visual only. | Added `aria-current="page"` to the Home and About links when their existing route is active. Routes and click behavior are unchanged. |

The landing hero, sections and illustrations retain their layout and motion. The public page has a single hero, ecosystem, impact, features, three-step process, AI preview, sustainability, FAQ, closing CTA and footer. There is no separate About content section or testimonials section on this page; the About link remains part of the existing navigation.

## Contrast and typography results

Contrast ratios below were calculated from the browser’s computed text and nearest reported surface colors. The hero uses a subtle radial gradient; the calculation reports its base surface color rather than sampling every rendered pixel. All 26 measured headings per theme and the sampled visible text passed 4.5:1 after fixes. Actual heading minima:

| Effective theme | Minimum heading ratio | Minimum sampled text ratio | Hero “Explore How It Works” |
| --- | ---: | ---: | ---: |
| Light | 5.20:1 | 5.03:1 | 7.77:1 |
| Dark | 6.40:1 | 5.85:1 | 13.62:1 |
| Forest | 6.34:1 | 5.80:1 | 9.35:1 |
| System, light OS | 5.20:1 | 5.03:1 | 7.77:1 |
| System, dark OS | 6.40:1 | 5.85:1 | 13.62:1 |

The rendered hero uses Space Grotesk for its editorial h1 (108px at the 1440px capture), Manrope for section h2 headings (46.08px in that capture), and DM Sans for body copy/navigation. Typography stays responsive; the mobile layout was captured at 390px.

## Theme and viewport coverage

Captured all five effective theme cases at four widths:

| Case | Widths |
| --- | --- |
| Light | 1440, 1280, 768, 390px |
| Dark | 1440, 1280, 768, 390px |
| Forest | 1440, 1280, 768, 390px |
| System with light OS preference | 1440, 1280, 768, 390px |
| System with dark OS preference | 1440, 1280, 768, 390px |

System resolved to Light and Dark respectively. Theme sequence check: `Dark → Forest → System/Light → Light → Dark`; refresh retained `Dark`. Mobile menu open state and theme label were captured for Light, Dark, Forest and System. Dropdown hover and keyboard focus states were also inspected. Theme switching stayed on the same page and applied without reload.

## Screenshots

The `before/` captures show the page immediately before the final theme-aware hero-action contrast correction. The `after/` captures show the current implementation. Full-height screenshots include every landing section. Each folder also includes `computed-styles.json`; the after file contains the measured values and interaction results.

| Theme | Before desktop | After desktop | After mobile |
| --- | --- | --- | --- |
| Light | [Before](before/light-desktop.png) | [After](after/light-desktop.png) | [Mobile](after/light-mobile.png) |
| Dark | [Before](before/dark-desktop.png) | [After](after/dark-desktop.png) | [Mobile](after/dark-mobile.png) |
| Forest | [Before](before/forest-desktop.png) | [After](after/forest-desktop.png) | [Mobile](after/forest-mobile.png) |
| System, light OS | [Before](before/system-light-desktop.png) | [After](after/system-light-desktop.png) | [Mobile](after/system-light-mobile.png) |
| System, dark OS | [Before](before/system-dark-desktop.png) | [After](after/system-dark-desktop.png) | [Mobile](after/system-dark-mobile.png) |

The folders contain the remaining laptop/tablet captures and open-mobile-menu screenshots for each supported theme case.

## Modified files

- `static/css/paperloop-themes.css` — theme-aware public surfaces, dark feature cards, AI preview contrast and hero action contrast.
- `static/css/site.css` — local visually-hidden utility and mobile feature-card flow.
- `templates/base.html` — public active-page semantics and theme stylesheet cache version.
- `templates/admin/base_site.html` — theme stylesheet cache version.
- `scripts/audit_landing_visual.mjs` — repeatable Chrome audit/screenshot runner; cache disabled to avoid stale CSS results.
- `docs/audits/paperloop-landing/` — before/after screenshots, computed browser measurements and this report.

## Verification

- `python manage.py check` — passed; no issues.
- `python manage.py test accounts.test_theme_system --keepdb` — passed; 3 tests.
- `node scripts/test_theme_system.mjs` — passed (startup, live selection, persistence and OS preference changes).
- Browser audit — 20 theme/viewport combinations plus 5 open-mobile-menu screenshots; no sampled text contrast failures after the final fix.
- `git diff --check` — passed for the edited implementation and audit files.

OS light/dark behavior was exercised by Chrome’s color-scheme emulation, rather than physically changing the workstation’s OS setting. The audit is specific to the current landing page and does not claim a full-route visual audit of every dashboard.
