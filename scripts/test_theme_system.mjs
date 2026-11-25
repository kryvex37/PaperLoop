import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";

class Classes {
  values = new Set();
  add(name) { this.values.add(name); }
  remove(name) { this.values.delete(name); }
  toggle(name, force) { const next = force ?? !this.values.has(name); next ? this.values.add(name) : this.values.delete(name); return next; }
  contains(name) { return this.values.has(name); }
}
class FakeElement {
  constructor(dataset = {}) { this.dataset = dataset; this.attributes = {}; this.classList = new Classes(); this.textContent = ""; this.href = "/static/icons.svg#icon-monitor"; this.hidden = true; this.focused = false; }
  setAttribute(key, value) { this.attributes[key] = value; }
  getAttribute(key) { return key === "href" ? this.href : this.attributes[key]; }
  querySelector(selector) { return selector === "use" ? this.use : null; }
  closest(selector) { if (selector === "[data-theme-option]") return this.option || null; if (selector === "[data-theme-toggle]") return this.toggle || null; if (selector === "[data-theme-switcher]") return this.owner || null; return null; }
  focus() { this.focused = true; }
}

const options = ["light", "dark", "forest", "system"].map((theme) => new FakeElement({ themeOption: theme }));
const themeCss = await readFile(new URL("../static/css/paperloop-themes.css", import.meta.url), "utf8");
const cssStructure = themeCss.replace(/\/\*[\s\S]*?\*\//g, "").replace(/"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'/g, "");
for (const [opening, closing] of [["{", "}"], ["(", ")"]]) {
  let depth = 0;
  for (const character of cssStructure) {
    if (character === opening) depth += 1;
    if (character === closing) depth -= 1;
    assert.ok(depth >= 0, `CSS ${closing} is paired`);
  }
  assert.equal(depth, 0, `CSS ${opening}${closing} blocks are balanced`);
}
for (const color of ["#E3EDE3", "#DCE8DF", "#F0F5EF", "#176B3A", "#174D31", "#496653", "#C9D9CB", "#D3E2D5"]) {
  assert.match(themeCss, new RegExp(color, "i"), `the required soft green token ${color} exists`);
}
const semanticTokens = ["page-bg", "section-bg", "card-bg", "card-hover", "navbar-bg", "sidebar-bg", "input-bg", "text-primary", "text-secondary", "text-muted", "heading", "link", "link-hover", "border", "primary", "primary-hover", "button-text", "shadow", "focus-ring"];
for (const token of [...semanticTokens, "eyebrow-on-strong"]) assert.match(themeCss, new RegExp(`--color-${token}:`), `semantic token --color-${token} exists`);
for (const selector of [".landing-hero", ".about-hero", ".dashboard-hero", ".recycler-hero", ".landing-ai", ".landing-final-cta", ".sustainability-panel", ".signin-story .story-kicker", ".landing-ecosystem", ".about-purpose", ".pl-theme-options", ".site-header > nav"]) {
  assert.ok(themeCss.includes(selector), `theme-aware hero or dark-panel styling covers ${selector}`);
}
assert.ok(themeCss.includes("body:is(.landing-page,.about-page) .site-header"), "public navbar rules match classes applied to the body element");
assert.ok(themeCss.includes("body.landing-page .landing-container"), "landing surface rules match the landing body class");
const themeBlocks = [themeCss.slice(themeCss.indexOf(":root {"), themeCss.indexOf("html[data-theme=\"dark\"]")), themeCss.slice(themeCss.indexOf('html[data-theme="dark"]'), themeCss.indexOf('html[data-theme="forest"]')), themeCss.slice(themeCss.indexOf('html[data-theme="forest"]'), themeCss.indexOf("html, body"))];
for (const [index, block] of themeBlocks.entries()) {
  for (const token of semanticTokens) assert.match(block, new RegExp(`--color-${token}:`), `theme ${index + 1} defines --color-${token}`);
}
const contrastThemes = [
  { name: "Light", page: "#E3EDE3", section: "#DCE8DF", card: "#F0F5EF", cardHover: "#D3E2D5", navbar: "#DCE8DF", sidebar: "#D6E3D8", input: "#FFFFFF", heading: "#174D31", secondary: "#496653", muted: "#496653", link: "#176B3A", strong: "#174D31", strongLink: "#EAF4ED", eyebrowStrong: "#8BD4A3", button: "#176B3A", buttonHover: "#12552E", buttonText: "#FFFFFF", statuses: [["#176B3A", "#DCE8DF"], ["#73500F", "#FEF4DA"], ["#8C3030", "#FCEBE8"], ["#155A74", "#E6F3F7"]] },
  { name: "Dark", page: "#111B16", section: "#17251D", card: "#1C2921", cardHover: "#24372B", navbar: "#17251D", sidebar: "#17251D", input: "#17251D", heading: "#EDF5EF", secondary: "#BDCCBF", muted: "#BDCCBF", link: "#8BD4A3", strong: "#0D392C", strongLink: "#B6E6C4", eyebrowStrong: "#8BD4A3", button: "#55B77A", buttonHover: "#8BD4A3", buttonText: "#102117", statuses: [["#8BD4A3", "#1D3928"], ["#F2CC78", "#3B321E"], ["#FFAAA0", "#3A2421"], ["#8BD2E8", "#1E3440"]] },
  { name: "Forest", page: "#0D392C", section: "#124433", card: "#174A39", cardHover: "#205642", navbar: "#124433", sidebar: "#124433", input: "#123F30", heading: "#F0F8F1", secondary: "#C5DCCB", muted: "#C5DCCB", link: "#8BD4A3", strong: "#0D392C", strongLink: "#C5DCCB", eyebrowStrong: "#B6E6C4", button: "#8BD4A3", buttonHover: "#B6E6C4", buttonText: "#0D392C", statuses: [["#8BD4A3", "#1C4938"], ["#F2CC78", "#3D351F"], ["#FFAAA0", "#3F2925"], ["#8BD2E8", "#1D3841"]] },
];
const channel = (value) => { const normalized = Number.parseInt(value, 16) / 255; return normalized <= .04045 ? normalized / 12.92 : ((normalized + .055) / 1.055) ** 2.4; };
const luminance = (color) => { const hex = color.slice(1); return .2126 * channel(hex.slice(0, 2)) + .7152 * channel(hex.slice(2, 4)) + .0722 * channel(hex.slice(4, 6)); };
const contrast = (first, second) => { const values = [luminance(first), luminance(second)].sort((a, b) => b - a); return (values[0] + .05) / (values[1] + .05); };
for (const theme of contrastThemes) {
  for (const background of [theme.page, theme.section, theme.card, theme.sidebar, theme.input]) {
    for (const [role, foreground] of [["heading", theme.heading], ["body", theme.secondary], ["muted", theme.muted], ["link", theme.link]]) {
      assert.ok(contrast(foreground, background) >= 4.5, `${theme.name} ${role} contrast on ${background} meets WCAG AA`);
    }
  }
  assert.ok(contrast(theme.link, theme.navbar) >= 4.5, `${theme.name} navbar link contrast meets WCAG AA`);
  assert.ok(contrast(theme.secondary, theme.navbar) >= 4.5, `${theme.name} theme-name label contrast meets WCAG AA`);
  assert.ok(contrast(theme.heading, theme.cardHover) >= 4.5, `${theme.name} selected theme option contrast meets WCAG AA`);
  assert.ok(contrast(theme.button, theme.card) >= 4.5, `${theme.name} theme-switcher icon contrast meets WCAG AA`);
  assert.ok(contrast(theme.buttonText, theme.button) >= 4.5, `${theme.name} button label contrast meets WCAG AA`);
  assert.ok(contrast(theme.buttonText, theme.buttonHover) >= 4.5, `${theme.name} hovered button label contrast meets WCAG AA`);
  assert.ok(contrast(theme.strongLink, theme.strong) >= 4.5, `${theme.name} links on dark callout panels meet WCAG AA`);
  assert.ok(contrast(theme.eyebrowStrong, "#0A3024") >= 4.5, `${theme.name} eyebrow on the dark AI section meets WCAG AA`);
  for (const [foreground, background] of theme.statuses) assert.ok(contrast(foreground, background) >= 4.5, `${theme.name} semantic status contrast meets WCAG AA`);
}
const owner = new FakeElement({ themeVariant: "settings" });
const trigger = new FakeElement();
const use = new FakeElement();
trigger.use = use;
trigger.owner = owner;
const current = new FakeElement();
const html = new FakeElement();
html.dataset = {};
const mediaListeners = [];
const media = { matches: false, addEventListener: (_event, listener) => mediaListeners.push(listener) };
const handlers = {};
const document = {
  documentElement: html,
  querySelectorAll(selector) {
    if (selector === "[data-theme-option]") return options;
    if (selector === "[data-theme-current]") return [current];
    if (selector === "[data-theme-toggle]") return [trigger];
    return [];
  },
  addEventListener(name, handler) { handlers[name] = handler; },
};
const stored = new Map([["paperloop.theme", "forest"]]);
const window = { matchMedia: () => media, localStorage: { getItem: (key) => stored.get(key) ?? null, setItem: (key, value) => stored.set(key, value) }, dispatchEvent() {} };
const sandbox = { window, document, CustomEvent: class { constructor(type, init) { this.type = type; this.detail = init.detail; } }, requestAnimationFrame: (fn) => fn() };
vm.runInNewContext(await readFile(new URL("../static/js/theme-system.js", import.meta.url), "utf8"), sandbox);
assert.equal(html.dataset.theme, "forest", "saved theme is applied at startup");
assert.equal(options[2].attributes["aria-pressed"], "true", "selected theme is announced");
assert.equal(current.textContent, "Forest", "dropdown exposes the active mode");

const selectDark = new FakeElement();
selectDark.option = options[1];
handlers.click({ target: selectDark });
assert.equal(html.dataset.theme, "dark", "theme can change without reload");
assert.equal(stored.get("paperloop.theme"), "dark", "selected mode persists");

const selectSystem = new FakeElement();
selectSystem.option = options[3];
handlers.click({ target: selectSystem });
assert.equal(html.dataset.theme, "light", "system mode resolves the initial OS preference");
media.matches = true;
mediaListeners[0]();
assert.equal(html.dataset.theme, "dark", "system mode responds to OS theme changes");
assert.equal(stored.get("paperloop.theme"), "system", "system preference remains persisted");
console.log("Theme system interaction checks passed (startup, live selection, persistence, OS changes).");
