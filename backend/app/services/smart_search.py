"""
AI Smart Search Service — RoadBuddy
-------------------------------------
Takes a natural language query and extracts
smart filters to search community routes.

Examples:
  "beach trip under 5000"
  "family trip to hill station 3 days"
  "weekend trip from Jaipur under 10000"
  "solo trip to Rajasthan heritage"
"""

import json
import asyncio
import httpx
from app.core.config import settings

GROQ_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
GROQ_MODEL = "gemini-1.5-flash"


# ── Prompt Builder ────────────────────────────────────────────────────────────

def build_search_prompt(query: str) -> str:
    return f"""You are RoadBuddy AI, an Indian travel search engine.
A user typed this search query: "{query}"

Extract travel filters from this query and return ONLY valid JSON, no markdown:
{{
  "understood_query": "What you understood from the query in 1 sentence.",
  "destination": "Specific destination if mentioned, else null",
  "destination_type": "One of: beach, hill_station, heritage, desert, forest, city, religious, adventure, or null",
  "origin": "Origin city if mentioned, else null",
  "max_budget_inr": 0,
  "duration_days": 0,
  "group_type": "One of: family, couple, friends, solo, or null",
  "season": "One of: summer, monsoon, winter, or null",
  "keywords": ["list", "of", "important", "keywords", "from", "query"],
  "suggested_destinations": ["3 real Indian destinations that match this query"],
  "search_tips": "One helpful tip for this type of trip in India."
}}

Rules:
- max_budget_inr: extract number from query. If not mentioned use 0
- duration_days: extract number of days. If "weekend" use 2. If not mentioned use 0
- destination_type: guess from context (e.g. "hill station" → hill_station, "beach" → beach)
- suggested_destinations: always suggest 3 real Indian places that match
- Be smart — "under 5k" means max_budget_inr: 5000
- "family" or "kids" means group_type: family
- "couple" or "honeymoon" means group_type: couple
- "solo" means group_type: solo
"""


# ── Call Groq API ─────────────────────────────────────────────────────────────

from app.services.groq_client import call_groq as call_groq_search


# ── Mock Response ─────────────────────────────────────────────────────────────

def mock_search(query: str) -> dict:
    query_lower = query.lower()

    if "beach" in query_lower or "goa" in query_lower:
        return {
            "understood_query": "Looking for a beach trip in India.",
            "destination": "Goa",
            "destination_type": "beach",
            "origin": None,
            "max_budget_inr": 10000,
            "duration_days": 3,
            "group_type": None,
            "season": "winter",
            "keywords": ["beach", "sea", "sand", "coastal"],
            "suggested_destinations": ["Goa", "Kovalam Kerala", "Puri Odisha"],
            "search_tips": "Best beach trips in India are from November to February.",
        }
    elif "hill" in query_lower or "mountain" in query_lower or "manali" in query_lower:
        return {
            "understood_query": "Looking for a hill station trip.",
            "destination": None,
            "destination_type": "hill_station",
            "origin": None,
            "max_budget_inr": 15000,
            "duration_days": 4,
            "group_type": None,
            "season": "summer",
            "keywords": ["hills", "mountains", "cool", "scenic"],
            "suggested_destinations": ["Manali Himachal Pradesh", "Ooty Tamil Nadu", "Munnar Kerala"],
            "search_tips": "Hill stations are best visited in summer (April-June) to escape the heat.",
        }
    elif "heritage" in query_lower or "rajasthan" in query_lower or "fort" in query_lower:
        return {
            "understood_query": "Looking for a heritage or cultural trip.",
            "destination": "Rajasthan",
            "destination_type": "heritage",
            "origin": None,
            "max_budget_inr": 12000,
            "duration_days": 5,
            "group_type": None,
            "season": "winter",
            "keywords": ["heritage", "fort", "palace", "culture", "history"],
            "suggested_destinations": ["Jaipur Rajasthan", "Udaipur Rajasthan", "Jodhpur Rajasthan"],
            "search_tips": "October to March is the best time for Rajasthan heritage trips.",
        }
    elif "family" in query_lower or "kids" in query_lower:
        return {
            "understood_query": "Looking for a family-friendly trip.",
            "destination": None,
            "destination_type": None,
            "origin": None,
            "max_budget_inr": 20000,
            "duration_days": 3,
            "group_type": "family",
            "season": None,
            "keywords": ["family", "kids", "children", "safe"],
            "suggested_destinations": ["Shimla Himachal Pradesh", "Mysore Karnataka", "Coorg Karnataka"],
            "search_tips": "For family trips, choose destinations with good road connectivity and clean hotels.",
        }
    else:
        return {
            "understood_query": f"Looking for a trip matching: {query}",
            "destination": None,
            "destination_type": None,
            "origin": None,
            "max_budget_inr": 10000,
            "duration_days": 3,
            "group_type": None,
            "season": None,
            "keywords": query.lower().split(),
            "suggested_destinations": ["Jaipur Rajasthan", "Manali Himachal Pradesh", "Goa"],
            "search_tips": "Try being more specific — mention destination, budget, or number of days.",
        }


# ── Main Function ─────────────────────────────────────────────────────────────

async def smart_search(query: str) -> dict:
    """
    Main function called from the router.
    Takes natural language query and returns extracted filters + suggestions.
    """
    try:
        if settings.gemini_api_key:
            prompt = build_search_prompt(query)
            filters = await call_groq_search(prompt)
        else:
            filters = mock_search(query)

        return {
            "query": query,
            "filters": filters,
            "message": f"Found filters for: {filters.get('understood_query', query)}",
        }

    except Exception as e:
        raise RuntimeError(f"Smart search failed: {e}")


# ── Global Place Search Engine (Mapbox -> Nominatim -> Overpass Fallback) ──────

import time
import urllib.parse

NOMINATIM_HEADERS = {"User-Agent": "RoadBuddy/1.0 (contact: kunalsinghtanwar355@gmail.com)"}

_last_nominatim_call = 0.0
_nominatim_lock = asyncio.Lock()

_search_cache: dict[str, tuple[float, list]] = {}
CACHE_TTL_SECONDS = 86400  # 24 hours


def get_cached_search(key: str):
    entry = _search_cache.get(key)
    if entry and (time.time() - entry[0]) < CACHE_TTL_SECONDS:
        return entry[1]
    return None


def set_cached_search(key: str, value: list):
    _search_cache[key] = (time.time(), value)


async def throttled_nominatim_call(func, *args, **kwargs):
    global _last_nominatim_call
    async with _nominatim_lock:
        elapsed = time.time() - _last_nominatim_call
        if elapsed < 1.1:
            await asyncio.sleep(1.1 - elapsed)
        _last_nominatim_call = time.time()
        return await func(*args, **kwargs)


async def search_mapbox_searchbox(query: str, lat: float = None, lon: float = None) -> list:
    mapbox_token = settings.mapbox_access_token.strip()
    if not mapbox_token:
        return []

    encoded_q = urllib.parse.quote(query)
    # Strictly limit Mapbox geocoding to India (country=IN)
    url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{encoded_q}.json?country=IN&limit=7&access_token={mapbox_token}"
    if lat is not None and lon is not None:
        url += f"&proximity={lon},{lat}"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(url)
            if res.status_code == 200:
                data = res.json()
                results = []
                for feat in data.get("features", []):
                    center = feat.get("center", [0, 0])
                    place_name = feat.get("place_name", "")
                    
                    # Verify India locality
                    if "india" in place_name.lower():
                        results.append({
                            "name": feat.get("text") or place_name.split(",")[0],
                            "lat": center[1],
                            "lon": center[0],
                            "address": place_name,
                            "category": feat.get("properties", {}).get("category", feat.get("place_type", ["place"])[0]),
                            "place_id": feat.get("id", ""),
                            "source": "mapbox"
                        })
                return results
    except Exception as e:
        print(f"Mapbox place search error: {e}")
    return []


async def search_nominatim(query: str, lat: float = None, lon: float = None) -> list:
    async def _call():
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Strictly limit Nominatim to India (countrycodes=in)
            params = {
                "q": query,
                "countrycodes": "in",
                "format": "jsonv2",
                "limit": 7,
                "addressdetails": 1
            }
            if lat is not None and lon is not None:
                params["viewbox"] = f"{lon-0.5},{lat+0.5},{lon+0.5},{lat-0.5}"
                params["bounded"] = 0
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params=params,
                headers=NOMINATIM_HEADERS
            )
            if resp.status_code == 200:
                results = []
                for item in resp.json():
                    display_name = item.get("display_name", "")
                    country_code = item.get("address", {}).get("country_code", "")
                    if country_code == "in" or "india" in display_name.lower():
                        short_name = item.get("name") or (display_name.split(",")[0] if display_name else query)
                        cat = item.get("type") or item.get("category") or "landmark"
                        results.append({
                            "name": short_name,
                            "lat": float(item.get("lat", 0)),
                            "lon": float(item.get("lon", 0)),
                            "address": display_name,
                            "category": cat.replace("_", " ").title(),
                            "place_id": str(item.get("place_id", "")),
                            "source": "nominatim"
                        })
                return results
            return []
    try:
        return await throttled_nominatim_call(_call)
    except Exception as e:
        print(f"Nominatim place search error: {e}")
        return []


async def search_overpass(query: str, lat: float = None, lon: float = None) -> list:
    if lat is None or lon is None:
        return []
    
    # Ensure coordinates are within India bounding box
    if not (6.0 <= lat <= 37.5 and 68.0 <= lon <= 97.5):
        return []

    overpass_url = "https://overpass-api.de/api/interpreter"
    query_clean = query.replace('"', '').strip()
    overpass_query = f"""
    [out:json][timeout:5];
    (
      node["name"~"{query_clean}",i](around:25000,{lat},{lon});
      way["name"~"{query_clean}",i](around:25000,{lat},{lon});
      node["shop"~"{query_clean}",i](around:25000,{lat},{lon});
      node["amenity"~"{query_clean}",i](around:25000,{lat},{lon});
    );
    out center 7;
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(overpass_url, data={"data": overpass_query})
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for elem in data.get("elements", []):
                    tags = elem.get("tags", {})
                    name = tags.get("name") or query
                    e_lat = elem.get("lat") or elem.get("center", {}).get("lat")
                    e_lon = elem.get("lon") or elem.get("center", {}).get("lon")
                    if e_lat and e_lon and (6.0 <= float(e_lat) <= 37.5 and 68.0 <= float(e_lon) <= 97.5):
                        cat = tags.get("shop") or tags.get("amenity") or tags.get("tourism") or "store"
                        results.append({
                            "name": name,
                            "lat": float(e_lat),
                            "lon": float(e_lon),
                            "address": f"{name}, {tags.get('addr:street', tags.get('addr:suburb', 'Local Area'))}, India",
                            "category": cat.replace("_", " ").title(),
                            "place_id": f"osm_{elem.get('id')}",
                            "source": "overpass"
                        })
                return results
    except Exception as e:
        print(f"Overpass search error: {e}")
    return []


async def unified_place_search(query: str, lat: float = None, lon: float = None, limit: int = 10) -> list:
    if not query or len(query.strip()) < 3:
        return []

    cache_key = f"{query.lower().strip()}:{round(lat, 2) if lat is not None else 0}:{round(lon, 2) if lon is not None else 0}"
    cached = get_cached_search(cache_key)
    if cached is not None:
        return cached

    # 1. Mapbox Search Box / Places API
    results = await search_mapbox_searchbox(query, lat, lon)
    if len(results) >= 3:
        set_cached_search(cache_key, results[:limit])
        return results[:limit]

    # 2. Nominatim OpenStreetMap Search
    nominatim_results = await search_nominatim(query, lat, lon)
    existing_names = {r["name"].lower() for r in results}
    for n_res in nominatim_results:
        if n_res["name"].lower() not in existing_names:
            results.append(n_res)
            existing_names.add(n_res["name"].lower())

    if len(results) >= 3:
        set_cached_search(cache_key, results[:limit])
        return results[:limit]

    # 3. Overpass API Fallback
    overpass_results = await search_overpass(query, lat, lon)
    for o_res in overpass_results:
        if o_res["name"].lower() not in existing_names:
            results.append(o_res)
            existing_names.add(o_res["name"].lower())

    set_cached_search(cache_key, results[:limit])
    return results[:limit]