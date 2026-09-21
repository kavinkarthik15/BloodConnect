import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.config import settings


def resolve_coordinates(address: str, city: str) -> tuple[float, float] | None:
    if settings.geocoding_provider.lower() != "nominatim":
        return None

    query = urlencode({"q": f"{address}, {city}", "format": "jsonv2", "limit": 1})
    request = Request(
        f"https://nominatim.openstreetmap.org/search?{query}",
        headers={"User-Agent": settings.geocoding_user_agent},
    )
    try:
        with urlopen(request, timeout=settings.geocoding_timeout_seconds) as response:
            results = json.load(response)
    except Exception:
        return None

    if not results:
        return None
    try:
        return float(results[0]["lat"]), float(results[0]["lon"])
    except (KeyError, TypeError, ValueError):
        return None