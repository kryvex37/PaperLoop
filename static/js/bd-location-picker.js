(() => {
  const BD_DEFAULT_CENTER = [23.8103, 90.4125];
  const BD_DEFAULT_ZOOM = 7;

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
  }

  function debounce(fn, delay) {
    let timer = null;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), delay);
    };
  }

  function initLocationPicker(root) {
    const mode = root.dataset.mode || "listing";
    const apiDivisions = root.dataset.apiDivisions;
    const apiDistrictsTpl = root.dataset.apiDistricts;
    const apiUpazilasTpl = root.dataset.apiUpazilas;
    const apiSearch = root.dataset.apiSearch;
    const apiReverse = root.dataset.apiReverse;

    const divSelect = root.querySelector("[data-bd-division]");
    const distSelect = root.querySelector("[data-bd-district]");
    const upazilaSelect = root.querySelector("[data-bd-upazila]");
    const addAreaBtn = root.querySelector("[data-bd-add-area]");
    const pillsContainer = root.querySelector("[data-bd-pills]");
    const searchInput = root.querySelector("[data-bd-search]");
    const resultsBox = root.querySelector("[data-bd-results]");
    const mapContainer = root.querySelector("[data-bd-map]");
    const coordReadout = root.querySelector("[data-bd-coord-readout]");
    const summaryBox = root.querySelector("[data-bd-summary]");
    const errorBanner = root.querySelector("[data-bd-error]");

    // Bound form inputs
    const serviceAreaInput = root.dataset.serviceAreaId
      ? document.getElementById(root.dataset.serviceAreaId)
      : null;
    const latInput = root.dataset.latId ? document.getElementById(root.dataset.latId) : null;
    const lonInput = root.dataset.lonId ? document.getElementById(root.dataset.lonId) : null;

    const addressInput = root.dataset.addressId ? document.getElementById(root.dataset.addressId) : null;
    const cityInput = root.dataset.cityId ? document.getElementById(root.dataset.cityId) : null;
    const countryInput = root.dataset.countryId ? document.getElementById(root.dataset.countryId) : null;

    if (mode === "listing" && countryInput && !countryInput.value.trim()) {
      countryInput.value = "Bangladesh";
    }

    function showError(msg) {
      if (!errorBanner) return;
      if (msg) {
        errorBanner.textContent = msg;
        errorBanner.classList.add("is-visible");
      } else {
        errorBanner.textContent = "";
        errorBanner.classList.remove("is-visible");
      }
    }

    // --- Listing Mode: Selected Location Summary Card ---
    let summaryState = {
      address: addressInput ? addressInput.value.trim() : "",
      upazila: "",
      district: cityInput ? cityInput.value.trim() : "",
      country: (countryInput && countryInput.value.trim()) || "Bangladesh",
    };

    function renderListingSummary() {
      if (mode !== "listing" || !summaryBox) return;
      const hasLocation = Boolean(summaryState.address && summaryState.district);
      if (divSelect) {
        divSelect.required = !hasLocation;
      }
      if (!hasLocation) {
        summaryBox.classList.add("is-empty");
        summaryBox.innerHTML = `
          <div class="bd-location-summary-title">Selected Location Summary *</div>
          <div class="bd-loc-hint">No location selected yet. Search above, pick Division → District → Upazila, or click the map pin.</div>
        `;
        return;
      }
      summaryBox.classList.remove("is-empty");
      const pills = [
        summaryState.address ? `<span class="bd-loc-pill">${escapeHtml(summaryState.address)}</span>` : "",
        summaryState.upazila ? `<span class="bd-loc-pill">Upazila: ${escapeHtml(summaryState.upazila)}</span>` : "",
        summaryState.district ? `<span class="bd-loc-pill">District / City: ${escapeHtml(summaryState.district)}</span>` : "",
        `<span class="bd-loc-pill">${escapeHtml(summaryState.country || "Bangladesh")}</span>`,
      ].filter(Boolean).join("");
      summaryBox.innerHTML = `
        <div class="bd-location-summary-title">Selected Location Summary</div>
        <div class="bd-location-summary-pills">${pills}</div>
      `;
    }

    if (mode === "listing") {
      renderListingSummary();
    }

    // --- Map initialization (Keyless OpenStreetMap Tiles) ---
    let map = null;
    let marker = null;

    function createPinIcon() {
      return window.L.divIcon({
        className: "bd-emerald-pin",
        html: '<div class="bd-emerald-pin-dot"></div>',
        iconSize: [18, 18],
        iconAnchor: [9, 9],
      });
    }

    function updateCoordinateDisplay(lat, lon) {
      const latFixed = Number(lat).toFixed(6);
      const lonFixed = Number(lon).toFixed(6);
      if (latInput) latInput.value = latFixed;
      if (lonInput) lonInput.value = lonFixed;
      if (coordReadout) {
        coordReadout.textContent = `${latFixed}, ${lonFixed}`;
      }
      showError("");
    }

    async function reverseGeocodePin(lat, lon) {
      if (mode !== "listing" || !apiReverse) return;
      try {
        const url = `${apiReverse}?lat=${encodeURIComponent(lat.toFixed(6))}&lon=${encodeURIComponent(lon.toFixed(6))}`;
        const data = await fetchJson(url);
        if (data && data.formatted_address) {
          const fallbackDist = (distSelect && distSelect.value) || data.city || data.district || "Dhaka";
          const fallbackUpa = (upazilaSelect && upazilaSelect.value) || data.upazila || "";
          const resolvedCity = data.city || data.district || fallbackDist;
          if (addressInput) addressInput.value = data.formatted_address;
          if (cityInput) cityInput.value = resolvedCity;
          if (countryInput) countryInput.value = data.country || "Bangladesh";
          summaryState = {
            address: data.formatted_address,
            upazila: fallbackUpa,
            district: resolvedCity,
            country: data.country || "Bangladesh",
          };
          renderListingSummary();
          showError("");
        }
      } catch (err) {
        // Offline fallback using dropdowns or coordinates
        const fallbackDist = (distSelect && distSelect.value) || (cityInput && cityInput.value) || "Dhaka";
        const fallbackUpa = (upazilaSelect && upazilaSelect.value) || "";
        const fallbackAddr = fallbackUpa
          ? `${fallbackUpa}, ${fallbackDist} (${lat.toFixed(5)}, ${lon.toFixed(5)})`
          : `Pinned Location (${lat.toFixed(5)}, ${lon.toFixed(5)})`;
        if (addressInput) addressInput.value = fallbackAddr;
        if (cityInput) cityInput.value = fallbackDist;
        if (countryInput) countryInput.value = "Bangladesh";
        summaryState = {
          address: fallbackAddr,
          upazila: fallbackUpa,
          district: fallbackDist,
          country: "Bangladesh",
        };
        renderListingSummary();
      }
    }

    function setMapPin(lat, lon, zoom = 15, triggerReverse = false) {
      if (!map || !Number.isFinite(lat) || !Number.isFinite(lon)) return;
      if (!marker) {
        marker = window.L.marker([lat, lon], {
          draggable: true,
          icon: createPinIcon(),
        }).addTo(map);
        marker.on("dragend", () => {
          const pos = marker.getLatLng();
          updateCoordinateDisplay(pos.lat, pos.lng);
          if (mode === "listing") {
            reverseGeocodePin(pos.lat, pos.lng);
          }
        });
      } else {
        marker.setLatLng([lat, lon]);
      }
      map.setView([lat, lon], zoom);
      updateCoordinateDisplay(lat, lon);
      if (triggerReverse && mode === "listing") {
        reverseGeocodePin(lat, lon);
      }
    }

    if (mapContainer && window.L) {
      const initialLat = latInput && latInput.value ? parseFloat(latInput.value) : NaN;
      const initialLon = lonInput && lonInput.value ? parseFloat(lonInput.value) : NaN;
      const hasInitialCoords = Number.isFinite(initialLat) && Number.isFinite(initialLon);

      map = window.L.map(mapContainer, {
        center: hasInitialCoords ? [initialLat, initialLon] : BD_DEFAULT_CENTER,
        zoom: hasInitialCoords ? 14 : BD_DEFAULT_ZOOM,
        scrollWheelZoom: false,
      });

      window.L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap contributors",
      }).addTo(map);

      if (hasInitialCoords) {
        setMapPin(initialLat, initialLon, 14, false);
      }

      map.on("click", (ev) => {
        const { lat, lng } = ev.latlng;
        setMapPin(lat, lng, Math.max(map.getZoom(), 14), true);
      });

      const syncFromInputs = () => {
        if (!latInput || !lonInput) return;
        const lat = parseFloat(latInput.value);
        const lon = parseFloat(lonInput.value);
        if (Number.isFinite(lat) && Number.isFinite(lon) && lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180) {
          setMapPin(lat, lon, Math.max(map.getZoom(), 13), false);
        }
      };
      if (latInput) latInput.addEventListener("change", syncFromInputs);
      if (lonInput) lonInput.addEventListener("change", syncFromInputs);
    }

    // --- Partner Mode: Service Area Pills ---
    let selectedAreas = [];

    function parseInitialAreas() {
      if (!serviceAreaInput || !serviceAreaInput.value) return [];
      const raw = serviceAreaInput.value
        .split(/[\n;]+/)
        .map((chunk) => chunk.trim())
        .filter(Boolean);
      if (raw.length === 1 && raw[0].includes(",")) {
        const parts = raw[0].split(",").map((p) => p.trim()).filter(Boolean);
        if (parts.length <= 2) {
          return [parts.join(", ")];
        }
        return parts;
      }
      return raw;
    }

    function syncServiceAreaField() {
      if (serviceAreaInput) {
        serviceAreaInput.value = selectedAreas.join("; ");
      }
    }

    function renderPills() {
      if (!pillsContainer) return;
      pillsContainer.innerHTML = "";
      if (selectedAreas.length === 0) {
        const empty = document.createElement("span");
        empty.className = "bd-loc-pills-empty";
        empty.textContent = "No operational areas added yet. Select a division, district, and upazila above.";
        pillsContainer.appendChild(empty);
        return;
      }
      selectedAreas.forEach((area, idx) => {
        const pill = document.createElement("span");
        pill.className = "bd-loc-pill";
        pill.innerHTML = `<span>${escapeHtml(area)}</span>`;
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "bd-loc-pill-remove";
        btn.setAttribute("aria-label", `Remove ${area}`);
        btn.textContent = "×";
        btn.addEventListener("click", () => {
          selectedAreas.splice(idx, 1);
          syncServiceAreaField();
          renderPills();
        });
        pill.appendChild(btn);
        pillsContainer.appendChild(pill);
      });
    }

    if (mode === "partner" && pillsContainer) {
      selectedAreas = parseInitialAreas();
      renderPills();
    }

    function updateAddButtonState() {
      if (!addAreaBtn) return;
      addAreaBtn.disabled = !(distSelect && distSelect.value);
    }

    if (addAreaBtn) {
      addAreaBtn.addEventListener("click", () => {
        const dist = distSelect ? distSelect.value.trim() : "";
        const upazila = upazilaSelect ? upazilaSelect.value.trim() : "";
        if (!dist) return;
        const label = upazila ? `${upazila}, ${dist}` : dist;
        if (!selectedAreas.some((a) => a.toLowerCase() === label.toLowerCase())) {
          selectedAreas.push(label);
          syncServiceAreaField();
          renderPills();
          showError("");
        }
      });
    }

    // --- Cascading Division -> District -> Upazila ---
    async function fetchJson(url) {
      const resp = await fetch(url, { headers: { Accept: "application/json" } });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return resp.json();
    }

    async function loadDivisions() {
      if (!divSelect || !apiDivisions) return;
      try {
        const data = await fetchJson(apiDivisions);
        const divisions = data.divisions || [];
        divSelect.innerHTML = '<option value="">Select Division</option>';
        divisions.forEach((d) => {
          const opt = document.createElement("option");
          opt.value = d.name;
          opt.textContent = d.name;
          if (d.lat != null && d.lon != null) {
            opt.dataset.lat = d.lat;
            opt.dataset.lon = d.lon;
          }
          divSelect.appendChild(opt);
        });
      } catch (err) {
        console.warn("Failed to load divisions:", err);
      }
    }

    async function loadDistricts(division) {
      if (!distSelect) return;
      distSelect.innerHTML = '<option value="">Select District</option>';
      distSelect.disabled = true;
      if (upazilaSelect) {
        upazilaSelect.innerHTML = '<option value="">Select Upazila / Thana</option>';
        upazilaSelect.disabled = true;
      }
      updateAddButtonState();
      if (!division || !apiDistrictsTpl) return;

      try {
        const url = apiDistrictsTpl.replace("__DIV__", encodeURIComponent(division));
        const data = await fetchJson(url);
        const districts = data.districts || [];
        districts.forEach((d) => {
          const opt = document.createElement("option");
          opt.value = d.name;
          opt.textContent = d.name;
          if (d.lat != null && d.lon != null) {
            opt.dataset.lat = d.lat;
            opt.dataset.lon = d.lon;
          }
          distSelect.appendChild(opt);
        });
        distSelect.disabled = districts.length === 0;
      } catch (err) {
        console.warn("Failed to load districts:", err);
      }
    }

    async function loadUpazilas(district) {
      if (!upazilaSelect) return;
      upazilaSelect.innerHTML = '<option value="">Select Upazila / Thana</option>';
      upazilaSelect.disabled = true;
      if (!district || !apiUpazilasTpl) return;

      try {
        const url = apiUpazilasTpl.replace("__DIST__", encodeURIComponent(district));
        const data = await fetchJson(url);
        const upazilas = data.upazilas || [];
        upazilas.forEach((u) => {
          const opt = document.createElement("option");
          opt.value = u;
          opt.textContent = u;
          upazilaSelect.appendChild(opt);
        });
        upazilaSelect.disabled = upazilas.length === 0;
        if (map && data.lat != null && data.lon != null) {
          map.setView([Number(data.lat), Number(data.lon)], 11);
        }
      } catch (err) {
        console.warn("Failed to load upazilas:", err);
      }
    }

    if (divSelect) {
      loadDivisions();
      divSelect.addEventListener("change", () => {
        const selectedOpt = divSelect.options[divSelect.selectedIndex];
        if (map && selectedOpt && selectedOpt.dataset.lat && selectedOpt.dataset.lon) {
          map.setView([parseFloat(selectedOpt.dataset.lat), parseFloat(selectedOpt.dataset.lon)], 9);
        }
        loadDistricts(divSelect.value);
      });
    }

    if (distSelect) {
      distSelect.addEventListener("change", () => {
        const selectedOpt = distSelect.options[distSelect.selectedIndex];
        if (map && selectedOpt && selectedOpt.dataset.lat && selectedOpt.dataset.lon) {
          map.setView([parseFloat(selectedOpt.dataset.lat), parseFloat(selectedOpt.dataset.lon)], 11);
        }
        if (mode === "listing" && distSelect.value) {
          const divName = divSelect ? divSelect.value : "";
          const addr = divName ? `${distSelect.value}, ${divName} Division` : distSelect.value;
          if (addressInput) addressInput.value = addr;
          if (cityInput) cityInput.value = distSelect.value;
          if (countryInput) countryInput.value = "Bangladesh";
          summaryState = {
            address: addr,
            upazila: "",
            district: distSelect.value,
            country: "Bangladesh",
          };
          renderListingSummary();
          showError("");
        }
        updateAddButtonState();
        loadUpazilas(distSelect.value);
      });
    }

    if (upazilaSelect) {
      upazilaSelect.addEventListener("change", () => {
        if (mode === "listing" && upazilaSelect.value) {
          const dist = distSelect ? distSelect.value : "";
          const divName = divSelect ? divSelect.value : "";
          const addr = dist
            ? `${upazilaSelect.value}, ${dist}${divName ? `, ${divName} Division` : ""}`
            : upazilaSelect.value;
          if (addressInput) addressInput.value = addr;
          if (cityInput && dist) cityInput.value = dist;
          if (countryInput) countryInput.value = "Bangladesh";
          summaryState = {
            address: addr,
            upazila: upazilaSelect.value,
            district: dist,
            country: "Bangladesh",
          };
          renderListingSummary();
          showError("");
        }
      });
    }

    // --- Autocomplete Search (Nominatim / Photon Proxy) ---
    function closeResults() {
      if (resultsBox) {
        resultsBox.classList.remove("is-open");
        resultsBox.innerHTML = "";
      }
    }

    function applySearchResult(item) {
      if (searchInput) {
        searchInput.value = item.name || item.formatted_address || item.display_name;
      }
      if (Number.isFinite(item.lat) && Number.isFinite(item.lon)) {
        setMapPin(item.lat, item.lon, 16, false);
      }
      if (mode === "listing") {
        const resolvedAddress = item.formatted_address || item.display_name || "";
        const resolvedCity = item.city || item.district || item.upazila || "";
        const resolvedCountry = item.country || "Bangladesh";
        if (addressInput) addressInput.value = resolvedAddress;
        if (cityInput) cityInput.value = resolvedCity;
        if (countryInput) countryInput.value = resolvedCountry;
        summaryState = {
          address: resolvedAddress,
          upazila: item.upazila || "",
          district: resolvedCity,
          country: resolvedCountry,
        };
        renderListingSummary();
        showError("");
      }
      closeResults();
    }

    const performSearch = debounce(async (query) => {
      if (!resultsBox || !apiSearch) return;
      const q = query.trim();
      if (q.length < 2) {
        closeResults();
        return;
      }
      resultsBox.innerHTML = '<div class="bd-autocomplete-status">Searching Bangladesh locations…</div>';
      resultsBox.classList.add("is-open");

      try {
        const data = await fetchJson(`${apiSearch}?q=${encodeURIComponent(q)}`);
        const items = data.results || [];
        resultsBox.innerHTML = "";
        if (items.length === 0) {
          resultsBox.innerHTML = '<div class="bd-autocomplete-status">No matching campus, road, or landmark found. Try clicking the map pin.</div>';
          return;
        }
        items.forEach((item) => {
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = "bd-autocomplete-item";
          const title = item.name || item.formatted_address || item.display_name;
          const sub = item.display_name || [item.upazila, item.city, item.postcode].filter(Boolean).join(", ");
          btn.innerHTML = `<span class="bd-autocomplete-title">${escapeHtml(title)}</span><span class="bd-autocomplete-sub">${escapeHtml(sub)}</span>`;
          btn.addEventListener("click", () => applySearchResult(item));
          resultsBox.appendChild(btn);
        });
      } catch (err) {
        resultsBox.innerHTML = '<div class="bd-autocomplete-status">Search unavailable right now. Use the map pin or dropdowns.</div>';
      }
    }, 320);

    if (searchInput && resultsBox) {
      searchInput.addEventListener("input", (e) => performSearch(e.target.value));
      searchInput.addEventListener("keydown", (e) => {
        if (e.key === "Escape") closeResults();
      });
      document.addEventListener("click", (e) => {
        if (!root.contains(e.target)) closeResults();
      });
    }

    // --- Mandatory Location Validation on Form Submit ---
    const parentForm = root.closest("form");
    if (parentForm) {
      parentForm.addEventListener("submit", (e) => {
        if (mode === "listing") {
          const hasAddr = addressInput && addressInput.value.trim().length > 0;
          const hasCity = cityInput && cityInput.value.trim().length > 0;
          if (!hasAddr || !hasCity) {
            e.preventDefault();
            showError("Location is required. Please search for your campus/street, choose Division → District → Upazila, or click the map pin.");
            root.scrollIntoView({ behavior: "smooth", block: "center" });
            return;
          }
        } else if (mode === "partner") {
          syncServiceAreaField();
          const hasAreas = selectedAreas.length > 0;
          const latVal = latInput ? parseFloat(latInput.value) : NaN;
          const lonVal = lonInput ? parseFloat(lonInput.value) : NaN;
          const hasCoords = Number.isFinite(latVal) && Number.isFinite(lonVal);
          if (!hasAreas || !hasCoords) {
            e.preventDefault();
            const missing = [];
            if (!hasAreas) missing.push("add at least one operational service area");
            if (!hasCoords) missing.push("set your pickup hub Latitude & Longitude via search or map pin");
            showError(`Required: Please ${missing.join(" and ")}.`);
            root.scrollIntoView({ behavior: "smooth", block: "center" });
            return;
          }
        }
        showError("");
      });
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-bd-location-picker]").forEach(initLocationPicker);
  });
})();
