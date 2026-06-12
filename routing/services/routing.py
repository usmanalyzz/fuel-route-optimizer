"""
Routing service — fetches driving routes from OSRM.

Makes a single OSRM API call per request and returns route geometry,
distance, and duration as a RouteResult dataclass.
"""
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import requests
from django.conf import settings
from shapely.geometry import LineString

from routing.constants import METERS_PER_MILE
from routing.services.geocoding import Coordinates


class RoutingError(Exception):
    """Raised when OSRM cannot compute a route between the given points."""


@dataclass
class RouteResult:
    """
    Parsed driving route from OSRM.

    Attributes:
        line: Shapely LineString for geometric calculations
        coordinates: GeoJSON coordinate list [[lon, lat], ...]
        distance_miles: Total route distance in miles
        duration_minutes: Estimated driving time in minutes
    """

    line: LineString
    coordinates: list[list[float]]
    distance_miles: float
    duration_minutes: float


def _fetch_osrm_route(start: Coordinates, end: Coordinates) -> RouteResult:
    """
    Fetch route from OSRM using simplified geometry for faster response.

    Uses overview=simplified to reduce payload size and processing time.
    Distance/duration from OSRM remain accurate regardless of geometry detail.
    """
    url = (
        f"{settings.OSRM_BASE_URL}/route/v1/driving/"
        f"{start.lon},{start.lat};{end.lon},{end.lat}"
    )
    params = {
        "overview": "simplified",
        "geometries": "geojson",
        "steps": "false",
    }
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    data: dict[str, Any] = response.json()

    if data.get("code") != "Ok" or not data.get("routes"):
        raise RoutingError(data.get("message", "Unable to compute route"))

    route = data["routes"][0]
    coordinates = route["geometry"]["coordinates"]
    line = LineString(coordinates)

    distance_miles = route["distance"] / METERS_PER_MILE
    duration_minutes = route["duration"] / 60.0

    return RouteResult(
        line=line,
        coordinates=coordinates,
        distance_miles=round(distance_miles, 2),
        duration_minutes=round(duration_minutes, 1),
    )


@lru_cache(maxsize=256)
def _get_route_cached(
    start_lat: float, start_lon: float, end_lat: float, end_lon: float
) -> RouteResult:
    """Cached wrapper — rounds coords to 3 decimals (~100m precision)."""
    return _fetch_osrm_route(
        Coordinates(lat=start_lat, lon=start_lon),
        Coordinates(lat=end_lat, lon=end_lon),
    )


def get_route(start: Coordinates, end: Coordinates) -> RouteResult:
    """
    Fetch a driving route between two points using the OSRM public API.

    Results are cached by rounded coordinates to speed up repeated queries.
    """
    return _get_route_cached(
        round(start.lat, 3),
        round(start.lon, 3),
        round(end.lat, 3),
        round(end.lon, 3),
    )
