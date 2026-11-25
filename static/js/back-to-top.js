(() => {
  "use strict";

  const button = document.querySelector("[data-back-to-top]");
  if (!button) return;

  const threshold = 300;
  let framePending = false;

  function syncVisibility() {
    framePending = false;
    const visible = window.scrollY >= threshold;
    button.classList.toggle("is-visible", visible);
    button.setAttribute("aria-hidden", String(!visible));
    button.tabIndex = visible ? 0 : -1;
    if (!visible && document.activeElement === button) button.blur();
  }

  function onScroll() {
    if (framePending) return;
    framePending = true;
    window.requestAnimationFrame(syncVisibility);
  }

  function onClick() {
    const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: 0, behavior: reducedMotion ? "instant" : "smooth" });
  }

  window.addEventListener("scroll", onScroll, { passive: true });
  button.addEventListener("click", onClick);
  window.addEventListener("pagehide", () => {
    window.removeEventListener("scroll", onScroll);
    button.removeEventListener("click", onClick);
  }, { once: true });
  syncVisibility();
})();
