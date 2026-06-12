"""
API views for the Fuel Route Optimizer.

RouteView is the main entry point: it orchestrates geocoding, routing,
and fuel optimization into a single JSON response.
"""
from concurrent.futures import ThreadPoolExecutor

import requests
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from routing.serializers import RouteRequestSerializer
from routing.services.fuel_optimizer import FuelOptimizationError, optimize_fuel_stops
from routing.services.geocoding import (
    GeocodingError,
    LocationNotFoundError,
    LocationOutsideUSAError,
    Coordinates,
    geocode_address,
)
from routing.services.routing import RoutingError, get_route


class RouteView(APIView):
    """
    POST /api/v1/route/

    Accepts start and finish locations, returns driving route geometry
    and cost-optimal fuel stops along the route.
    """

    def post(self, request):
        """Handle a route optimization request."""
        serializer = RouteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            start_data = serializer.validated_data["start"]
            finish_data = serializer.validated_data["finish"]

            # Geocode start and finish in parallel when both are addresses
            start, finish = self._resolve_locations_parallel(start_data, finish_data)

            route = get_route(start, finish)
            optimization = optimize_fuel_stops(route)

        except LocationNotFoundError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except LocationOutsideUSAError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except RoutingError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except FuelOptimizationError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except requests.RequestException as exc:
            return Response(
                {"error": f"External routing service error: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except GeocodingError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        fuel_stops = [
            {
                "mile_marker": stop.mile_marker,
                "station": {
                    "name": stop.station.name,
                    "address": stop.station.address,
                    "city": stop.station.city,
                    "state": stop.station.state,
                    "retail_price": stop.station.retail_price,
                    "latitude": stop.station.latitude,
                    "longitude": stop.station.longitude,
                },
                "segment_miles": stop.segment_miles,
                "gallons": stop.gallons,
                "cost_usd": stop.cost_usd,
            }
            for stop in optimization.fuel_stops
        ]

        return Response(
            {
                "route": {
                    "type": "LineString",
                    "coordinates": route.coordinates,
                    "distance_miles": route.distance_miles,
                    "duration_minutes": route.duration_minutes,
                },
                "fuel_stops": fuel_stops,
                "total_fuel_cost_usd": optimization.total_fuel_cost_usd,
                "total_gallons": optimization.total_gallons,
                "assumptions": {
                    "max_range_miles": settings.MAX_RANGE_MILES,
                    "mpg": settings.MPG,
                },
            }
        )

    def _resolve_locations_parallel(self, start: dict, finish: dict) -> tuple[Coordinates, Coordinates]:
        """
        Resolve start and finish concurrently when both need geocoding.

        Coordinate inputs skip geocoding entirely (instant).
        """
        if start["type"] == "coordinates" and finish["type"] == "coordinates":
            return self._resolve_location(start), self._resolve_location(finish)

        with ThreadPoolExecutor(max_workers=2) as executor:
            start_future = executor.submit(self._resolve_location, start)
            finish_future = executor.submit(self._resolve_location, finish)
            return start_future.result(), finish_future.result()

    def _resolve_location(self, location: dict) -> Coordinates:
        """Convert a validated location input to Coordinates."""
        if location["type"] == "coordinates":
            coords = location["value"]
            lat, lon = coords["lat"], coords["lon"]
            from routing.services.geocoding import is_within_usa

            if not is_within_usa(lat, lon):
                raise LocationOutsideUSAError(
                    f"Coordinates ({lat}, {lon}) are outside the USA."
                )
            return Coordinates(lat=lat, lon=lon)

        return geocode_address(location["value"])
