# Fuel Route Optimizer

Django REST API that computes a driving route between two USA locations, returns GeoJSON map geometry, and recommends cost-optimal fuel stops along the route.

## Features

- **Route mapping** via [OSRM](http://project-osrm.org/) (1 API call per request)
- **Geocoding** via [Nominatim](https://nominatim.org/) (2 API calls when using addresses)
- **Fuel optimization** using Dijkstra on stations within 25 miles of the route
- **Pre-geocoded fuel stations** from the provided CSV (~6,700 US stations)
- **Constraints**: 500-mile max range, 10 MPG, vehicle starts with a full tank

## Quick Start

### 1. Start PostgreSQL

```bash
docker compose up -d
```

### 2. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 3. Run migrations

```bash
python manage.py migrate
```

### 4. Import fuel prices

Full import geocodes ~3,900 unique city/state pairs via Nominatim (~1 hour, rate-limited):

```bash
python manage.py import_fuel_prices data/fuel-prices-for-be-assessment.csv
```

For local development / tests without waiting:

```bash
python manage.py import_fuel_prices data/fuel-prices-for-be-assessment.csv --skip-geocode
```

### 5. Run the server

```bash
python manage.py runserver
```

## API

### `POST /api/v1/route/`

**Request (addresses):**

```json
{
  "start": "Chicago, IL",
  "finish": "Denver, CO"
}
```

**Request (coordinates — skips geocoding, 1 external API call):**

```json
{
  "start": {"lat": 41.8781, "lon": -87.6298},
  "finish": {"lat": 39.7392, "lon": -104.9903}
}
```

**Response:**

```json
{
  "route": {
    "type": "LineString",
    "coordinates": [[-87.62, 41.88], ...],
    "distance_miles": 920.0,
    "duration_minutes": 840.0
  },
  "fuel_stops": [
    {
      "mile_marker": 412.5,
      "station": {
        "name": "PILOT TRAVEL CENTER",
        "address": "I-80",
        "city": "Des Moines",
        "state": "IA",
        "retail_price": "3.1000",
        "latitude": 41.5,
        "longitude": -93.6
      },
      "segment_miles": 412.5,
      "gallons": 41.25,
      "cost_usd": 127.88
    }
  ],
  "total_fuel_cost_usd": 285.0,
  "total_gallons": 92.0,
  "assumptions": {
    "max_range_miles": 500,
    "mpg": 10
  }
}
```

## Assumptions

| Parameter | Value |
|-----------|-------|
| Max range | 500 miles between fuel stops |
| Fuel economy | 10 miles per gallon |
| Starting fuel | Full tank (no cost for trips ≤ 500 miles) |
| Fuel cost | Paid at each stop for the segment driven to reach it |
| Station corridor | Within 25 miles of the route polyline |

## Architecture

```
POST /api/v1/route/
  → geocode start & finish (Nominatim, cached)
  → fetch driving route (OSRM, 1 call)
  → filter stations near route (PostgreSQL + Shapely)
  → Dijkstra min-cost fuel stop selection
  → JSON response with GeoJSON route + fuel stops
```

## Tests

```bash
python manage.py test routing
```

Tests mock external HTTP calls and use SQLite in-memory.

## Loom Demo Script (5 min)

1. Show `docker compose up -d` and `python manage.py runserver`
2. Postman: `POST http://127.0.0.1:8000/api/v1/route/` with Chicago → Denver
3. Highlight response: route geometry, fuel stops, `total_fuel_cost_usd`
4. Walk through `routing/views.py` → `fuel_optimizer.py` → `import_fuel_prices.py`
5. Mention: 3 external API calls per address-based request; stations pre-geocoded offline

## Project Structure

```
config/          Django settings & URLs
routing/         API app
  services/      geocoding, routing, fuel optimizer
  management/    import_fuel_prices command
data/            fuel-prices-for-be-assessment.csv
```
