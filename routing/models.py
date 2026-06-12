"""
Database models for fuel stations and geocoding cache.

FuelStation stores pre-geocoded truck stop data imported from CSV.
GeocodeCache avoids repeated Nominatim calls for the same city/state pair.
"""
from django.db import models


class GeocodeCache(models.Model):
    """
    Persistent cache of city/state → latitude/longitude lookups.

    Populated during fuel price import so the same city is never
    geocoded twice via Nominatim.
    """

    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)
    latitude = models.FloatField()
    longitude = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("city", "state")
        indexes = [models.Index(fields=["city", "state"])]

    def __str__(self):
        return f"{self.city}, {self.state}"


class FuelStation(models.Model):
    """
    A US truck stop with fuel price and geocoded coordinates.

    Coordinates are assigned at import time (city/state geocoding or
    state centroid in dev mode). Used by the fuel optimizer to find
    stations near the driving route.
    """

    opis_id = models.IntegerField(db_index=True, unique=True)  # Unique station ID from CSV
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2, db_index=True)
    retail_price = models.DecimalField(max_digits=8, decimal_places=4)  # USD per gallon
    latitude = models.FloatField()
    longitude = models.FloatField()

    class Meta:
        indexes = [
            # Speed up bounding-box queries during route optimization
            models.Index(fields=["state", "latitude", "longitude"]),
            models.Index(fields=["latitude", "longitude"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.city}, {self.state})"
