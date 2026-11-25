"""Bangladesh administrative location hierarchy and geocoding proxy service."""

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from django.conf import settings

BDAPIS_BASE_URL = "https://bdapis.com/api/v1.2"
NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
PHOTON_SEARCH_URL = "https://photon.komoot.io/api/"
USER_AGENT = "PaperLoop-App/1.0 (https://paperloop.local)"

HIERARCHY_CACHE_TTL = 6 * 60 * 60  # 6 hours
SEARCH_CACHE_TTL = 15 * 60         # 15 minutes

_CACHE = {}
_CACHE_LOCK = threading.Lock()
_LOCAL_DATA_CACHE = None


def _get_cached(key):
    now = time.monotonic()
    with _CACHE_LOCK:
        entry = _CACHE.get(key)
        if entry and entry[0] > now:
            return entry[1]
        if entry:
            _CACHE.pop(key, None)
    return None


def _set_cached(key, value, ttl):
    expires_at = time.monotonic() + ttl
    with _CACHE_LOCK:
        if len(_CACHE) > 512:
            now = time.monotonic()
            expired = [k for k, (exp, _) in _CACHE.items() if exp <= now]
            for k in expired:
                _CACHE.pop(k, None)
        _CACHE[key] = (expires_at, value)


def _fetch_json(url, timeout=4.0):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status != 200:
            raise ValueError(f"Unexpected status {resp.status}")
        return json.loads(resp.read().decode("utf-8"))


def _load_local_bd_data():
    global _LOCAL_DATA_CACHE
    if _LOCAL_DATA_CACHE is not None:
        return _LOCAL_DATA_CACHE
    data_path = Path(settings.BASE_DIR) / "static" / "data" / "bd_locations.json"
    with data_path.open("r", encoding="utf-8") as fh:
        _LOCAL_DATA_CACHE = json.load(fh)
    return _LOCAL_DATA_CACHE


def _parse_coordinates(coord_str):
    if not coord_str or not isinstance(coord_str, str):
        return None, None
    parts = [p.strip() for p in coord_str.split(",")]
    if len(parts) != 2:
        return None, None
    try:
        return float(parts[0]), float(parts[1])
    except (TypeError, ValueError):
        return None, None


def get_divisions():
    """Return Bangladesh divisions from bdapis.com with local JSON fallback."""
    cache_key = "bd:divisions"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    local_data = _load_local_bd_data()
    local_coords = {
        d["name"].casefold(): (d.get("lat"), d.get("lon"), d.get("bn_name", ""))
        for d in local_data.get("divisions", [])
    }

    divisions = []
    source = "bdapis"
    try:
        payload = _fetch_json(f"{BDAPIS_BASE_URL}/divisions", timeout=4.0)
        for item in payload.get("data", []):
            name = (item.get("division") or "").strip()
            if not name:
                continue
            lat, lon = _parse_coordinates(item.get("coordinates"))
            fallback_lat, fallback_lon, fallback_bn = local_coords.get(name.casefold(), (None, None, ""))
            divisions.append({
                "name": name,
                "bn_name": item.get("divisionbn") or fallback_bn,
                "lat": lat if lat is not None else fallback_lat,
                "lon": lon if lon is not None else fallback_lon,
            })
    except (urllib.error.URLError, TimeoutError, ValueError, OSError, json.JSONDecodeError):
        divisions = []

    if not divisions:
        source = "local"
        divisions = [
            {
                "name": d["name"],
                "bn_name": d.get("bn_name", ""),
                "lat": d.get("lat"),
                "lon": d.get("lon"),
            }
            for d in local_data.get("divisions", [])
        ]

    result = {"divisions": divisions, "source": source}
    _set_cached(cache_key, result, HIERARCHY_CACHE_TTL)
    return result


def get_districts(division_name):
    """Return districts for a Bangladesh division from bdapis.com with local fallback."""
    clean_div = (division_name or "").strip()
    cache_key = f"bd:districts:{clean_div.casefold()}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    local_data = _load_local_bd_data()
    local_div = next(
        (d for d in local_data.get("divisions", []) if d["name"].casefold() == clean_div.casefold()),
        None,
    )
    local_dist_coords = {
        dist["name"].casefold(): (dist.get("lat"), dist.get("lon"))
        for dist in (local_div.get("districts", []) if local_div else [])
    }

    districts = []
    source = "bdapis"
    if clean_div:
        try:
            encoded = urllib.parse.quote(clean_div.lower())
            payload = _fetch_json(f"{BDAPIS_BASE_URL}/division/{encoded}", timeout=4.0)
            for item in payload.get("data", []):
                name = (item.get("district") or "").strip()
                if not name:
                    continue
                lat, lon = _parse_coordinates(item.get("coordinates"))
                fb_lat, fb_lon = local_dist_coords.get(name.casefold(), (None, None))
                districts.append({
                    "name": name,
                    "bn_name": item.get("districtbn") or "",
                    "lat": lat if lat is not None else fb_lat,
                    "lon": lon if lon is not None else fb_lon,
                })
        except (urllib.error.URLError, TimeoutError, ValueError, OSError, json.JSONDecodeError):
            districts = []

    if not districts and local_div:
        source = "local"
        districts = [
            {
                "name": dist["name"],
                "bn_name": dist.get("bn_name", ""),
                "lat": dist.get("lat"),
                "lon": dist.get("lon"),
            }
            for dist in local_div.get("districts", [])
        ]

    result = {"division": clean_div, "districts": districts, "source": source}
    _set_cached(cache_key, result, HIERARCHY_CACHE_TTL)
    return result


def get_upazilas(district_name):
    """Return upazilas/thanas for a Bangladesh district from bdapis.com with local fallback."""
    clean_dist = (district_name or "").strip()
    cache_key = f"bd:upazilas:{clean_dist.casefold()}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    local_data = _load_local_bd_data()
    local_dist = None
    for div in local_data.get("divisions", []):
        for dist in div.get("districts", []):
            if dist["name"].casefold() == clean_dist.casefold():
                local_dist = dist
                break
        if local_dist:
            break

    upazilas = []
    lat = local_dist.get("lat") if local_dist else None
    lon = local_dist.get("lon") if local_dist else None
    source = "bdapis"

    if clean_dist:
        try:
            encoded = urllib.parse.quote(clean_dist.lower())
            payload = _fetch_json(f"{BDAPIS_BASE_URL}/district/{encoded}", timeout=4.0)
            for item in payload.get("data", []):
                raw_list = item.get("upazilla") or item.get("upazilas") or []
                for u in raw_list:
                    u_clean = (u or "").strip()
                    if u_clean and u_clean not in upazilas:
                        upazilas.append(u_clean)
                item_lat, item_lon = _parse_coordinates(item.get("coordinates"))
                if item_lat is not None and item_lon is not None:
                    lat, lon = item_lat, item_lon
        except (urllib.error.URLError, TimeoutError, ValueError, OSError, json.JSONDecodeError):
            upazilas = []

    if local_dist:
        # Merge local urban thanas (e.g. Dhanmondi, Gulshan, Uttara) for major cities if missing
        local_upazilas = local_dist.get("upazilas", [])
        if not upazilas:
            source = "local"
            upazilas = list(local_upazilas)
        elif clean_dist.casefold() in {"dhaka", "chattogram", "rajshahi", "khulna", "sylhet", "barishal", "rangpur", "mymensingh"}:
            existing_cf = {u.casefold() for u in upazilas}
            for u in local_upazilas:
                if u.casefold() not in existing_cf:
                    upazilas.append(u)

    result = {
        "district": clean_dist,
        "lat": lat,
        "lon": lon,
        "upazilas": upazilas,
        "source": source,
    }
    _set_cached(cache_key, result, HIERARCHY_CACHE_TTL)
    return result


def _normalize_nominatim_item(item):
    addr = item.get("address") or {}
    road_parts = [
        item.get("name") or "",
        addr.get("house_number") or "",
        addr.get("road") or "",
        addr.get("neighbourhood") or addr.get("suburb") or "",
    ]
    street_parts = []
    for p in road_parts:
        p = p.strip()
        if p and p not in street_parts:
            street_parts.append(p)

    upazila = (
        addr.get("city_district")
        or addr.get("subdistrict")
        or addr.get("county")
        or addr.get("town")
        or ""
    )
    city = (
        addr.get("city")
        or addr.get("town")
        or addr.get("state_district")
        or addr.get("county")
        or ""
    )
    district = (addr.get("state_district") or city or "").replace(" District", "").strip()
    postcode = addr.get("postcode") or ""

    formatted_parts = []
    if street_parts:
        formatted_parts.append(", ".join(street_parts))
    if upazila and upazila.casefold() not in (street_parts[0].casefold() if street_parts else ""):
        formatted_parts.append(upazila)
    if postcode:
        formatted_parts.append(postcode)

    return {
        "display_name": item.get("display_name") or ", ".join(formatted_parts),
        "formatted_address": ", ".join(formatted_parts) or item.get("display_name", ""),
        "name": item.get("name") or (street_parts[0] if street_parts else ""),
        "upazila": upazila,
        "city": city or district,
        "district": district,
        "postcode": postcode,
        "country": "Bangladesh",
        "lat": float(item["lat"]),
        "lon": float(item["lon"]),
        "source": "nominatim",
    }


def _normalize_photon_feature(feature):
    props = feature.get("properties") or {}
    coords = (feature.get("geometry") or {}).get("coordinates") or []
    if len(coords) < 2:
        return None
    lon, lat = float(coords[0]), float(coords[1])

    name = (props.get("name") or "").strip()
    street = (props.get("street") or "").strip()
    housenumber = (props.get("housenumber") or "").strip()
    district = (props.get("district") or props.get("suburb") or "").strip()
    city = (props.get("city") or props.get("county") or props.get("state") or "").strip()
    postcode = (props.get("postcode") or "").strip()

    addr_parts = [p for p in [name, f"{housenumber} {street}".strip(), district, postcode] if p]
    seen = []
    for p in addr_parts:
        if p not in seen:
            seen.append(p)
    formatted_address = ", ".join(seen)
    display_parts = seen + ([city] if city and city not in seen else []) + ["Bangladesh"]

    return {
        "display_name": ", ".join(display_parts),
        "formatted_address": formatted_address or ", ".join(display_parts),
        "name": name or street or city,
        "upazila": district,
        "city": city or district,
        "district": city,
        "postcode": postcode,
        "country": "Bangladesh",
        "lat": lat,
        "lon": lon,
        "source": "photon",
    }


def search_locations(query):
    """Search Bangladesh streets, campuses, and landmarks via Nominatim + Photon fallback."""
    clean_q = (query or "").strip()
    if len(clean_q) < 2:
        return {"query": clean_q, "results": [], "source": "none"}

    cache_key = f"bd:search:{clean_q.casefold()}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    results = []
    source = "nominatim"

    # 1. Primary: OpenStreetMap Nominatim restricted to Bangladesh
    try:
        params = urllib.parse.urlencode({
            "q": clean_q,
            "countrycodes": "bd",
            "format": "json",
            "addressdetails": 1,
            "limit": 8,
        })
        payload = _fetch_json(f"{NOMINATIM_SEARCH_URL}?{params}", timeout=5.0)
        if isinstance(payload, list):
            for item in payload:
                if item.get("lat") and item.get("lon"):
                    results.append(_normalize_nominatim_item(item))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError, json.JSONDecodeError):
        results = []

    # 2. Fallback: Photon (Komoot) biased to Bangladesh
    if not results:
        source = "photon"
        try:
            params = urllib.parse.urlencode({
                "q": f"{clean_q}, Bangladesh",
                "limit": 8,
                "lat": "23.8103",
                "lon": "90.4125",
            })
            payload = _fetch_json(f"{PHOTON_SEARCH_URL}?{params}", timeout=5.0)
            for feature in payload.get("features", []):
                props = feature.get("properties") or {}
                country_code = (props.get("countrycode") or "").upper()
                country = (props.get("country") or "").casefold()
                if country_code and country_code != "BD" and country != "bangladesh":
                    continue
                normalized = _normalize_photon_feature(feature)
                if normalized:
                    results.append(normalized)
        except (urllib.error.URLError, TimeoutError, ValueError, OSError, json.JSONDecodeError):
            results = []

    # 3. Offline fallback: match local bundled districts & upazilas
    if not results:
        source = "local"
        q_cf = clean_q.casefold()
        tokens = [t for t in q_cf.replace(",", " ").split() if len(t) >= 2]
        local_data = _load_local_bd_data()

        def _matches_local(name):
            name_cf = name.casefold()
            return q_cf in name_cf or any(tok in name_cf for tok in tokens)

        for div in local_data.get("divisions", []):
            for dist in div.get("districts", []):
                if _matches_local(dist["name"]):
                    results.append({
                        "display_name": f"{dist['name']}, {div['name']} Division, Bangladesh",
                        "formatted_address": f"{dist['name']}, {div['name']} Division",
                        "name": dist["name"],
                        "upazila": "",
                        "city": dist["name"],
                        "district": dist["name"],
                        "postcode": "",
                        "country": "Bangladesh",
                        "lat": dist.get("lat"),
                        "lon": dist.get("lon"),
                        "source": "local",
                    })
                for upazila in dist.get("upazilas", []):
                    if _matches_local(upazila):
                        results.append({
                            "display_name": f"{upazila}, {dist['name']}, Bangladesh",
                            "formatted_address": f"{upazila}, {dist['name']}",
                            "name": upazila,
                            "upazila": upazila,
                            "city": dist["name"],
                            "district": dist["name"],
                            "postcode": "",
                            "country": "Bangladesh",
                            "lat": dist.get("lat"),
                            "lon": dist.get("lon"),
                            "source": "local",
                        })
                if len(results) >= 8:
                    break
            if len(results) >= 8:
                break

    payload = {"query": clean_q, "results": results[:8], "source": source}
    _set_cached(cache_key, payload, SEARCH_CACHE_TTL)
    return payload


def reverse_geocode(lat, lon):
    """Reverse geocode coordinates in Bangladesh via Nominatim with graceful fallback."""
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return None

    cache_key = f"bd:rev:{lat_f:.5f},{lon_f:.5f}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    result = None
    try:
        params = urllib.parse.urlencode({
            "lat": f"{lat_f:.6f}",
            "lon": f"{lon_f:.6f}",
            "format": "json",
            "addressdetails": 1,
        })
        item = _fetch_json(f"{NOMINATIM_REVERSE_URL}?{params}", timeout=4.0)
        if isinstance(item, dict) and item.get("lat") and item.get("lon"):
            result = _normalize_nominatim_item(item)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError, json.JSONDecodeError):
        result = None

    if result is None:
        result = {
            "display_name": f"Pinned Location ({lat_f:.6f}, {lon_f:.6f}), Bangladesh",
            "formatted_address": f"Pinned Location ({lat_f:.6f}, {lon_f:.6f})",
            "name": "Pinned Location",
            "upazila": "",
            "city": "Dhaka",
            "district": "Dhaka",
            "postcode": "",
            "country": "Bangladesh",
            "lat": lat_f,
            "lon": lon_f,
            "source": "fallback",
        }

    _set_cached(cache_key, result, SEARCH_CACHE_TTL)
    return result
