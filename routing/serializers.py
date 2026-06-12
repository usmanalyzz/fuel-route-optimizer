"""
DRF serializers for the route optimization API.

Defines request validation (start/finish as address or coordinates)
and response schema documentation.
"""
from rest_framework import serializers


class CoordinateSerializer(serializers.Serializer):
    """Validates a lat/lon coordinate pair."""

    lat = serializers.FloatField(min_value=-90, max_value=90)
    lon = serializers.FloatField(min_value=-180, max_value=180)


class LocationField(serializers.Field):
    """
    Custom field that accepts either:
      - A string address: "Chicago, IL"
      - A coordinate object: {"lat": 41.88, "lon": -87.63}

    Normalizes both into an internal dict with 'type' and 'value' keys.
    """

    def to_internal_value(self, data):
        # Case 1: plain text address
        if isinstance(data, str):
            if not data.strip():
                raise serializers.ValidationError("Location cannot be empty.")
            return {"type": "address", "value": data.strip()}

        # Case 2: coordinate object
        if isinstance(data, dict):
            coord = CoordinateSerializer(data=data)
            coord.is_valid(raise_exception=True)
            return {"type": "coordinates", "value": coord.validated_data}

        raise serializers.ValidationError(
            "Location must be a string address or {lat, lon} object."
        )


class RouteRequestSerializer(serializers.Serializer):
    """Validates POST /api/v1/route/ request body."""

    start = LocationField()
    finish = LocationField()


class StationSerializer(serializers.Serializer):
    """Schema for a fuel station in the API response."""

    name = serializers.CharField()
    address = serializers.CharField()
    city = serializers.CharField()
    state = serializers.CharField()
    retail_price = serializers.DecimalField(max_digits=8, decimal_places=4)
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()


class FuelStopSerializer(serializers.Serializer):
    """Schema for a single recommended fuel stop in the API response."""

    mile_marker = serializers.FloatField()      # Miles from route start
    station = StationSerializer()
    segment_miles = serializers.FloatField()    # Miles driven since last stop
    gallons = serializers.FloatField()          # Fuel consumed on this segment
    cost_usd = serializers.FloatField()         # Cost at this stop


class RouteGeometrySerializer(serializers.Serializer):
    """Schema for the route map geometry in the API response."""

    type = serializers.CharField()              # Always "LineString"
    coordinates = serializers.ListField(child=serializers.ListField(child=serializers.FloatField()))
    distance_miles = serializers.FloatField()
    duration_minutes = serializers.FloatField()


class AssumptionsSerializer(serializers.Serializer):
    """Documents the vehicle constraints used in the calculation."""

    max_range_miles = serializers.IntegerField()
    mpg = serializers.IntegerField()


class RouteResponseSerializer(serializers.Serializer):
    """Full API response schema (used for documentation/validation)."""

    route = RouteGeometrySerializer()
    fuel_stops = FuelStopSerializer(many=True)
    total_fuel_cost_usd = serializers.FloatField()
    total_gallons = serializers.FloatField()
    assumptions = AssumptionsSerializer()
