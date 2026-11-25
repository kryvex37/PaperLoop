import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";

class Classes {
  values = new Set();
  toggle(name, force) {
    const active = force ?? !this.values.has(name);
    active ? this.values.add(name) : this.values.delete(name);
    return active;
  }
  add(name) { this.values.add(name); }
  remove(name) { this.values.delete(name); }
  contains(name) { return this.values.has(name); }
}

class Link {
  constructor(label, href, nav) {
    this.label = label;
    this.href = href;
    this.nav = nav;
    this.target = "";
    this.attributes = {};
    this.classList = new Classes();
  }
  closest(selector) { return selector === ".site-header nav" || selector === "a[href]" ? this.nav : null; }
  setAttribute(name, value) { this.attributes[name] = value; }
  getAttribute(name) { return this.attributes[name] ?? null; }
  removeAttribute(name) { delete this.attributes[name]; }
}

const navListeners = {};
const nav = {
  attributes: {},
  addEventListener(name, callback) { navListeners[name] = callback; },
  setAttribute(name, value) { this.attributes[name] = value; },
  removeAttribute(name) { delete this.attributes[name]; },
};
const links = [
  new Link("Home", "http://paperloop.test/accounts/landing/", nav),
  new Link("About", "http://paperloop.test/accounts/about/", nav),
  new Link("How It Works", "http://paperloop.test/accounts/landing/#how-it-works", nav),
  new Link("Features", "http://paperloop.test/accounts/landing/#features", nav),
  new Link("Contact", "http://paperloop.test/accounts/landing/#contact", nav),
  new Link("Sign In", "http://paperloop.test/accounts/login/", nav),
];
const sections = new Map(["how-it-works", "features", "contact"].map((id) => [id, { id }]));
const observers = [];
const documentListeners = {};
const windowListeners = {};
const location = { origin: "http://paperloop.test", pathname: "/accounts/landing/", hash: "" };
Object.defineProperty(location, "href", { get() { return `${this.origin}${this.pathname}${this.hash}`; } });
let timerId = 0;

const document = {
  documentElement: { classList: new Classes() },
  querySelectorAll(selector) {
    if (selector === ".site-header nav a[href]") return links;
    if (selector === ".site-header nav a[href*='#']") return links.filter((link) => link.href.includes("#"));
    return [];
  },
  querySelector(selector) { return selector === ".site-header" ? { classList: new Classes() } : null; },
  getElementById(id) { return sections.get(id) ?? null; },
  addEventListener(name, callback) { documentListeners[name] = callback; },
};
const window = {
  location,
  innerHeight: 900,
  scrollY: 0,
  matchMedia: () => ({ matches: false, addEventListener() {} }),
  addEventListener(name, callback) { (windowListeners[name] ??= []).push(callback); },
  requestAnimationFrame(callback) { callback(); return 1; },
  setTimeout() { return ++timerId; },
  clearTimeout() {},
};
class IntersectionObserver {
  constructor(callback) { this.callback = callback; observers.push(this); }
  observe() {}
  unobserve() {}
}
window.IntersectionObserver = IntersectionObserver;

const source = await readFile(new URL("../static/js/institution-ui.js", import.meta.url), "utf8");
vm.runInNewContext(source, { document, window, URL, IntersectionObserver, requestAnimationFrame: window.requestAnimationFrame });

const activeLink = () => links.filter((link) => link.classList.contains("is-nav-current"));
const assertActive = (label) => assert.deepEqual(activeLink().map((link) => link.label), [label]);
const click = (link) => navListeners.click({
  target: { closest: () => link }, defaultPrevented: false, button: 0,
  metaKey: false, ctrlKey: false, shiftKey: false, altKey: false,
});
const fire = (name) => (windowListeners[name] || []).forEach((callback) => callback());
const sectionObserver = observers[0];

assertActive("Home");
click(links[0]); assertActive("Home");
click(links[1]); assertActive("About");
location.pathname = "/accounts/about/"; fire("pageshow"); assertActive("About");

for (const [index, id] of [[2, "how-it-works"], [3, "features"], [4, "contact"]]) {
  click(links[index]); assertActive(links[index].label);
  location.pathname = "/accounts/landing/";
  location.hash = `#${id}`;
  fire("hashchange");
  sectionObserver.callback([{ target: sections.get(id), isIntersecting: true, intersectionRatio: 0.8 }]);
  assertActive(links[index].label);
}

click(links[5]); assertActive("Sign In");
location.pathname = "/accounts/login/"; location.hash = ""; fire("pageshow"); assertActive("Sign In");
location.pathname = "/accounts/landing/"; location.hash = "#features"; fire("popstate"); assertActive("Features");
location.pathname = "/accounts/about/"; location.hash = ""; fire("popstate"); assertActive("About");
console.log("Navigation active state checks passed (all six links, section visibility, and browser history).");
