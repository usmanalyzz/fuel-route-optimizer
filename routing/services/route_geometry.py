"""
Route geometry utilities for distance and projection calculations.

Provides haversine distance, cumulative mile markers along a route,
point-to-route projection, polyline simplification, and bounding box helpers.
"""
import math

from shapely.geometry import LineString, Point

from routing.constants import METERS_PER_MILE

# Max polyline vertices used for station filtering (keeps projection fast)
MAX_ROUTE_POINTS = 300


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points in miles.

    Uses the haversine formula for accuracy over short and medium distances.
    """
    radius_miles = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius_miles * math.asin(math.sqrt(a))


def simplify_coordinates(
    coordinates: list[list[float]], max_points: int = MAX_ROUTE_POINTS
) -> list[list[float]]:
    """
    Reduce route polyline to at most max_points vertices via uniform sampling.

    Keeps first and last points. Used before station projection to avoid
    O(stations × route_vertices) blow-up on long OSRM routes.
    """
    if len(coordinates) <= max_points:
        return coordinates

    step = (len(coordinates) - 1) / (max_points - 1)
    simplified = [coordinates[0]]
    for i in range(1, max_points - 1):
        simplified.append(coordinates[int(round(i * step))])
    simplified.append(coordinates[-1])
    return simplified


def build_cumulative_distances(coordinates: list[list[float]]) -> list[float]:
    """
    Build a list of cumulative mile markers for each route vertex.

    Index i gives the total miles from the route start to coordinate i.
    """
    if not coordinates:
        return []

    cumulative = [0.0]
    for i in range(1, len(coordinates)):
        lon1, lat1 = coordinates[i - 1]
        lon2, lat2 = coordinates[i]
        cumulative.append(
            cumulative[-1] + haversine_miles(lat1, lon1, lat2, lon2)
        )
    return cumulative


def project_point_to_route_fast(
    point_lat: float,
    point_lon: float,
    route_line: LineString,
    total_miles: float,
    corridor_miles: float,
) -> tuple[float, float] | None:
    """
    Fast point-to-route projection using Shapely C implementations.

    Returns (mile_marker, distance_to_route_miles) or None if outside corridor.
    """
    line_length = route_line.length
    if line_length == 0:
        return None

    point = Point(point_lon, point_lat)
    dist_miles = point.distance(route_line) * 69.0
    if dist_miles > corridor_miles:
        return None

    mile_marker = (route_line.project(point) / line_length) * total_miles
    return mile_marker, dist_miles


def project_point_to_route(
    point_lat: float,
    point_lon: float,
    route_line: LineString,
    cumulative_miles: list[float],
) -> tuple[float, float]:
    """
    Project a fuel station point onto the nearest point on the route polyline.

    Legacy precise implementation — prefer project_point_to_route_fast for bulk use.
    Returns (mile_marker, distance_to_route_miles).
    """
    coords = list(route_line.coords)
    best_distance = float("inf")
    best_mile = 0.0

    for i in range(len(coords) - 1):
        lon1, lat1 = coords[i]
        lon2, lat2 = coords[i + 1]
        seg_len = haversine_miles(lat1, lon1, lat2, lon2)
        if seg_len == 0:
            continue

        dx, dy = lon2 - lon1, lat2 - lat1
        t = ((point_lon - lon1) * dx + (point_lat - lat1) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))

        proj_lon = lon1 + t * dx
        proj_lat = lat1 + t * dy
        dist = haversine_miles(point_lat, point_lon, proj_lat, proj_lon)

        if dist < best_distance:
            best_distance = dist
            seg_start_mile = cumulative_miles[i]
            best_mile = seg_start_mile + t * seg_len

    shapely_dist_degrees = Point(point_lon, point_lat).distance(route_line)
    approx_dist_miles = shapely_dist_degrees * 69.0

    return best_mile, min(best_distance, approx_dist_miles)


def route_bounding_box(
    coordinates: list[list[float]], buffer_miles: float
) -> tuple[float, float, float, float]:
    """
    Compute a lat/lon bounding box around the route with a buffer.

    Returns (min_lat, max_lat, min_lon, max_lon).
    """
    lats = [c[1] for c in coordinates]
    lons = [c[0] for c in coordinates]
    lat_buffer = buffer_miles / 69.0
    lon_buffer = buffer_miles / 55.0
    return (
        min(lats) - lat_buffer,
        max(lats) + lat_buffer,
        min(lons) - lon_buffer,
        max(lons) + lon_buffer,
    )
