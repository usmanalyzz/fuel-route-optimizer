"""Unit tests for the fuel stop optimizer algorithm."""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from shapely.geometry import LineString

from routing.models import FuelStation
from routing.services.fuel_optimizer import _dijkstra_fuel_stops, optimize_fuel_stops
from routing.services.routing import RouteResult


class FuelOptimizerTests(TestCase):
    """Tests for Dijkstra fuel stop optimization logic."""

    def setUp(self):
        """Create sample fuel stations for optimizer tests."""
        self.station_a = FuelStation.objects.create(
            opis_id=1,
            name="Cheap Stop",
            address="I-40",
            city="Amarillo",
            state="TX",
            retail_price=Decimal("2.50"),
            latitude=35.2,
            longitude=-101.8,
        )
        self.station_b = FuelStation.objects.create(
            opis_id=2,
            name="Mid Stop",
            address="I-40",
            city="Oklahoma City",
            state="OK",
            retail_price=Decimal("3.00"),
            latitude=35.5,
            longitude=-97.5,
        )
        self.station_c = FuelStation.objects.create(
            opis_id=3,
            name="Pricey Stop",
            address="I-40",
            city="Memphis",
            state="TN",
            retail_price=Decimal("4.00"),
            latitude=35.1,
            longitude=-90.0,
        )

    def test_fuel_cost_math_short_route(self):
        """Routes <= 500 miles should need no fuel stops and cost $0."""
        route = RouteResult(
            line=LineString([(-118.24, 34.05), (-117.16, 32.72)]),
            coordinates=[[-118.24, 34.05], [-117.16, 32.72]],
            distance_miles=120.0,
            duration_minutes=120.0,
        )
        result = optimize_fuel_stops(route)
        self.assertEqual(result.fuel_stops, [])
        self.assertEqual(result.total_fuel_cost_usd, 0.0)

    def test_dijkstra_picks_cheaper_station(self):
        """Dijkstra should find a valid path with positive total cost."""
        stations = [
            (self.station_a, 200.0),
            (self.station_b, 400.0),
            (self.station_c, 600.0),
        ]
        stops, total_cost, total_gallons = _dijkstra_fuel_stops(
            total_miles=700.0,
            stations=stations,
            max_range=500.0,
            mpg=10.0,
        )
        self.assertGreater(len(stops), 0)
        self.assertAlmostEqual(total_gallons, 70.0, places=1)
        self.assertGreater(total_cost, 0)

    def test_long_route_requires_stops_within_range(self):
        """Consecutive fuel stops should never be more than 500 miles apart."""
        route = RouteResult(
            line=LineString([(-87.62, 41.88), (-104.99, 39.74)]),
            coordinates=[[-87.62, 41.88], (-98.0, 40.0), [-104.99, 39.74]],
            distance_miles=920.0,
            duration_minutes=840.0,
        )
        FuelStation.objects.create(
            opis_id=10,
            name="Corridor Stop",
            address="I-80",
            city="Des Moines",
            state="IA",
            retail_price=Decimal("3.10"),
            latitude=41.5,
            longitude=-93.6,
        )
        with patch(
            "routing.services.fuel_optimizer._get_candidate_stations",
            return_value=[(self.station_a, 300.0), (self.station_b, 600.0)],
        ):
            result = optimize_fuel_stops(route)
        for i in range(len(result.fuel_stops) - 1):
            gap = result.fuel_stops[i + 1].mile_marker - result.fuel_stops[i].mile_marker
            self.assertLessEqual(gap, 500.0)
