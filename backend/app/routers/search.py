from fastapi import APIRouter, Query
from app.services.smart_search import unified_place_search, get_cached_search

router = APIRouter(prefix="/api/search", tags=["Global Place Search"])


@router.get("/places")
async def search_places(
    q: str = Query(..., min_length=3, description="Search query string"),
    lat: float = Query(None, description="Proximity latitude"),
    lon: float = Query(None, description="Proximity longitude"),
    limit: int = Query(10, ge=1, le=20)
):
    query_str = q.strip()
    if len(query_str) < 3:
        return {"results": [], "cached": False}

    cache_key = f"{query_str.lower()}:{round(lat, 2) if lat is not None else 0}:{round(lon, 2) if lon is not None else 0}"
    cached = get_cached_search(cache_key)
    if cached is not None:
        return {"results": cached, "cached": True}

    results = await unified_place_search(query_str, lat, lon, limit=limit)
    return {"results": results, "cached": False}
