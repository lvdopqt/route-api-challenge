import requests
from django.conf import settings
from routeplanner.utils import find_stops, haversine, calculate_cumulative_distances
# Removed imports for stdout and style

class RoutePlanner:
    FUEL_EFFICIENCY = 10  # mpg
    MAX_RANGE = 1  # miles
    DEFAULT_PRICE_PER_GALLON = 3.00
    ROUTE_SERVICE_BASE_URL = 'https://api.openrouteservice.org/v2/directions/driving-car'

    def __init__(self, start_coords, end_coords):
        """
        Initializes the RoutePlanner.

        Args:
            start_coords: Tuple or list of [longitude, latitude] for the start.
            end_coords: Tuple or list of [longitude, latitude] for the end.
        """
        # Store coordinates as [longitude, latitude] as required by OpenRouteService GET parameters
        self.start_coords = start_coords
        self.end_coords = end_coords
        # Removed initialization of self.stdout and self.style


    def _get_initial_route(self, start_segment_coords, end_segment_coords):
        """
        Calls the OpenRouteService API for the initial route (start to end).
        Uses the GET request structure shown in the user's image.
        This method is called only once in the plan().

        Args:
            start_segment_coords: [longitude, latitude] for the segment start.
            end_segment_coords: [longitude, latitude] for the segment end.

        Returns:
            A tuple containing:
            - coords: List of [longitude, latitude] pairs for the segment geometry.
            - distance_m: Total distance of the segment in meters.
            - duration_s: Total duration of the segment in seconds.

        Raises:
            Exception: If the API call fails.
        """
        # Format coordinates as strings "longitude,latitude" for GET parameters
        start_param = f"{start_segment_coords[0]},{start_segment_coords[1]}"
        end_param = f"{end_segment_coords[0]},{end_segment_coords[1]}"

        route_params = {
            'api_key': settings.OPENROUTESERVICE_API_KEY,
            'start': start_param,
            'end': end_param,
            'geometry': 'true', # Request route geometry
            'details': 'distance,duration', # Request distance and duration
        }

        

        try:
            # Use GET request as shown in the image
            resp = requests.get(self.ROUTE_SERVICE_BASE_URL, params=route_params)
            resp.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)

            route_data = resp.json()

            if not route_data.get('features'):
                 raise Exception("No route features found in initial route response.")

            feature = route_data['features'][0]
            coords = feature['geometry']['coordinates'] # List of [lon, lat] pairs for the route
            summary = feature['properties']['summary']
            distance_m = summary['distance']
            duration_s = summary['duration']

            return coords, distance_m, duration_s

        except requests.exceptions.RequestException as e:
            raise Exception(f'Failed to get initial route from OpenRouteService: {e}')
        except Exception as e:
             # Catch other potential errors during JSON parsing or data extraction
             raise Exception(f'Error processing OpenRouteService initial route response: {e}')


    def plan(self):
        """
        Plans the optimal route including fuel stops based on a single initial route.

        Steps:
        1. Get the initial route from start to end (ONE API CALL).
        2. Find optimal fuel stops along this initial route geometry.
        3. Calculate the total fuel cost based on segments of the initial route defined by the stops.

        Returns:
            A dictionary containing route details, fuel stops, and total cost.
        """
        # 1. Get the initial route from start to end (ONE API CALL)
        try:
            initial_route_coords, initial_distance_m, initial_duration_s = self._get_initial_route(self.start_coords, self.end_coords)
            initial_distance_miles = initial_distance_m / 1609.34
        except Exception as e:
            
            return {'error': f"Could not plan route: {e}"}


        # 2. Find optimal fuel stops along this initial route geometry
        
        # find_stops now queries the GasStation model directly and uses the route geometry
        # to identify stops along the path.
        optimal_stops = find_stops(initial_route_coords, initial_distance_miles, self.MAX_RANGE)

        
        # Sort stops by distance from start (approximation from find_stops)
        optimal_stops.sort(key=lambda x: x.get('distance_from_start_miles', 0))


        # 3. Calculate the total fuel cost based on segments of the initial route defined by the stops.
        
        total_fuel_cost = self._calculate_total_fuel_cost_on_route(initial_route_coords, initial_distance_miles, optimal_stops)


        # Prepare the final response
        # Return route geometry as [lat, lon] for easier use with mapping libraries on frontend
        initial_route_coords_latlon = [[coord[1], coord[0]] for coord in initial_route_coords]

        return {
            'total_distance_miles': round(initial_distance_miles, 2),
            'total_duration_seconds': initial_duration_s,
            'total_fuel_cost_usd': round(total_fuel_cost, 2),
            'fuel_stops': optimal_stops, # Return the list of selected stops
            'route_geometry': initial_route_coords_latlon, # Return the initial route geometry
        }

    def _calculate_total_fuel_cost_on_route(self, route_coords, total_route_distance_miles, optimal_stops):
        """
        Calculates the total fuel cost based on the initial route and fuel prices at stops.
        This assumes fuel is consumed along the initial route geometry.

        Args:
            route_coords: The list of [lon, lat] pairs for the initial route geometry.
            total_route_distance_miles: The total distance of the initial route in miles.
            optimal_stops: The list of selected optimal fuel stop dictionaries.

        Returns:
            The total estimated fuel cost in USD.
        """
        total_cost = 0
        # Assume no initial price, or set a default if needed. Using DEFAULT_PRICE_PER_GALLON.

        # Calculate cumulative distances along the route points
        cumulative_distances = calculate_cumulative_distances(route_coords, total_route_distance_miles)

        # Create a list of distances along the route for each waypoint (start, stops, end)
        # This requires mapping the stop coordinates back onto the route geometry.
        waypoint_distances_along_route = [0] # Start is at distance 0

        # Add distances for the optimal stops
        # This is an approximation: find the closest point on the route line to the stop's coordinates
        # and use its cumulative distance.
        for stop in optimal_stops:
            stop_coords = [stop['location'][1], stop['location'][0]] # Convert [lat, lon] to [lon, lat]
            closest_route_point_index = 0
            min_dist_to_waypoint = float('inf')
            for i, route_point in enumerate(route_coords):
                 dist = haversine(stop_coords, route_point)
                 if dist < min_dist_to_waypoint:
                     min_dist_to_waypoint = dist
                     closest_route_point_index = i
            waypoint_distances_along_route.append(cumulative_distances[closest_route_point_index])

        waypoint_distances_along_route.append(total_route_distance_miles) # End is at the total distance

        # Sort the waypoint distances to ensure segments are in order
        waypoint_distances_along_route.sort()

        # Calculate cost segment by segment
        # Segments are defined by the distances between consecutive waypoints along the route
        for i in range(len(waypoint_distances_along_route) - 1):
            segment_start_distance = waypoint_distances_along_route[i]
            segment_end_distance = waypoint_distances_along_route[i+1]
            segment_distance = segment_end_distance - segment_start_distance

            # Determine the fuel price for this segment
            if i == 0:
                # First segment (start to first stop or end)
                current_fuel_price_per_gallon = self.DEFAULT_PRICE_PER_GALLON
            else:
                # Segments between stops or last stop to end
                # The price is the price at the *start* of the segment (the previous stop)
                # Waypoint i (for i > 0) corresponds to optimal_stops[i-1]
                if i-1 < len(optimal_stops):
                    current_fuel_price_per_gallon = optimal_stops[i-1]['fuel_price_per_gallon']
                else:
                    # This case should ideally not happen if waypoint_distances_along_route
                    # is constructed correctly from start, stops, and end.
                    # If it does, it means we are in the segment after the last stop.
                    # The price should be the price at the last stop.
                    current_fuel_price_per_gallon = optimal_stops[-1]['fuel_price_per_gallon']


            fuel_needed_segment = segment_distance / self.FUEL_EFFICIENCY
            total_cost += fuel_needed_segment * current_fuel_price_per_gallon


        return total_cost