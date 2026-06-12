"""Unit tests for the route optimization API endpoint."""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from shapely.geometry import LineString

from routing.models import FuelStation
from routing.services.fuel_optimizer import FuelStop, OptimizationResult
from routing.services.geocoding import Coordinates
from routing.services.routing import RouteResult


class RouteAPITests(TestCase):
    """Tests for POST /api/v1/route/ with mocked external services."""

    def setUp(self):
        """Create API client and resolve the route endpoint URL."""
        self.client = APIClient()
        self.url = reverse("route")

    @patch("routing.views.optimize_fuel_stops")
    @patch("routing.views.get_route")
    @patch("routing.views.geocode_address")
    def test_route_success(self, mock_geocode, mock_route, mock_optimize):
        """Happy path: valid addresses return route, fuel stops, and totals."""
        mock_geocode.side_effect = [
            Coordinates(lat=41.88, lon=-87.62),
            Coordinates(lat=39.74, lon=-104.99),
        ]
        mock_route.return_value = RouteResult(
            line=LineString([(-87.62, 41.88), (-104.99, 39.74)]),
            coordinates=[[-87.62, 41.88], [-104.99, 39.74]],
            distance_miles=920.0,
            duration_minutes=840.0,
        )
        station = FuelStation(
            opis_id=1,
            name="Test Stop",
            address="I-80",
            city="Des Moines",
            state="IA",
            retail_price=Decimal("3.10"),
            latitude=41.5,
            longitude=-93.6,
        )
        mock_optimize.return_value = OptimizationResult(
            fuel_stops=[
                FuelStop(
                    mile_marker=400.0,
                    station=station,
                    segment_miles=400.0,
                    gallons=40.0,
                    cost_usd=124.0,
                )
            ],
            total_fuel_cost_usd=285.0,
            total_gallons=92.0,
        )

        response = self.client.post(
            self.url,
            {"start": "Chicago, IL", "finish": "Denver, CO"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["route"]["distance_miles"], 920.0)
        self.assertEqual(len(response.data["fuel_stops"]), 1)
        self.assertEqual(response.data["total_fuel_cost_usd"], 285.0)
        self.assertEqual(mock_geocode.call_count, 2)
        mock_route.assert_called_once()

    @patch("routing.views.geocode_address")
    def test_invalid_usa_location(self, mock_geocode):
        """Non-USA addresses should return 400 Bad Request."""
        from routing.services.geocoding import LocationOutsideUSAError

        mock_geocode.side_effect = LocationOutsideUSAError("Location outside USA: Paris, France")

        response = self.client.post(
            self.url,
            {"start": "Paris, France", "finish": "Denver, CO"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_coordinates_skip_geocoding(self):
        """Providing lat/lon directly should skip Nominatim geocoding."""
        with patch("routing.views.get_route") as mock_route, patch(
            "routing.views.optimize_fuel_stops"
        ) as mock_optimize:
            mock_route.return_value = RouteResult(
                line=LineString([(-118.24, 34.05), (-117.16, 32.72)]),
                coordinates=[[-118.24, 34.05], [-117.16, 32.72]],
                distance_miles=120.0,
                duration_minutes=120.0,
            )
            mock_optimize.return_value = OptimizationResult(
                fuel_stops=[],
                total_fuel_cost_usd=0.0,
                total_gallons=0.0,
            )

            response = self.client.post(
                self.url,
                {
                    "start": {"lat": 34.05, "lon": -118.24},
                    "finish": {"lat": 32.72, "lon": -117.16},
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["fuel_stops"], [])

    def test_rejects_outside_usa_coordinates(self):
        """Coordinates outside USA bounding box should return 400."""
        response = self.client.post(
            self.url,
            {
                "start": {"lat": 48.85, "lon": 2.35},
                "finish": {"lat": 39.74, "lon": -104.99},
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
