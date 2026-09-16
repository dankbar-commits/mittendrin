"""
app/clients/maps_client.py

Turns a free-text address into coordinates. Supports two providers,
switched via MAP_PROVIDER in .env:
  - "osm"    -> OpenStreetMap's Nominatim API, no key needed
  - "google" -> Google Geocoding API, needs MAPS_API_KEY

Nothing else in the app should call a map API directly — everything goes
through geocode_address(), so switching providers or adding a new one
later doesn't touch calling code.
"""

import httpx

from app.config import get_settings
from app.schemas import Location

# Module-level so tests can point these at a mock server without touching
# real config/settings.
NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org/search"
GOOGLE_GEOCODE_BASE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


class MapsError(Exception):
    """Raised when the map provider call fails or returns something unusable."""


async def geocode_address(address: str) -> Location | None:
    """
    Resolves a free-text address into a Location with coordinates.
    Returns None if the address couldn't be matched to anything (not an
    error — just no result), and raises MapsError on connection/API failures.
    """
    settings = get_settings()

    if settings.map_provider == "google":
        return await _geocode_google(address, settings.maps_api_key)
    return await _geocode_osm(address)


async def _geocode_osm(address: str) -> Location | None:
    params = {"q": address, "format": "json", "limit": 1}
    headers = {
        "User-Agent": "mittendrin-events-app"
    }  # required by Nominatim's usage policy

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                NOMINATIM_BASE_URL, params=params, headers=headers
            )
            response.raise_for_status()
            results = response.json()
    except httpx.HTTPStatusError as e:
        raise MapsError(
            f"Nominatim returned {e.response.status_code}: {e.response.text}"
        ) from e
    except httpx.RequestError as e:
        raise MapsError(f"Could not reach Nominatim: {e}") from e

    if not results:
        return None

    match = results[0]
    return Location(
        address=match.get("display_name", address),
        latitude=float(match["lat"]),
        longitude=float(match["lon"]),
    )


async def _geocode_google(address: str, api_key: str) -> Location | None:
    if not api_key:
        raise MapsError("MAP_PROVIDER is set to 'google' but MAPS_API_KEY is empty")

    params = {"address": address, "key": api_key}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(GOOGLE_GEOCODE_BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as e:
        raise MapsError(
            f"Google Geocoding returned {e.response.status_code}: {e.response.text}"
        ) from e
    except httpx.RequestError as e:
        raise MapsError(f"Could not reach Google Geocoding API: {e}") from e

    status = data.get("status")
    if status == "ZERO_RESULTS":
        return None
    if status != "OK":
        raise MapsError(
            f"Google Geocoding API returned status '{status}': {data.get('error_message', '')}"
        )

    result = data["results"][0]
    location = result["geometry"]["location"]
    return Location(
        address=result.get("formatted_address", address),
        latitude=location["lat"],
        longitude=location["lng"],
    )
