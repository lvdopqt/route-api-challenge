# Route Fuel API

This project is a Django application that provides two main functionalities related to route planning and fuel stops:

1. **Gas Station Data Enrichment:** A management command to import and enrich gas station information, including geocoding addresses.

2. **Route Planning API:** An API endpoint to calculate a route between two points, identify optimal fuel stops along the way based on vehicle range, and estimate the total fuel cost.

## Installation

Follow these steps to get the project up and running:

1. **Clone the repository:**

```
git clone &lt;repository_url>
cd route_fuel_api
```

2. **Create and activate a virtual environment:**

```
python -m venv venv
source venv/bin/activate
```

3. **Install dependencies:**

```
pip install -r requirements.txt
```


5. **Run database migrations:**

python manage.py migrate


## Configuration

Ensure the following settings are configured, preferably via environment.

* `OPENROUTESERVICE_API_KEY`: Your API key from OpenRouteService (used for route calculations). You can generate it [here](https://account.heigit.org/manage/key)


## Usage

The application provides two main flows:

### 1. Enriching Gas Station Data

This flow involves importing gas station data from a CSV file and using the Nominatim service to geocode their addresses.

* **Run the management command:**
```
python manage.py import_fuel_prices_command /path/to/your/fuel_prices.csv
```

This command will read the CSV, update or create `GasStation` records in the database, and attempt to geocode the address for each station using the Nominatim service.

### 2. Route Planning API

This flow allows users to get a planned route between two points, including optimal fuel stops.

* **Endpoint:** `/route-plan/` (GET request)

* **Parameters:**

* `start`: The starting coordinates as a comma-separated string `longitude,latitude` (e.g., `-74.0060,40.7128`).

* `end`: The ending coordinates as a comma-separated string `longitude,latitude` (e.g., `-77.0369,38.9072`).

* **Example Request:**

curl "https://www.google.com/search?q=http://127.0.0.1:8000/route-plan/%3Fstart%3D-74.0060,40.7128%26end%3D-77.0369,38.9072"


* **Response:**
A JSON object containing the route details, including:

* `total_distance_miles`: Total route distance.

* `total_duration_seconds`: Estimated total travel time.

* `total_fuel_cost_usd`: Estimated total fuel cost based on stops.

* `fuel_stops`: A list of optimal fuel stops with their location (\[latitude, longitude\]), fuel price, and approximate distance from the start.

* `route_geometry`: A list of coordinates (\[latitude, longitude\] pairs) representing the route line.

*(Note: The `RoutePlanner` logic finds stops based on an initial route and calculates cost. The returned `route_geometry` is the initial route, not necessarily a multi-stop route geometry.)*

## Running Tests

To run the project's tests, use the Django test command:

```
python manage.py test
```

This will discover and run tests in your app's `tests` directory.