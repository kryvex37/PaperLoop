(() => {
  "use strict";
  const KEY = "paperloop.theme";
  const valid = new Set(["light", "dark", "forest", "system"]);
  const media = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  const root = document.documentElement;
  let preference = "system";

  function readPreference() {
    try {
      const saved = window.localStorage.getItem(KEY);
      return valid.has(saved) ? saved : "system";
    } catch (_) { return "system"; }
  }
  function effectiveTheme(value) {
    if (value === "system") return media && media.matches ? "dark" : "light";
    return value;
  }
  function updateControls() {
    document.querySelectorAll("[data-theme-option]").forEach((button) => {
      const active = button.dataset.themeOption === preference;
      button.setAttribute("aria-pressed", String(active));
      button.classList.toggle("is-active", active);
    });
    document.querySelectorAll("[data-theme-current]").forEach((label) => {
      label.textContent = preference.charAt(0).toUpperCase() + preference.slice(1);
    });
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      const mode = preference === "system" ? effectiveTheme("system") : preference;
      const icon = mode === "dark" ? "moon" : mode === "forest" ? "tree-pine" : "sun";
      const use = button.querySelector("use");
      if (use) use.setAttribute("href", `${use.getAttribute("href").split("#")[0]}#icon-${icon}`);
    });
  }
  function apply(value, persist = false) {
    preference = valid.has(value) ? value : "system";
    root.dataset.themePreference = preference;
    root.dataset.theme = effectiveTheme(preference);
    if (persist) {
      try { window.localStorage.setItem(KEY, preference); } catch (_) { /* Storage can be disabled. */ }
    }
    updateControls();
    window.dispatchEvent(new CustomEvent("paperloop:themechange", { detail: { preference, theme: root.dataset.theme } }));
  }

  apply(readPreference());
  document.addEventListener("click", (event) => {
    const choice = event.target.closest("[data-theme-option]");
    if (choice) {
      apply(choice.dataset.themeOption, true);
      const owner = choice.closest("[data-theme-switcher]");
      if (owner && owner.dataset.themeVariant !== "settings") close(owner, false);
      return;
    }
    const toggle = event.target.closest("[data-theme-toggle]");
    if (toggle) {
      const owner = toggle.closest("[data-theme-switcher]");
      const opened = owner.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", String(opened));
      const menu = owner.querySelector("[data-theme-options]");
      if (menu) menu.hidden = !opened;
      if (opened) owner.querySelector("[data-theme-option].is-active")?.focus();
      return;
    }
    document.querySelectorAll("[data-theme-switcher].is-open").forEach((owner) => close(owner, false));
  });
  document.addEventListener("keydown", (event) => {
    const owner = event.target.closest?.("[data-theme-switcher].is-open");
    if (!owner) return;
    if (event.key === "Escape") { close(owner, true); return; }
    if (["ArrowDown", "ArrowUp"].includes(event.key) && event.target.matches("[data-theme-option]")) {
      event.preventDefault();
      const options = [...owner.querySelectorAll("[data-theme-option]")];
      const next = (options.indexOf(event.target) + (event.key === "ArrowDown" ? 1 : -1) + options.length) % options.length;
      options[next].focus();
    }
  });
  function close(owner, restoreFocus) {
    owner.classList.remove("is-open");
    const trigger = owner.querySelector("[data-theme-toggle]");
    const menu = owner.querySelector("[data-theme-options]");
    if (trigger) { trigger.setAttribute("aria-expanded", "false"); if (restoreFocus) trigger.focus(); }
    if (menu && owner.dataset.themeVariant !== "settings") menu.hidden = true;
  }
  if (media) {
    const onSystemChange = () => { if (preference === "system") apply("system"); };
    if (media.addEventListener) media.addEventListener("change", onSystemChange);
    else if (media.addListener) media.addListener(onSystemChange);
  }
  requestAnimationFrame(() => root.classList.add("theme-ready"));
})();
