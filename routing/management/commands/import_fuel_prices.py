"""
Management command to import fuel prices from CSV into PostgreSQL.

Run once during setup:
    python manage.py import_fuel_prices data/fuel-prices-for-be-assessment.csv

Options:
    --skip-geocode  Use state centroids instead of Nominatim (fast dev mode)
    --limit N       Import only first N stations (for testing)
"""
import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from routing.constants import US_STATES
from routing.models import FuelStation
from routing.services.geocoding import GeocodingError, geocode_city_state


class Command(BaseCommand):
    """Import fuel station data from CSV, geocode, and store in PostgreSQL."""

    help = "Import fuel prices from CSV, geocode stations, and load into PostgreSQL."

    def add_arguments(self, parser):
        """Define CLI arguments for the import command."""
        parser.add_argument("csv_path", type=str, help="Path to fuel prices CSV file")
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limit number of stations to import (for testing)",
        )
        parser.add_argument(
            "--skip-geocode",
            action="store_true",
            help="Skip geocoding and use state centroid placeholders (dev only)",
        )

    def handle(self, *args, **options):
        """
        Main import logic: parse CSV, geocode each station, save to DB.

        For each unique OPIS station ID:
            1. Get lat/lon (Nominatim or state centroid)
            2. Upsert into FuelStation table
        """
        csv_path = Path(options["csv_path"])
        if not csv_path.exists():
            raise CommandError(f"File not found: {csv_path}")

        stations = self._parse_csv(csv_path)
        if options["limit"]:
            stations = dict(list(stations.items())[: options["limit"]])

        self.stdout.write(f"Importing {len(stations)} unique stations...")

        created = 0
        updated = 0
        failed = 0

        for opis_id, row in stations.items():
            city = row["city"]
            state = row["state"]

            try:
                if options["skip_geocode"]:
                    # Dev mode: use approximate state center (fast, less accurate)
                    lat, lon = self._state_centroid(state)
                else:
                    # Production mode: geocode city/state via Nominatim (rate-limited)
                    coords = geocode_city_state(city, state, rate_limit=True)
                    lat, lon = coords.lat, coords.lon
            except GeocodingError as exc:
                self.stderr.write(f"Geocode failed for {city}, {state}: {exc}")
                failed += 1
                continue

            # Insert or update station in PostgreSQL
            _, was_created = FuelStation.objects.update_or_create(
                opis_id=opis_id,
                defaults={
                    "name": row["name"],
                    "address": row["address"],
                    "city": city,
                    "state": state,
                    "retail_price": row["price"],
                    "latitude": lat,
                    "longitude": lon,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created: {created}, Updated: {updated}, Failed: {failed}"
            )
        )

    def _parse_csv(self, csv_path: Path) -> dict[int, dict]:
        """
        Parse the fuel prices CSV and deduplicate by OPIS Truckstop ID.

        Cleaning rules:
            - Skip non-US states (Canadian provinces, etc.)
            - Trim whitespace from city/state fields
            - Keep lowest retail price when duplicate OPIS IDs exist

        Returns:
            Dict mapping opis_id → station row dict.
        """
        stations: dict[int, dict] = {}

        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                state = row["State"].strip().upper()
                if state not in US_STATES:
                    continue  # Skip Canadian and other non-US entries

                try:
                    opis_id = int(row["OPIS Truckstop ID"])
                    price = Decimal(row["Retail Price"].strip())
                except (ValueError, InvalidOperation, KeyError):
                    continue  # Skip malformed rows

                city = " ".join(row["City"].split())  # Normalize whitespace
                entry = {
                    "name": row["Truckstop Name"].strip(),
                    "address": row["Address"].strip(),
                    "city": city,
                    "state": state,
                    "price": price,
                }

                # Keep the lowest price when the same OPIS ID appears multiple times
                if opis_id not in stations or price < stations[opis_id]["price"]:
                    stations[opis_id] = entry

        return stations

    def _state_centroid(self, state: str) -> tuple[float, float]:
        """
        Return approximate geographic center coordinates for a US state.

        Used only with --skip-geocode for fast local development.
        All stations in a state get the same coordinates in this mode.

        Args:
            state: Two-letter state code

        Returns:
            (latitude, longitude) tuple.
        """
        centroids = {
            "AL": (32.806671, -86.791130),
            "AK": (61.370716, -152.404419),
            "AZ": (33.729759, -111.431221),
            "AR": (34.969704, -92.373123),
            "CA": (36.116203, -119.681564),
            "CO": (39.059811, -105.311104),
            "CT": (41.597782, -72.755371),
            "DE": (39.318523, -75.507141),
            "FL": (27.766279, -81.686783),
            "GA": (33.040619, -83.643074),
            "HI": (21.094318, -157.498337),
            "ID": (44.240459, -114.478828),
            "IL": (40.349457, -88.986137),
            "IN": (39.849426, -86.258278),
            "IA": (42.011539, -93.210526),
            "KS": (38.526600, -96.726486),
            "KY": (37.668140, -84.670067),
            "LA": (31.169546, -91.867805),
            "ME": (44.693947, -69.381927),
            "MD": (39.063946, -76.802101),
            "MA": (42.230171, -71.530106),
            "MI": (43.326618, -84.536095),
            "MN": (45.694454, -93.900192),
            "MS": (32.741646, -89.678696),
            "MO": (38.456085, -92.288368),
            "MT": (46.921925, -110.454353),
            "NE": (41.125370, -98.268082),
            "NV": (38.313515, -117.055374),
            "NH": (43.452492, -71.563896),
            "NJ": (40.298904, -74.521011),
            "NM": (34.840515, -106.248482),
            "NY": (42.165726, -74.948051),
            "NC": (35.630066, -79.806419),
            "ND": (47.528912, -99.784012),
            "OH": (40.388783, -82.764915),
            "OK": (35.565342, -96.928917),
            "OR": (44.572021, -122.070938),
            "PA": (40.590752, -77.209755),
            "RI": (41.680893, -71.511780),
            "SC": (33.856892, -80.945007),
            "SD": (44.299782, -99.438828),
            "TN": (35.747845, -86.692345),
            "TX": (31.054487, -97.563461),
            "UT": (40.150032, -111.862434),
            "VT": (44.045876, -72.710686),
            "VA": (37.769337, -78.169968),
            "WA": (47.400902, -121.490494),
            "WV": (38.491226, -80.954453),
            "WI": (44.268543, -89.616508),
            "WY": (42.755966, -107.302490),
            "DC": (38.897438, -77.026817),
        }
        # Default to geographic center of continental US if state not found
        return centroids.get(state, (39.8283, -98.5795))
