"""
Shared constants used across the routing application.

Includes US state codes for CSV filtering and unit conversion factors
for distance calculations.
"""

# Valid US state/territory codes — used to filter non-US rows from the CSV
US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}

# Conversion factors for distance math
METERS_PER_MILE = 1609.344       # OSRM returns distance in meters
DEGREES_PER_MILE_LAT = 1 / 69.0  # Approximate lat degrees per mile
