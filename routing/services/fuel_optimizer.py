"""
Fuel stop optimizer — finds minimum-cost fuel stops along a driving route.

Uses corridor filtering to find nearby stations, then Dijkstra's algorithm
on a 1D graph to minimize total fuel cost while respecting the 500-mile
range constraint.
"""
import heapq
from dataclasses import dataclass

from django.conf import settings
from shapely.geometry import LineString

from routing.models import FuelStation
from routing.services.route_geometry import (
    project_point_to_route_fast,
    route_bounding_box,
    simplify_coordinates,
)
from routing.services.routing import RouteResult


class FuelOptimizationError(Exception):
    """Raised when no valid fuel stop sequence can be found."""


@dataclass
class FuelStop:
    """A recommended fuel stop along the route."""

    mile_marker: float
    station: FuelStation
    segment_miles: float
    gallons: float
    cost_usd: float


@dataclass
class OptimizationResult:
    """Complete fuel optimization output."""

    fuel_stops: list[FuelStop]
    total_fuel_cost_usd: float
    total_gallons: float


def _dedupe_stations_by_location(stations: list[FuelStation]) -> list[FuelStation]:
    """
    Keep the cheapest station at each rounded lat/lon location.

    Critical when using --skip-geocode imports where all stations in a state
    share identical coordinates.
    """
    best: dict[tuple[float, float], FuelStation] = {}
    for station in stations:
        key = (round(station.latitude, 2), round(station.longitude, 2))
        if key not in best or station.retail_price < best[key].retail_price:
            best[key] = station
    return list(best.values())


def _get_candidate_stations(
    route: RouteResult,
    corridor_miles: float,
) -> list[tuple[FuelStation, float]]:
    """
    Find fuel stations within the corridor distance of the route.

    Optimized pipeline:
        1. Simplify route polyline to ~300 points
        2. SQL bounding-box pre-filter
        3. Deduplicate co-located stations (keep cheapest)
        4. Fast Shapely projection per unique location
    """
    simplified_coords = simplify_coordinates(route.coordinates)
    min_lat, max_lat, min_lon, max_lon = route_bounding_box(simplified_coords, corridor_miles)

    candidates = list(
        FuelStation.objects.filter(
            latitude__gte=min_lat,
            latitude__lte=max_lat,
            longitude__gte=min_lon,
            longitude__lte=max_lon,
        ).only(
            "id", "opis_id", "name", "address", "city", "state",
            "retail_price", "latitude", "longitude",
        )
    )

    unique_stations = _dedupe_stations_by_location(candidates)
    route_line = LineString(simplified_coords)
    total_miles = route.distance_miles

    stations_with_mile_marker: list[tuple[FuelStation, float]] = []
    for station in unique_stations:
        result = project_point_to_route_fast(
            station.latitude,
            station.longitude,
            route_line,
            total_miles,
            corridor_miles,
        )
        if result is not None:
            mile_marker, _ = result
            stations_with_mile_marker.append((station, mile_marker))

    stations_with_mile_marker.sort(key=lambda item: item[1])
    return stations_with_mile_marker


def _dijkstra_fuel_stops(
    total_miles: float,
    stations: list[tuple[FuelStation, float]],
    max_range: float,
    mpg: float,
) -> tuple[list[FuelStop], float, float]:
    """
    Find minimum-cost fuel stop sequence using Dijkstra's algorithm.

    Optimized with forward-only edge traversal since stations are sorted
    by mile_marker — O(n * k) where k is avg reachable stations per node.
    """
    n = len(stations)
    end_node = n + 1
    total_nodes = n + 2

    mile_markers = [0.0] + [s[1] for s in stations] + [total_miles]
    prices = [0.0] + [float(s[0].retail_price) for s in stations] + [0.0]

    def edge_cost(from_node: int, to_node: int) -> float:
        segment = mile_markers[to_node] - mile_markers[from_node]
        if segment <= 0:
            return float("inf")
        gallons = segment / mpg
        if to_node == end_node:
            return gallons * prices[from_node]
        return gallons * prices[to_node]

    dist = [float("inf")] * total_nodes
    prev = [-1] * total_nodes
    dist[0] = 0.0
    heap = [(0.0, 0)]

    while heap:
        cost, node = heapq.heappop(heap)
        if cost > dist[node]:
            continue
        if node == end_node:
            break

        from_mile = mile_markers[node]
        for next_node in range(node + 1, total_nodes):
            if mile_markers[next_node] - from_mile > max_range + 1e-6:
                break

            edge = edge_cost(node, next_node)
            if node == 0 and next_node == end_node and total_miles <= max_range:
                edge = 0.0
            new_cost = dist[node] + edge
            if new_cost < dist[next_node]:
                dist[next_node] = new_cost
                prev[next_node] = node
                heapq.heappush(heap, (new_cost, next_node))

    if dist[end_node] == float("inf"):
        raise FuelOptimizationError(
            "No valid fuel stop sequence found along this route. "
            "Try widening the corridor or check station coverage."
        )

    path: list[int] = []
    current = end_node
    while current != -1:
        path.append(current)
        current = prev[current]
    path.reverse()

    fuel_stops: list[FuelStop] = []
    total_gallons = 0.0
    total_cost = dist[end_node]

    for i in range(len(path) - 1):
        from_node, to_node = path[i], path[i + 1]

        if to_node == end_node:
            if from_node == 0:
                break
            segment = total_miles - mile_markers[from_node]
            total_gallons += segment / mpg
            break

        segment = mile_markers[to_node] - mile_markers[from_node]
        gallons = segment / mpg
        cost = gallons * prices[to_node]
        total_gallons += gallons
        station, mile_marker = stations[to_node - 1]
        fuel_stops.append(
            FuelStop(
                mile_marker=round(mile_marker, 2),
                station=station,
                segment_miles=round(segment, 2),
                gallons=round(gallons, 2),
                cost_usd=round(cost, 2),
            )
        )

    return fuel_stops, round(total_cost, 2), round(total_gallons, 2)


def optimize_fuel_stops(route: RouteResult) -> OptimizationResult:
    """
    Main entry point: find optimal fuel stops for a driving route.

    Assumes vehicle starts with a full tank (500-mile range).
    Trips <= 500 miles require no fuel stops and cost $0.
    """
    max_range = settings.MAX_RANGE_MILES
    mpg = settings.MPG
    corridor = settings.CORRIDOR_MILES
    total_miles = route.distance_miles

    if total_miles <= max_range:
        return OptimizationResult(
            fuel_stops=[],
            total_fuel_cost_usd=0.0,
            total_gallons=0.0,
        )

    candidates = _get_candidate_stations(route, corridor)
    if not candidates:
        raise FuelOptimizationError("No fuel stations found near the route corridor.")

    fuel_stops, total_cost, total_gallons = _dijkstra_fuel_stops(
        total_miles, candidates, max_range, mpg
    )

    return OptimizationResult(
        fuel_stops=fuel_stops,
        total_fuel_cost_usd=total_cost,
        total_gallons=total_gallons,
    )
