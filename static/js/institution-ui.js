(() => {
  "use strict";

  document.querySelectorAll("[data-auth-motion-toggle]").forEach((toggle) => {
    const page = toggle.closest(".signin-page");
    if (!page) return;
    const label = toggle.querySelector("[data-motion-label]");
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const setMotion = (enabled) => {
      enabled = enabled && !reducedMotion.matches;
      page.classList.toggle("motion-enabled", enabled);
      page.classList.toggle("motion-paused", !enabled);
      toggle.setAttribute("aria-pressed", String(enabled));
      toggle.disabled = reducedMotion.matches;
      toggle.setAttribute("aria-label", reducedMotion.matches ? "Motion disabled by reduced motion preference" : enabled ? "Pause ambient motion" : "Resume ambient motion");
      if (label) label.textContent = reducedMotion.matches ? "Motion reduced" : enabled ? "Pause motion" : "Resume motion";
    };
    setMotion(!reducedMotion.matches);
    toggle.addEventListener("click", () => setMotion(!page.classList.contains("motion-enabled")));
    reducedMotion.addEventListener?.("change", (event) => {
      setMotion(!event.matches);
    });
  });

  document.querySelectorAll("[data-quantity-comparison]").forEach((comparison) => {
    const estimate = Number(comparison.dataset.estimated);
    const input = document.getElementById("id_final_collected_quantity_kg");
    const actualOutput = comparison.querySelector("[data-quantity-actual]");
    const differenceOutput = comparison.querySelector("[data-quantity-difference]");
    if (!Number.isFinite(estimate) || !actualOutput || !differenceOutput) return;
    const format = (value) => new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value);
    const awaitingActual = input ? "Enter measured weight" : "Awaiting partner confirmation";
    const awaitingDifference = input ? "Shown as you enter a weight" : "Confirmed after pickup";
    const update = (rawValue) => {
      const actual = Number(rawValue);
      if (!rawValue || !Number.isFinite(actual) || actual <= 0) {
        actualOutput.textContent = awaitingActual;
        differenceOutput.textContent = awaitingDifference;
        comparison.classList.remove("is-over", "is-under", "is-equal");
        return;
      }
      const difference = Number((actual - estimate).toFixed(2));
      actualOutput.textContent = `${format(actual)} kg`;
      differenceOutput.textContent = `${difference > 0 ? "+" : difference < 0 ? "−" : ""}${format(Math.abs(difference))} kg`;
      comparison.classList.toggle("is-over", difference > 0);
      comparison.classList.toggle("is-under", difference < 0);
      comparison.classList.toggle("is-equal", difference === 0);
    };
    update(input?.value || comparison.dataset.actual);
    input?.addEventListener("input", () => update(input.value));
  });

  document.querySelectorAll("[data-table-filter]").forEach((form) => {
    const table = document.querySelector(form.dataset.tableTarget || "");
    if (!table) return;

    const rows = Array.from(table.querySelectorAll("tbody [data-filter-row], [data-filter-row]"));
    const count = document.querySelector(form.dataset.countTarget || "");
    const controls = Array.from(form.querySelectorAll("[data-filter-field]"));

    const applyFilters = () => {
      const values = Object.fromEntries(controls.map((control) => [
        control.dataset.filterField,
        control.value.trim().toLocaleLowerCase(),
      ]));
      let visible = 0;

      rows.forEach((row) => {
        const searchMatches = !values.search || (row.dataset.search || "").toLocaleLowerCase().includes(values.search);
        const statusMatches = !values.status || row.dataset.status === values.status;
        const categoryMatches = !values.category || row.dataset.category === values.category;
        const date = row.dataset.date || "";
        const fromMatches = !values.from || date >= values.from;
        const toMatches = !values.to || date <= values.to;
        const matches = searchMatches && statusMatches && categoryMatches && fromMatches && toMatches;
        row.hidden = !matches;
        if (matches) visible += 1;
      });

      if (count) count.textContent = `${visible} of ${rows.length} shown`;
    };

    form.addEventListener("submit", (event) => event.preventDefault());
    controls.forEach((control) => control.addEventListener(
      control.tagName === "SELECT" || control.type === "date" ? "change" : "input",
      applyFilters,
    ));
    form.querySelectorAll("[data-filter-reset]").forEach((button) => {
      button.addEventListener("click", () => {
        form.reset();
        applyFilters();
      });
    });
    applyFilters();
  });

  const syncSidebarAnchor = () => {
    const activeAnchor = window.location.hash.slice(1);
    if (!activeAnchor) return;
    document.querySelectorAll("[data-sidebar-anchor]").forEach((link) => {
      const active = activeAnchor && link.dataset.sidebarAnchor === activeAnchor;
      link.classList.toggle("active", Boolean(active));
      if (active) link.setAttribute("aria-current", "location");
      else link.removeAttribute("aria-current");
    });
  };
  window.addEventListener("hashchange", syncSidebarAnchor);
  syncSidebarAnchor();

  const sidebarSections = Array.from(document.querySelectorAll("[data-sidebar-anchor]"))
    .map((link) => document.getElementById(link.dataset.sidebarAnchor))
    .filter(Boolean);
  if (sidebarSections.length && "IntersectionObserver" in window) {
    const sidebarObserver = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting)
        .sort((first, second) => second.intersectionRatio - first.intersectionRatio)[0];
      if (!visible) return;
      document.querySelectorAll("[data-sidebar-anchor]").forEach((link) => {
        const active = link.dataset.sidebarAnchor === visible.target.id;
        link.classList.toggle("active", active);
        if (active) link.setAttribute("aria-current", "location");
        else if (link.getAttribute("aria-current") === "location") link.removeAttribute("aria-current");
      });
    }, { threshold: [0.15, 0.35, 0.6], rootMargin: "-18% 0px -58% 0px" });
    sidebarSections.forEach((section) => sidebarObserver.observe(section));
  }

  const completedCollections = Array.from(document.querySelectorAll("[data-sustainability-collection='collected']"));
  document.querySelectorAll("[data-collection-empty-state]").forEach((element) => {
    element.hidden = document.querySelector("[data-sustainability-collection]") !== null;
  });
  const totalWeight = completedCollections.reduce((total, element) => {
    const weight = Number.parseFloat(element.dataset.finalKg || "0");
    return total + (Number.isFinite(weight) ? weight : 0);
  }, 0);
  document.querySelectorAll("[data-sustainability-count]").forEach((element) => {
    element.textContent = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(completedCollections.length);
  });
  document.querySelectorAll("[data-sustainability-weight]").forEach((element) => {
    element.textContent = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(totalWeight);
  });

  document.querySelectorAll("[data-mobile-nav-toggle]").forEach((toggle) => {
    const navigation = document.getElementById(toggle.getAttribute("aria-controls"));
    if (!navigation) return;

    const setOpen = (open) => {
      toggle.setAttribute("aria-expanded", String(open));
      navigation.classList.toggle("is-open", open);
    };

    toggle.addEventListener("click", () => {
      setOpen(toggle.getAttribute("aria-expanded") !== "true");
    });
    navigation.addEventListener("click", (event) => {
      if (event.target.closest("a")) setOpen(false);
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") setOpen(false);
    });
    window.addEventListener("resize", () => {
      if (window.matchMedia("(min-width: 761px)").matches) setOpen(false);
    });
  });

  const motionPage = document.querySelector(".landing-page, .about-page");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const motionCandidates = [
    ".dashboard-hero", ".recycler-hero", ".paperloop-admin-hero",
    ".stat-card", ".recycler-kpi-card", ".recommendation-card", ".recycler-discovery-card",
    ".recycler-listing-card", ".paperloop-admin-overview-card", ".paperloop-admin-register-card",
    ".feature-editorial", ".process-step", ".impact-metric", ".purpose-card", ".about-process-step",
    ".collection-stage", ".ai-preview-wrap", ".sustainability-panel", ".collection-progress-card",
    ".sustainability-about-art", ".sustainability-about-copy", ".about-match-visual",
    ".card-saas", ".table-responsive", ".empty-state", ".recycler-profile-settings",
    ".institution-sidebar-panel", ".recycler-sidebar-panel", ".paperloop-admin-quicknav",
  ].join(",");
  document.querySelectorAll(motionCandidates).forEach((element) => {
    if (!element.hasAttribute("data-no-motion")) element.setAttribute("data-motion-reveal", "");
  });
  document.querySelectorAll(".page-shell .card:not(.modal-content), .paperloop-admin-dashboard .paperloop-admin-activity, .paperloop-admin-dashboard .paperloop-admin-transaction-card, .testimonial-card, .testimonial-section").forEach((element) => {
    if (!element.hasAttribute("data-no-motion")) element.setAttribute("data-motion-reveal", "");
  });
  document.querySelectorAll("main h1:not([data-reveal]), #content h1:not([data-reveal])").forEach((heading) => {
    if (!heading.closest("[data-motion-reveal], [data-no-motion]")) heading.setAttribute("data-motion-reveal", "heading");
  });
  document.querySelectorAll("main img:not(.brand-logo-image):not([data-no-motion]), #content img:not(.brand-logo-image):not([data-no-motion])").forEach((image) => {
    if (!image.hasAttribute("data-image-reveal")) image.setAttribute("data-image-reveal", "");
  });

  document.querySelectorAll(".stat-value, .recycler-kpi-number").forEach((metric) => {
    if (metric.hasAttribute("data-target") || metric.hasAttribute("data-no-count") || metric.querySelector("span")) return;
    const renderedValue = metric.textContent.trim();
    const normalizedValue = renderedValue.replace(/,/g, "");
    if (!/^-?\d+(?:\.\d+)?$/.test(normalizedValue)) return;
    metric.dataset.counter = "";
    metric.dataset.target = normalizedValue;
    const decimals = normalizedValue.split(".")[1]?.length || 0;
    if (decimals) metric.dataset.decimals = String(Math.min(decimals, 2));
  });

  const revealItems = Array.from(document.querySelectorAll("[data-reveal], [data-motion-reveal], [data-image-reveal]"));
  const counters = Array.from(document.querySelectorAll("[data-counter][data-target]"));
  const parallaxItems = Array.from(document.querySelectorAll("[data-parallax]"));
  const siteHeader = document.querySelector(".site-header");
  let scrollFrame = 0;
  const syncHeader = () => {
    if (scrollFrame) return;
    scrollFrame = requestAnimationFrame(() => {
      scrollFrame = 0;
      siteHeader?.classList.toggle("is-scrolled", window.scrollY > 8);
    });
  };
  window.addEventListener("scroll", syncHeader, { passive: true });
  syncHeader();

  const navigationLinks = Array.from(document.querySelectorAll(".site-header nav a[href]"));
  const navigationBars = [...new Set(navigationLinks.map((link) => link.closest(".site-header nav")).filter(Boolean))];
  const navigationTargets = navigationLinks.map((link) => ({ link, url: new URL(link.href, window.location.href) }));
  let pendingSectionTarget = null;
  let pendingSectionTimer = 0;

  const setActiveNavigation = (activeLink, current = "page") => {
    if (!activeLink) return;
    navigationLinks.forEach((link) => {
      const active = link === activeLink;
      link.classList.toggle("is-nav-current", active);
      link.classList.toggle("is-section-current", active && current === "location");
      if (active) link.setAttribute("aria-current", current);
      else link.removeAttribute("aria-current");
    });
    navigationBars.forEach((navigation) => {
      if (current === "location") navigation.setAttribute("data-section-active", "");
      else navigation.removeAttribute("data-section-active");
    });
  };

  const syncNavigationFromLocation = () => {
    const matchingHash = navigationTargets.find(({ url }) =>
      url.origin === window.location.origin && url.pathname === window.location.pathname &&
      url.hash && url.hash === window.location.hash);
    const matchingRoute = navigationTargets.find(({ url }) =>
      url.origin === window.location.origin && url.pathname === window.location.pathname && !url.hash);
    setActiveNavigation(matchingHash?.link || matchingRoute?.link, matchingHash ? "location" : "page");
    window.clearTimeout(pendingSectionTimer);
    pendingSectionTarget = matchingHash?.url.hash.slice(1) || null;
    if (pendingSectionTarget) {
      pendingSectionTimer = window.setTimeout(() => { pendingSectionTarget = null; }, 2500);
    }
  };

  navigationBars.forEach((navigation) => navigation.addEventListener("click", (event) => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest("a[href]");
    if (!link || !navigationLinks.includes(link) || link.target === "_blank") return;
    const { url } = navigationTargets.find((target) => target.link === link) || {};
    if (!url || url.origin !== window.location.origin) return;

    const isSection = Boolean(url.hash);
    setActiveNavigation(link, isSection ? "location" : "page");
    window.clearTimeout(pendingSectionTimer);
    pendingSectionTarget = isSection ? url.hash.slice(1) : null;
    if (pendingSectionTarget) {
      pendingSectionTimer = window.setTimeout(() => { pendingSectionTarget = null; }, 2500);
    }
  }));

  window.addEventListener("hashchange", syncNavigationFromLocation);
  window.addEventListener("popstate", syncNavigationFromLocation);
  window.addEventListener("pageshow", syncNavigationFromLocation);
  syncNavigationFromLocation();
  let navigationResetFrame = 0;
  window.addEventListener("scroll", () => {
    if (window.scrollY >= 120 || pendingSectionTarget || navigationResetFrame) return;
    navigationResetFrame = window.requestAnimationFrame(() => {
      navigationResetFrame = 0;
      const routeLink = navigationTargets.find(({ url }) =>
        url.origin === window.location.origin && url.pathname === window.location.pathname && !url.hash)?.link;
      if (routeLink) setActiveNavigation(routeLink, "page");
    });
  }, { passive: true });
  const sectionNavigation = Array.from(document.querySelectorAll(".site-header nav a[href*='#']"))
    .map((link) => ({ link, url: new URL(link.href, window.location.href) }))
    .filter(({ url }) => url.pathname === window.location.pathname && url.hash.length > 1)
    .map(({ link, url }) => ({ link, section: document.getElementById(url.hash.slice(1)) }))
    .filter(({ section }) => Boolean(section));
  if (sectionNavigation.length) {
    const syncScrollActive = () => {
      if (pendingSectionTarget) return;
      const scrollY = window.scrollY || window.pageYOffset || 0;
      if (scrollY < 120) {
        const homeLink = navigationTargets.find(({ url }) =>
          url.origin === window.location.origin && url.pathname === window.location.pathname && !url.hash)?.link;
        if (homeLink) setActiveNavigation(homeLink, "page");
        return;
      }

      // Check if user has scrolled near bottom of page (where Contact is located)
      const windowHeight = window.innerHeight;
      const docHeight = document.documentElement.scrollHeight;
      const isAtBottom = (windowHeight + scrollY) >= (docHeight - 120);

      // Choose focal point: if at bottom of page, anchor to bottom; otherwise use 30% from viewport top (below header)
      const focalLine = isAtBottom ? (windowHeight - 80) : Math.max(100, windowHeight * 0.3);

      // Find section enclosing the focal line
      let matched = sectionNavigation.find(({ section }) => {
        const rect = section.getBoundingClientRect();
        return rect.top <= focalLine && rect.bottom >= focalLine;
      });

      // If no section directly encloses the focal line, pick section closest to focal line
      if (!matched) {
        const sorted = [...sectionNavigation].sort((a, b) => {
          const rectA = a.section.getBoundingClientRect();
          const rectB = b.section.getBoundingClientRect();
          const distA = Math.min(Math.abs(rectA.top - focalLine), Math.abs(rectA.bottom - focalLine));
          const distB = Math.min(Math.abs(rectB.top - focalLine), Math.abs(rectB.bottom - focalLine));
          return distA - distB;
        });
        matched = sorted[0];
      }

      if (matched) {
        setActiveNavigation(matched.link, "location");
      }
    };

    let scrollNavThrottle = 0;
    window.addEventListener("scroll", () => {
      if (scrollNavThrottle) return;
      scrollNavThrottle = window.requestAnimationFrame(() => {
        scrollNavThrottle = 0;
        syncScrollActive();
      });
    }, { passive: true });

    window.addEventListener("scrollend", () => {
      if (pendingSectionTarget) {
        pendingSectionTarget = null;
        window.clearTimeout(pendingSectionTimer);
      }
      syncScrollActive();
    });

    // Run initial check
    syncScrollActive();
  }

  document.addEventListener("shown.bs.tab", (event) => {
    const trigger = event.target;
    const paneId = trigger?.getAttribute("data-bs-target")?.replace(/^#/, "") || trigger?.getAttribute("aria-controls");
    const pane = paneId ? document.getElementById(paneId) : null;
    if (!pane) return;
    pane.classList.remove("motion-tab-enter");
    requestAnimationFrame(() => pane.classList.add("motion-tab-enter"));
  });

  const revealImmediately = () => revealItems.forEach((item) => item.classList.add("is-visible"));
  const animateCounter = (element) => {
    if (element.dataset.counted === "true") return;
    const target = Number(element.dataset.target);
    if (!Number.isFinite(target)) return;
    element.dataset.counted = "true";
    const decimals = Math.max(0, Math.min(2, Number(element.dataset.decimals) || 0));
    if (reduceMotion.matches) {
      element.textContent = target.toLocaleString(undefined, { maximumFractionDigits: decimals });
      return;
    }
    const startedAt = performance.now();
    const duration = 950;
    const tick = (now) => {
      const progress = Math.min((now - startedAt) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 4);
      const value = Math.round(target * eased * (10 ** decimals)) / (10 ** decimals);
      element.textContent = value.toLocaleString(undefined, { maximumFractionDigits: decimals });
      if (progress < 1 && !reduceMotion.matches) requestAnimationFrame(tick);
      else element.textContent = target.toLocaleString(undefined, { maximumFractionDigits: decimals });
    };
    requestAnimationFrame(tick);
  };

  if (reduceMotion.matches || !("IntersectionObserver" in window)) {
    revealImmediately();
    if (reduceMotion.matches) counters.forEach(animateCounter);
  } else {
    document.documentElement.classList.add("motion-system-ready");
    motionPage?.classList.add("motion-ready");
    if (revealItems.length) {
      const staggerGroupSelector = ".row, .paperloop-admin-overview-grid, .paperloop-admin-register-grid, .process-track, .impact-grid, .feature-grid, .landing-actions";
      revealItems.forEach((item) => {
        const group = item.closest(staggerGroupSelector);
        const siblings = group
          ? revealItems.filter((candidate) => candidate.closest(staggerGroupSelector) === group)
          : item.parentElement ? Array.from(item.parentElement.children).filter((child) => child.matches("[data-reveal], [data-motion-reveal], [data-image-reveal]")) : [];
        const index = siblings.indexOf(item);
        if (index > 0 && !item.style.getPropertyValue("--reveal-delay")) item.style.setProperty("--reveal-delay", `${Math.min(index, 6) * 70}ms`);
      });
      const revealObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        });
      }, { threshold: 0.12, rootMargin: "0px 0px -36px 0px" });
      revealItems.forEach((item) => revealObserver.observe(item));
    }
    if (counters.length) {
      const counterObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          animateCounter(entry.target);
          observer.unobserve(entry.target);
        });
      }, { threshold: 0.65 });
      counters.forEach((counter) => counterObserver.observe(counter));
    }

    if (parallaxItems.length) {
      let parallaxFrame = 0;
      const syncParallax = () => {
        if (parallaxFrame || reduceMotion.matches) return;
        parallaxFrame = requestAnimationFrame(() => {
          parallaxFrame = 0;
          parallaxItems.forEach((element) => {
            const bounds = element.getBoundingClientRect();
            if (bounds.bottom < 0 || bounds.top > window.innerHeight) return;
            const intensity = Number(element.dataset.parallax) || 0;
            const offset = Math.max(-14, Math.min(14, (bounds.top + bounds.height / 2 - window.innerHeight / 2) * intensity));
            element.style.setProperty("--parallax-offset", `${offset.toFixed(1)}px`);
          });
        });
      };
      window.addEventListener("scroll", syncParallax, { passive: true });
      window.addEventListener("resize", syncParallax, { passive: true });
      syncParallax();
    }
  }

  reduceMotion.addEventListener?.("change", (event) => {
    if (event.matches) {
      document.documentElement.classList.remove("motion-system-ready");
      motionPage?.classList.remove("motion-ready");
      revealImmediately();
      counters.forEach(animateCounter);
      parallaxItems.forEach((element) => element.style.removeProperty("--parallax-offset"));
    }
  });

  if (window.gsap?.matchMedia) {
    const shapeMotion = window.gsap.matchMedia();
    shapeMotion.add("(prefers-reduced-motion: no-preference)", () => {
      const movingShapes = Array.from(document.querySelectorAll("[data-gsap-motion]"));
      movingShapes.forEach((shape) => {
        const motion = shape.dataset.gsapMotion;
        if (motion === "rotate") {
          window.gsap.to(shape, { rotation: "+=360", duration: 84, ease: "none", repeat: -1, transformOrigin: "50% 50%", force3D: true });
        } else if (motion === "orbit") {
          window.gsap.to(shape, { rotation: "-=360", duration: 112, ease: "none", repeat: -1, transformOrigin: "50% 50%", force3D: true });
        } else if (motion === "float") {
          window.gsap.to(shape, { y: -7, duration: 4.8, ease: "sine.inOut", repeat: -1, yoyo: true, force3D: true });
        } else if (motion === "breathe") {
          window.gsap.to(shape, { scale: 1.045, duration: 5.2, ease: "sine.inOut", repeat: -1, yoyo: true, transformOrigin: "50% 50%", force3D: true });
        }
      });
      return () => window.gsap.killTweensOf(movingShapes);
    });
  }
})();
