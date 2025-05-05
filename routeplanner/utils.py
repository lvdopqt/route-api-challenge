import math
from math import radians, cos, sin, asin, sqrt
from django.db.models import F
from .models import GasStation

def haversine(coord1, coord2):
    """
    Calculate distance between two points on Earth (miles).
    coord1, coord2: (longitude, latitude).
    """
    lon1, lat1 = coord1
    lon2, lat2 = coord2
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    miles = 3956 * c
    return miles

def calculate_cumulative_distances(route_coords, total_route_distance_miles):
    """
    Calculates cumulative distance along route points.
    route_coords: List of [longitude, latitude] pairs.
    total_route_distance_miles: Total route distance in miles.
    Returns: List of cumulative distances.
    """
    cumulative_distances = [0]
    for i in range(1, len(route_coords)):
        dist_segment = haversine(route_coords[i-1], route_coords[i])
        cumulative_distances.append(cumulative_distances[-1] + dist_segment)

    if cumulative_distances and abs(cumulative_distances[-1] - total_route_distance_miles) > 1:
         cumulative_distances[-1] = total_route_distance_miles

    return cumulative_distances

def find_route_point_index_by_distance(cumulative_distances, target_distance, start_index=0):
    """
    Finds index of route point closest to a target distance from start.
    cumulative_distances: List of cumulative distances.
    target_distance: Distance from start.
    start_index: Index to start search from.
    Returns: Index of route point.
    """
    for j in range(start_index, len(cumulative_distances)):
         if cumulative_distances[j] >= target_distance:
             return j
    return len(cumulative_distances) - 1

def deduplicate_stops_by_location(stops_list):
    """
    Deduplicates a list of fuel stop dictionaries based on their 'location'.
    If multiple stops have the same location, the first one encountered is kept.

    Args:
        stops_list: A list of fuel stop dictionaries, potentially with duplicates.

    Returns:
        A new list with duplicate stops (based on location) removed.
    """
    seen_locations = set()
    deduplicated_stops = []
    for stop in stops_list:
        # Convert the location list [lat, lon] to a hashable tuple (lat, lon)
        location_tuple = tuple(stop['location'])
        if location_tuple not in seen_locations:
            deduplicated_stops.append(stop)
            seen_locations.add(location_tuple)
    return deduplicated_stops

def find_candidate_stations_near_segment(route_coords, cumulative_distances, segment_start_index, segment_end_index, proximity_threshold_miles, last_stop_distance_from_start):
    """
    Finds gas stations near a specific route segment.
    Returns: List of candidate station dictionaries.
    """
    candidate_stations = []
    all_gas_stations = GasStation.objects.filter(latitude__isnull=False, longitude__isnull=False)
    
    for station in all_gas_stations:
        station_coords = (float(station.longitude), float(station.latitude))

        is_near_route_segment = False
        for k in range(segment_start_index, segment_end_index + 1):
            route_point_coords = route_coords[k]
            dist_to_route_point = haversine(station_coords, route_point_coords)
            if dist_to_route_point < proximity_threshold_miles:
                is_near_route_segment = True
                break

        if is_near_route_segment:
            dist_station_from_start_straight_line = haversine(route_coords[0], station_coords)
            if dist_station_from_start_straight_line > last_stop_distance_from_start:
                candidate_stations.append({
                    'location': [float(station.latitude), float(station.longitude)],
                    'fuel_price_per_gallon': float(station.retail_price),
                    'distance_from_start_straight_line_miles': dist_station_from_start_straight_line,
                    'station_obj': station
                })
    return candidate_stations

def select_cheapest_stop(candidate_stations):
    """
    Selects the cheapest station from candidates.
    Returns: Dictionary for cheapest station, or None.
    """
    if candidate_stations:
        return min(candidate_stations, key=lambda x: x['fuel_price_per_gallon'])
    return None


def find_stops(route_coords, total_route_distance_miles, max_range_miles):
    """
    Finds optimal fuel stops along the route.
    Queries GasStation model.
    Returns: List of optimal fuel stop dictionaries.
    """
    optimal_stops = []
    last_stop_distance_from_start = 0

    cumulative_distances = calculate_cumulative_distances(route_coords, total_route_distance_miles)

    i = 0
    proximity_threshold_miles = 10

    while i < len(route_coords):
        current_distance_from_start = cumulative_distances[i]
        distance_since_last_stop = current_distance_from_start - last_stop_distance_from_start
        current_range = max_range_miles - distance_since_last_stop

        remaining_distance_total = total_route_distance_miles - current_distance_from_start

        target_distance_for_next_stop = last_stop_distance_from_start + max_range_miles

        next_stop_target_index = find_route_point_index_by_distance(cumulative_distances, target_distance_for_next_stop, start_index=i)

        distance_to_next_stop_target_point = cumulative_distances[next_stop_target_index] - current_distance_from_start

        if remaining_distance_total > current_range and distance_to_next_stop_target_point > current_range:

             look_ahead_distance = current_range

             look_ahead_index = find_route_point_index_by_distance(cumulative_distances, current_distance_from_start + look_ahead_distance, start_index=i)
             
             candidate_stations = find_candidate_stations_near_segment(
                 route_coords,
                 cumulative_distances,
                 i,
                 look_ahead_index,
                 proximity_threshold_miles,
                 last_stop_distance_from_start
             )

             cheapest_stop = select_cheapest_stop(candidate_stations)

             if cheapest_stop:
                 optimal_stops.append({
                     'location': cheapest_stop['location'],
                     'fuel_price_per_gallon': cheapest_stop['fuel_price_per_gallon'],
                     'distance_from_start_miles': current_distance_from_start
                 })

                 last_stop_distance_from_start = current_distance_from_start

        i += 1

    return deduplicate_stops_by_location(optimal_stops)
