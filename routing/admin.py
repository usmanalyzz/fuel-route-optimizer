"""Django admin configuration for routing models."""
from django.contrib import admin

from routing.models import FuelStation, GeocodeCache


@admin.register(FuelStation)
class FuelStationAdmin(admin.ModelAdmin):
    """Admin interface for browsing imported fuel stations."""

    list_display = ("opis_id", "name", "city", "state", "retail_price")
    list_filter = ("state",)
    search_fields = ("name", "city", "address")


@admin.register(GeocodeCache)
class GeocodeCacheAdmin(admin.ModelAdmin):
    """Admin interface for viewing cached geocoding results."""

    list_display = ("city", "state", "latitude", "longitude")
