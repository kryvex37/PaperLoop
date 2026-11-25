# PaperLoop — Lighter-Inspired Frontend Design Plan

> **Scope:** UI/UX & Visual Design Plan Only (No changes to Django backend, PostgreSQL models, APIs, authentication, permissions, or PyTorch/AI logic).
> **Primary Visual Reference:** [Lighter Webflow Template](https://lighter-template.webflow.io/)
> **Brand Reference:** Original PaperLoop Logo & Forest-Green Login Screen

---

## 1. Reference Design Analysis (`lighter-template.webflow.io`)

Based on a live browser audit of the Lighter template, its visual identity is defined by:

### 1.1 Navigation & Header
- **Three-part horizontal header (`banner`):**
  - **Left:** Brand logo mark + wordmark.
  - **Center:** Floating white pill container (`border-radius: 9999px`) housing concise anchor links (`About`, `Services`, `Works`, `Pricing`).
  - **Right:** Solid dark pill CTA button (`Start a Project`).
- **Behavior:** Clicking navigation links smoothly/directly scrolls to section anchors.

### 1.2 Hero Composition
- **Container:** Rounded white card/panel set against a light gray (`#F7F7F7`-style) outer canvas with a subtle dotted grid pattern.
- **Badge:** Centered pill badge (`• Get Started`) with a subtle drop shadow.
- **Headline:** Large centered display typography mixing bold/medium sans-serif text with inline rounded visual pills.
- **Subtext & CTAs:** Centered muted gray description followed by two side-by-side pill buttons (white secondary pill + solid dark primary pill with drop shadow) and a large dashboard preview image below.

### 1.3 Section-by-Section Layout Patterns
- **Asymmetric Story / About:** Eyebrow pill + large H2, followed by a 2-column split (left: subheading, copy, rating block; right: rounded photo with overlapping floating metric cards).
- **Repeating Marquee / Ticker:** Horizontal keyword and client logo tickers.
- **Impact / Statistics Carousel:** Interactive 4-slide metric carousel with previous/next controls.
- **Services / Capabilities Stack:** Full-width rounded pill/row cards (`1px` subtle border, generous border-radius) with title, tagline, and description.
- **Process / How It Works:** Interactive 3-slide step carousel with step numbers, descriptions, and CTA.
- **Pricing / Tiered Plans:** 4-column card grid with a Monthly/Yearly pill toggle, checklist items, and a highlighted gradient card for the top tier.
- **Testimonials & FAQ:** 3-slide testimonial carousel; 2-column FAQ with left support CTA and right clickable `+`/`-` accordion rows.
- **Bottom CTA & Footer:** Full-width rounded dark/gradient CTA card with dotted grid overlay; full-width rounded dark charcoal footer with 4-column top grid and bottom copyright + `Back to Top ^` bar.

### 1.4 Observed Interactions
- Dynamic Monthly/Yearly pill toggle updating plan values.
- Smooth/direct anchor scrolling from header links.
- Interactive `previous slide` / `next slide` carousels (Impact, Process, Testimonials).
- Clickable FAQ accordion rows (`+` / `-` toggle).
- Interactive media pause/play toggle.

---

## 2. Existing PaperLoop Frontend Audit

### 2.1 Templates Inventory (`templates/`)
- **Base & Error:** `templates/base.html`, `templates/403.html`
- **Public Pages:** `templates/accounts/landing.html`, `templates/accounts/about.html`
- **Authentication:** `templates/accounts/login.html`, `templates/accounts/register.html`, `templates/accounts/verification_pending.html`, `templates/accounts/access_unavailable.html`, `templates/accounts/password_reset_form.html`, `templates/accounts/password_reset_done.html`, `templates/accounts/password_reset_confirm.html`, `templates/accounts/password_reset_complete.html`
- **Institution Portal:** `templates/accounts/components/institution_sidebar.html`, `templates/accounts/institution_dashboard.html`, `templates/accounts/institution_profile_form.html`, `templates/accounts/listing_form.html`, `templates/accounts/listing_recommendations.html`, `templates/accounts/partner_directory.html`, `templates/accounts/partner_public_detail.html`, `templates/accounts/bulk_aggregation.html`
- **Recycler / Partner Portal:** `templates/accounts/partner_dashboard.html`, `templates/accounts/partner_profile_form.html`, `templates/accounts/partner_profile_detail.html`
- **Shared Operations & Records:** `templates/accounts/collection_detail.html`, `templates/accounts/transaction_history.html`, `templates/accounts/transaction_detail.html`, `templates/accounts/digital_record.html`
- **Admin:** `templates/admin/index.html`

### 2.2 Static Assets (`static/`)
- **CSS:** `static/css/site.css` (global tokens, components, auth, landing), `static/css/institution-dashboard.css` (institution portal overrides)
- **JS:** `static/js/institution-ui.js`
- **Brand Assets:** Inline SVG/badge logo mark (`P` + `PaperLoop` wordmark) and Bootstrap 5.3.9 CDN.

---

## 3. Proposed PaperLoop Design Language (Lighter × PaperLoop)

We will combine **Lighter's** airy, rounded-card, pill-driven SaaS structure with **PaperLoop's** forest-green environmental brand identity.

### 3.1 Color Palette
| Token | Hex | Usage |
| :--- | :--- | :--- |
| `--color-dark` | `#0D392C` | Deep Forest Green — Primary CTAs, dark footer/CTA cards, headings |
| `--color-primary` | `#176B3A` | Primary Green — Active states, links, badges, accents |
| `--color-secondary` | `#238B50` | Secondary Green — Hover states, gradients, positive indicators |
| `--color-soft` | `#EAF4ED` | Soft Green — Pill backgrounds, icon containers, subtle highlights |
| `--color-bg` | `#F5F8F5` | Page Background — Airy pale-green outer canvas (replacing Lighter's `#F7F7F7`) |
| `--color-surface` | `#FFFFFF` | Card Surface — Crisp white rounded section & content cards |
| `--color-text` | `#24332A` | Dark Text — Primary body copy and labels |
| `--color-muted` | `#77817B` | Muted Text — Subtitles, captions, secondary metadata |
| `--color-border` | `#E1E9E2` | Border — Thin `1px` neutral-green card and input borders |

### 3.2 Typography
- **Font Family:** `Inter`, system-ui sans-serif.
- **Hierarchy:**
  - **Display Hero:** `clamp(2.5rem, 5vw, 4.25rem)`, weight `700–800`, tight tracking (`-0.04em`), `#0D392C`.
  - **Section H2:** `clamp(1.75rem, 3.5vw, 2.75rem)`, weight `700`, `#0D392C`.
  - **Card / Component Titles:** `1.125rem–1.35rem`, weight `650–700`.
  - **Body:** `1rem`, line-height `1.6`, `#24332A` / `#77817B`.

### 3.3 Layout System & Surface Treatment
- **Outer Canvas:** `#F5F8F5` with subtle dotted grid overlay on hero and CTA sections.
- **Rounded Section Containers:** Major landing sections sit inside crisp `#FFFFFF` cards with `20px–24px` border radius and `1px solid #E1E9E2` borders.
- **4px Spacing Scale:** Consistent padding (`24px–48px` inside cards, `48px–80px` between sections).

### 3.4 Reusable Components
- **Floating Pill Navbar:** Left PaperLoop logo, center white pill nav links, right `#0D392C` pill CTA.
- **Eyebrow Pill Badges:** `• Label` with soft-green or white-shadow pill styling.
- **Pill Buttons:** Primary (`#0D392C` fill, white text, soft shadow) and Secondary (`#FFFFFF` fill, `1px solid #E1E9E2`, `#24332A` text).
- **Service / Capability Rows:** Full-width rounded pill rows (`border-radius: 16px`, `1px solid #E1E9E2`) with hover elevation.
- **Floating Metric Cards:** Overlapping white/glassmorphic stat cards with percentage/impact pills.
- **FAQ Accordion & Carousels:** Clean `+`/`-` expandable rows and previous/next slide controls.
- **Dark Rounded Footer:** `#0D392C` rounded container with dotted grid, 4-column links, and `Back to Top ^`.

### 3.5 Animation Strategy
- **Entrance & Scroll:** Subtle `fadeInUp` reveals (`240ms–380ms`, `cubic-bezier(0.16, 1, 0.3, 1)`).
- **Hover:** `translateY(-2px)` card elevation and smooth border/shadow transitions.
- **Ambient:** Gentle floating motion on hero/auth orbit cards.
- **Accessibility:** Full `prefers-reduced-motion: reduce` support disabling non-essential motion.

---

## 4. Page-by-Page Redesign & Responsive Strategy

1. **Public Pages (`landing.html`, `about.html`):** Adopt Lighter's 3-part pill navbar, rounded white hero card with inline visual pills, asymmetric About + floating metric cards, full-width capability rows, interactive Process/Impact carousels, FAQ accordion, dark forest-green CTA card, and rounded `#0D392C` footer.
2. **Authentication (`login.html`, `register.html`, `verification_pending.html`, `password_reset_*`):** Preserve the split-screen `#0D392C` left story panel + `#F5F8F5` right form card, aligning radii, pill buttons, and typography with the Lighter system.
3. **Institution Portal (`institution_dashboard.html`, `listing_form.html`, `listing_recommendations.html`, `partner_directory.html`, etc.):** White left sidebar with `#176B3A` active indicator, `#F5F8F5` canvas, rounded white stat/table cards, and pill actions.
4. **Recycler & Admin Portals (`partner_dashboard.html`, `partner_profile_*`, `admin/index.html`):** Distinct role-appropriate layouts sharing the same `#0D392C` / `#176B3A` / `#F5F8F5` token system.
5. **Responsive Strategy:** Desktop (`≥1200px`) multi-column grids and sticky sidebars; Tablet (`768px–1199px`) 2-column grids and collapsible navigation; Mobile (`<768px`) single-column stacked cards, simplified decorative panels, and zero horizontal overflow.
