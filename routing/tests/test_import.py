"""Unit tests for the import_fuel_prices management command."""
import csv
import tempfile
from decimal import Decimal
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from routing.models import FuelStation


class ImportFuelPricesTests(TestCase):
    """Tests for CSV parsing, deduplication, and US-state filtering."""

    def _write_csv(self, rows: list[dict]) -> Path:
        """Write test rows to a temporary CSV file and return its path."""
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="")
        fieldnames = [
            "OPIS Truckstop ID",
            "Truckstop Name",
            "Address",
            "City",
            "State",
            "Rack ID",
            "Retail Price",
        ]
        writer = csv.DictWriter(tmp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        tmp.close()
        return Path(tmp.name)

    def test_import_dedup_keeps_lowest_price(self):
        """Duplicate OPIS IDs should keep the row with the lowest retail price."""
        csv_path = self._write_csv(
            [
                {
                    "OPIS Truckstop ID": "100",
                    "Truckstop Name": "Station A",
                    "Address": "I-40",
                    "City": "Flagstaff",
                    "State": "AZ",
                    "Rack ID": "1",
                    "Retail Price": "3.50",
                },
                {
                    "OPIS Truckstop ID": "100",
                    "Truckstop Name": "Station A",
                    "Address": "I-40",
                    "City": "Flagstaff",
                    "State": "AZ",
                    "Rack ID": "1",
                    "Retail Price": "3.10",
                },
            ]
        )
        call_command("import_fuel_prices", str(csv_path), "--skip-geocode")
        station = FuelStation.objects.get(opis_id=100)
        self.assertEqual(station.retail_price, Decimal("3.10"))

    def test_import_filters_non_us_states(self):
        """Canadian provinces and other non-US states should be excluded."""
        csv_path = self._write_csv(
            [
                {
                    "OPIS Truckstop ID": "200",
                    "Truckstop Name": "Canadian Station",
                    "Address": "HWY 401",
                    "City": "London",
                    "State": "ON",
                    "Rack ID": "1",
                    "Retail Price": "3.50",
                },
                {
                    "OPIS Truckstop ID": "201",
                    "Truckstop Name": "US Station",
                    "Address": "I-10",
                    "City": "Phoenix",
                    "State": "AZ",
                    "Rack ID": "1",
                    "Retail Price": "3.20",
                },
            ]
        )
        call_command("import_fuel_prices", str(csv_path), "--skip-geocode")
        self.assertEqual(FuelStation.objects.count(), 1)
        self.assertEqual(FuelStation.objects.first().state, "AZ")
