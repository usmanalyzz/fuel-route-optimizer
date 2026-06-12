"""
Geocoding service — converts addresses and city/state pairs to lat/lon.

Uses Nominatim (OpenStreetMap) for geocoding with in-memory LRU cache
and persistent GeocodeCache database table for import-time lookups.
"""
import time
from functools import lru_cache
from typing import NamedTuple

import requests
from django.conf import settings

from routing.models import GeocodeCache


class Coordinates(NamedTuple):
    """Immutable latitude/longitude pair."""

    lat: float
    lon: float


class GeocodingError(Exception):
    """Base exception for geocoding failures."""


class LocationNotFoundError(GeocodingError):
    """Raised when Nominatim returns no results for a query."""


class LocationOutsideUSAError(GeocodingError):
    """Raised when coordinates fall outside the USA bounding box."""


def is_within_usa(lat: float, lon: float) -> bool:
    """
    Check if coordinates fall within the USA bounding box.

    Uses a rectangular approximation that includes continental US,
    Alaska, Hawaii, and DC.
    """
    return (
        settings.USA_LAT_MIN <= lat <= settings.USA_LAT_MAX
        and settings.USA_LON_MIN <= lon <= settings.USA_LON_MAX
    )


def _nominatim_request(params: dict) -> list:
    """
    Make a raw HTTP request to the Nominatim search API.

    Args:
        params: Query parameters (q, format, limit, countrycodes, etc.)

    Returns:
        List of result dicts from Nominatim JSON response.
    """
    headers = {"User-Agent": "fuel-route-optimizer/1.0 (spotter-assessment)"}
    response = requests.get(
        f"{settings.NOMINATIM_BASE_URL}/search",
        params=params,
        headers=headers,
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


@lru_cache(maxsize=512)
def _geocode_address_cached(query: str) -> Coordinates:
    """
    Geocode a text query via Nominatim with in-memory caching.

    Cached so repeated demo requests for the same city don't hit Nominatim again.

    Args:
        query: Free-text location, e.g. "Chicago, IL" or "Tomah, WI, USA"

    Returns:
        Coordinates for the first matching result.

    Raises:
        LocationNotFoundError: No results from Nominatim.
        LocationOutsideUSAError: Result is outside USA bounding box.
    """
    results = _nominatim_request(
        {"q": query, "format": "json", "limit": 1, "countrycodes": "us"}
    )
    if not results:
        raise LocationNotFoundError(f"Could not geocode: {query}")

    lat = float(results[0]["lat"])
    lon = float(results[0]["lon"])

    if not is_within_usa(lat, lon):
        raise LocationOutsideUSAError(f"Location outside USA: {query}")

    return Coordinates(lat=lat, lon=lon)


def geocode_address(address: str) -> Coordinates:
    """
    Geocode a user-provided address string (used at API request time).

    Args:
        address: e.g. "Chicago, IL" or "Los Angeles, CA"

    Returns:
        Coordinates for the geocoded location.
    """
    return _geocode_address_cached(address.strip())


def geocode_city_state(city: str, state: str, rate_limit: bool = False) -> Coordinates:
    """
    Geocode a city/state pair (used during fuel station CSV import).

    Checks GeocodeCache DB first, then Nominatim if not cached.
    All stations in the same city share these coordinates.

    Args:
        city: City name from CSV, e.g. "Tomah"
        state: Two-letter state code, e.g. "WI"
        rate_limit: If True, sleep 1.1s before Nominatim call (respects 1 req/sec limit)

    Returns:
        Coordinates for the city center.
    """
    city = city.strip()
    state = state.strip().upper()

    # Check persistent DB cache first
    cached = GeocodeCache.objects.filter(city__iexact=city, state=state).first()
    if cached:
        return Coordinates(lat=cached.latitude, lon=cached.longitude)

    # Respect Nominatim usage policy: max 1 request per second during bulk import
    if rate_limit:
        time.sleep(1.1)

    query = f"{city}, {state}, USA"
    coords = _geocode_address_cached(query)

    # Save to DB cache for future imports
    GeocodeCache.objects.update_or_create(
        city=city,
        state=state,
        defaults={"latitude": coords.lat, "longitude": coords.lon},
    )
    return coords
