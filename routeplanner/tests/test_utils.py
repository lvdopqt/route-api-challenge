import unittest
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.db.models import F
from django.conf import settings 

from routeplanner.utils import (
    haversine,
    calculate_cumulative_distances,
    find_route_point_index_by_distance,
    find_candidate_stations_near_segment,
    select_cheapest_stop,
    find_stops
)
from routeplanner.models import GasStation 


class HaversineTests(unittest.TestCase):
    """Tests for the haversine distance calculation function."""

    def test_haversine_same_point(self):
        """Test distance between the same point is zero."""
        coord1 = (-74.0060, 40.7128) # New York City
        coord2 = (-74.0060, 40.7128)
        distance = haversine(coord1, coord2)
        self.assertAlmostEqual(distance, 0.0, places=5)

    def test_haversine_known_distance(self):
        """Test distance between two points with a known approximate distance."""
        # Distance between NYC and Washington D.C. is approx 204 miles
        coord1 = (-74.0060, 40.7128) # New York City
        coord2 = (-77.0369, 38.9072) # Washington D.C.
        distance = haversine(coord1, coord2)
        self.assertAlmostEqual(distance, 204.0, delta=5.0) # Allow a delta for approximation

    def test_haversine_antipodal_points(self):
        """Test distance between antipodal points (should be half circumference)."""
        coord1 = (0, 0) # Equator, Prime Meridian
        coord2 = (180, 0) # Equator, 180th Meridian
        # Earth circumference approx 24856 miles, half is 12428
        distance = haversine(coord1, coord2)
        self.assertAlmostEqual(distance, 12428.0, delta=50.0)


class CalculateCumulativeDistancesTests(unittest.TestCase):
    """Tests for calculating cumulative distances along a route."""

    def test_calculate_cumulative_distances_simple(self):
        """Test cumulative distances for a simple straight route."""
        route_coords = [
            (-74.0, 40.0),
            (-74.1, 40.1),
            (-74.2, 40.2),
        ]
        # Approximate distance between consecutive points (adjust as needed based on haversine)
        dist_segment1 = haversine(route_coords[0], route_coords[1])
        dist_segment2 = haversine(route_coords[1], route_coords[2])
        total_distance = dist_segment1 + dist_segment2

        cumulative = calculate_cumulative_distances(route_coords, total_distance)

        self.assertEqual(len(cumulative), len(route_coords))
        self.assertAlmostEqual(cumulative[0], 0.0, places=5)
        self.assertAlmostEqual(cumulative[1], dist_segment1, places=5)
        self.assertAlmostEqual(cumulative[2], total_distance, places=5)

    def test_calculate_cumulative_distances_empty_route(self):
        """Test with an empty route."""
        route_coords = []
        total_distance = 0
        cumulative = calculate_cumulative_distances(route_coords, total_distance)
        self.assertEqual(cumulative, [0]) # Should return [0] for an empty route

    def test_calculate_cumulative_distances_single_point(self):
        """Test with a route of a single point."""
        route_coords = [(-74.0, 40.0)]
        total_distance = 0
        cumulative = calculate_cumulative_distances(route_coords, total_distance)
        self.assertEqual(cumulative, [0])


class FindRoutePointIndexByDistanceTests(unittest.TestCase):
    """Tests for finding route point index by distance."""

    def test_find_index_exact_distance(self):
        """Test finding index for an exact cumulative distance."""
        cumulative_distances = [0, 10, 25, 40, 60]
        target_distance = 25
        index = find_route_point_index_by_distance(cumulative_distances, target_distance)
        self.assertEqual(index, 2)

    def test_find_index_between_points(self):
        """Test finding index for a distance between cumulative points."""
        cumulative_distances = [0, 10, 25, 40, 60]
        target_distance = 30 # Between 25 and 40
        index = find_route_point_index_by_distance(cumulative_distances, target_distance)
        self.assertEqual(index, 3) # Should return the index of the point >= target distance

    def test_find_index_beyond_end(self):
        """Test finding index for a distance beyond the total route distance."""
        cumulative_distances = [0, 10, 25, 40, 60]
        total_distance = 60
        target_distance = 70
        index = find_route_point_index_by_distance(cumulative_distances, target_distance)
        self.assertEqual(index, len(cumulative_distances) - 1) # Should return the last index

    def test_find_index_at_start(self):
        """Test finding index for a distance of zero."""
        cumulative_distances = [0, 10, 25, 40, 60]
        target_distance = 0
        index = find_route_point_index_by_distance(cumulative_distances, target_distance)
        self.assertEqual(index, 0)

    def test_find_index_with_start_index(self):
        """Test finding index starting search from a specific index."""
        cumulative_distances = [0, 10, 25, 40, 60]
        target_distance = 40
        start_index = 2 # Start search from index 2 (cumulative distance 25)
        index = find_route_point_index_by_distance(cumulative_distances, target_distance, start_index=start_index)
        self.assertEqual(index, 3)


class SelectCheapestStopTests(unittest.TestCase):
    """Tests for selecting the cheapest fuel stop from a list."""

    def test_select_cheapest_stop_basic(self):
        """Test selecting the cheapest stop from a list of candidates."""
        candidate_stations = [
            {'fuel_price_per_gallon': 3.50, 'location': [1, 1]},
            {'fuel_price_per_gallon': 3.25, 'location': [2, 2]},
            {'fuel_price_per_gallon': 3.75, 'location': [3, 3]},
        ]
        cheapest = select_cheapest_stop(candidate_stations)
        self.assertEqual(cheapest['fuel_price_per_gallon'], 3.25)

    def test_select_cheapest_stop_empty_list(self):
        """Test with an empty list of candidates."""
        candidate_stations = []
        cheapest = select_cheapest_stop(candidate_stations)
        self.assertIsNone(cheapest)

    def test_select_cheapest_stop_single_candidate(self):
        """Test with a single candidate."""
        candidate_stations = [{'fuel_price_per_gallon': 3.10, 'location': [4, 4]}]
        cheapest = select_cheapest_stop(candidate_stations)
        self.assertEqual(cheapest['fuel_price_per_gallon'], 3.10)


# Patch haversine for simplicity in this test class
@patch('routeplanner.utils.haversine', side_effect=lambda c1, c2: 10)
class FindCandidateStationsNearSegmentTests(TestCase):
    """
    Tests for finding candidate gas stations near a route segment.
    Requires a database and GasStation model.
    """

    def setUp(self):
        """Create some dummy GasStation instances for testing."""
        # Create stations with and without coordinates
        self.station1 = GasStation.objects.create(
            opis_truckstop_id='1', truckstop_name='Station 1', address='Addr 1',
            city='City 1', state='S1', rack_id='R1', retail_price=3.00,
            latitude=40.0, longitude=-74.0
        )
        self.station2 = GasStation.objects.create(
            opis_truckstop_id='2', truckstop_name='Station 2', address='Addr 2',
            city='City 2', state='S2', rack_id='R2', retail_price=3.10,
            latitude=40.1, longitude=-74.1
        )
        self.station3 = GasStation.objects.create(
            opis_truckstop_id='3', truckstop_name='Station 3', address='Addr 3',
            city='City 3', state='S3', rack_id='R3', retail_price=3.20,
            latitude=None, longitude=None # Station without coordinates
        )
        self.station4 = GasStation.objects.create(
             opis_truckstop_id='4', truckstop_name='Station 4', address='Addr 4',
             city='City 4', state='S4', rack_id='R4', retail_price=2.90,
             latitude=40.5, longitude=-74.5 # Station potentially far from the route segment
        )

        # Define a dummy route segment and parameters
        self.route_coords = [(-74.0, 40.0), (-74.1, 40.1), (-74.2, 40.2), (-74.3, 40.3)]
        self.cumulative_distances = [0, 10, 20, 30] # Dummy cumulative distances
        self.segment_start_index = 1 # Segment from index 1 to 2
        self.segment_end_index = 2
        self.proximity_threshold_miles = 15 # Threshold for being near the route point
        self.last_stop_distance_from_start = 5 # Assume last stop was at distance 5

    def test_find_candidate_stations_near_segment_found(self, mock_haversine):
        """Test finding stations near the segment."""
        # Configure mock_haversine's side_effect to control distances returned
        # haversine is called between station_coords and route_point_coords[k] for proximity
        # and between station_coords and route_coords[0] for the "ahead" check.
        def mock_haversine_side_effect(coord1, coord2):
            # Simulate proximity check: return 10 (within threshold 15) for station1/2, 30 (above threshold) for station4
            if coord2 in self.route_coords[self.segment_start_index : self.segment_end_index + 1]:
                 if coord1 in [(float(self.station1.longitude), float(self.station1.latitude)),
                               (float(self.station2.longitude), float(self.station2.latitude))]:
                     return 10
                 if coord1 == (float(self.station4.longitude), float(self.station4.latitude)):
                      return 30
            # Simulate "ahead" check from route_coords[0]: return > last_stop_distance_from_start (5) for station1/2, < 5 for station4
            if coord2 == self.route_coords[0]:
                 if coord1 == (float(self.station1.longitude), float(self.station1.latitude)):
                     return 8 # Ahead
                 if coord1 == (float(self.station2.longitude), float(self.station2.latitude)):
                     return 12 # Ahead
                 if coord1 == (float(self.station4.longitude), float(self.station4.latitude)):
                      return 4 # Not ahead
            return 10 # Default for other haversine calls if any

        mock_haversine.side_effect = mock_haversine_side_effect


        candidates = find_candidate_stations_near_segment(
            self.route_coords, self.cumulative_distances,
            self.segment_start_index, self.segment_end_index,
            self.proximity_threshold_miles, self.last_stop_distance_from_start
        )

        # Expect station1 and station2 to be found as candidates (near segment and ahead of last stop)
        self.assertEqual(len(candidates), 2)
        candidate_opis_ids = {c['station_obj'].opis_truckstop_id for c in candidates}
        self.assertIn(self.station1.opis_truckstop_id, candidate_opis_ids)
        self.assertIn(self.station2.opis_truckstop_id, candidate_opis_ids)
        self.assertNotIn(self.station3.opis_truckstop_id, candidate_opis_ids) # No coordinates
        self.assertNotIn(self.station4.opis_truckstop_id, candidate_opis_ids) # Not ahead of last stop


    def test_find_candidate_stations_near_segment_none_found(self, mock_haversine):
        """Test finding no stations near the segment."""
        # Configure mock_haversine so no stations are near the segment or ahead of last stop
        mock_haversine.side_effect = lambda c1, c2: 30 # Always return a distance > proximity_threshold

        candidates = find_candidate_stations_near_segment(
            self.route_coords, self.cumulative_distances,
            self.segment_start_index, self.segment_end_index,
            self.proximity_threshold_miles, self.last_stop_distance_from_start
        )

        # Expect no candidates to be found
        self.assertEqual(len(candidates), 0)

    def test_find_candidate_stations_near_segment_no_stations_in_db(self, mock_haversine):
        """Test with no stations in the database."""
        GasStation.objects.all().delete() # Delete all stations

        candidates = find_candidate_stations_near_segment(
            self.route_coords, self.cumulative_distances,
            self.segment_start_index, self.segment_end_index,
            self.proximity_threshold_miles, self.last_stop_distance_from_start
        )

        # Expect no candidates to be found
        self.assertEqual(len(candidates), 0)


# Patch dependencies for find_stops
@patch('routeplanner.utils.find_candidate_stations_near_segment')
@patch('routeplanner.utils.calculate_cumulative_distances')
@patch('routeplanner.utils.find_route_point_index_by_distance') # Patch this as well
class FindStopsTests(TestCase):
    """Tests for the main find_stops function."""

    def test_find_stops_no_stops_needed(self, mock_find_route_point_index_by_distance, mock_calculate_cumulative_distances, mock_find_candidate_stations_near_segment):
        """Test a short route where no stops are needed within max range."""
        route_coords = [(-74.0, 40.0), (-73.0, 41.0)] # Short route
        total_route_distance_miles = 400 # Less than max range
        max_range_miles = 500

        # Mock cumulative distances to be less than max range
        mock_calculate_cumulative_distances.return_value = [0, 400]
        # Mock find_route_point_index_by_distance to return the end index when looking ahead
        mock_find_route_point_index_by_distance.return_value = len(route_coords) - 1


        # Configure mock_find_candidate_stations_near_segment to return empty list always
        mock_find_candidate_stations_near_segment.return_value = []

        optimal_stops = find_stops(route_coords, total_route_distance_miles, max_range_miles)

        # Expect no optimal stops
        self.assertEqual(len(optimal_stops), 0)
        # In this scenario, the loop condition to trigger stop search should not be met,
        # so find_candidate_stations_near_segment should NOT be called.
        mock_find_candidate_stations_near_segment.assert_not_called()


    def test_find_stops_with_stops_found(self, mock_find_route_point_index_by_distance, mock_calculate_cumulative_distances, mock_find_candidate_stations_near_segment):
        """Test a route where stops are needed and candidates are found."""
        route_coords = [(-74.0, 40.0), (-75.0, 41.0), (-76.0, 42.0), (-77.0, 43.0), (-78.0, 44.0)] # Longer route
        total_route_distance_miles = 1000 # More than max range
        max_range_miles = 200 # Smaller range to force stops

        # Mock cumulative distances to simulate segments where stops are needed
        cumulative_dists = [0, 150, 300, 450, 600, 750, 900, 1000]
        mock_calculate_cumulative_distances.return_value = cumulative_dists

        # Mock find_route_point_index_by_distance to return appropriate indices
        def mock_find_route_point_index_side_effect(cumulative_distances, target_distance, start_index=0):
            for j in range(start_index, len(cumulative_distances)):
                 if cumulative_distances[j] >= target_distance:
                     return j
            return len(cumulative_distances) - 1

        mock_find_route_point_index_by_distance.side_effect = mock_find_route_point_index_side_effect


        # Configure mock_find_candidate_stations_near_segment to return candidates at specific points
        # Corrected side_effect function signature to accept positional arguments
        def find_candidates_side_effect(route_coords, cumulative_distances, segment_start_index, segment_end_index, proximity_threshold_miles, last_stop_distance_from_start):
            # Simulate finding a cheap station when the segment starts around distances where stops are needed
            current_dist = cumulative_distances[segment_start_index]

            # Based on trace, stops are needed when segment_start_index (i) is 0 and 2.
            if segment_start_index == 0: # First segment
                 return [{
                     'location': [40.5, -74.5],
                     'fuel_price_per_gallon': 3.05,
                     'distance_from_start_straight_line_miles': current_dist + 155, # Dummy ahead distance relative to current_dist
                     'station_obj': MagicMock()
                 }]
            elif segment_start_index == 2: # Segment starting around cumulative dist 300
                 return [{
                     'location': [41.5, -75.5],
                     'fuel_price_per_gallon': 3.15,
                     'distance_from_start_straight_line_miles': current_dist + 155, # Dummy ahead distance relative to current_dist
                     'station_obj': MagicMock()
                 }]
            return [] # No candidates found otherwise

        mock_find_candidate_stations_near_segment.side_effect = find_candidates_side_effect


        optimal_stops = find_stops(route_coords, total_route_distance_miles, max_range_miles)

        # Expect two optimal stops to be found based on the side effect logic
        self.assertEqual(len(optimal_stops), 2)
        # You could add more specific assertions about the stops found based on the side effect logic


    def test_find_stops_no_candidates_found_when_needed(self, mock_find_route_point_index_by_distance, mock_calculate_cumulative_distances, mock_find_candidate_stations_near_segment):
        """Test a route where stops are needed but no candidates are found."""
        route_coords = [(-74.0, 40.0), (-75.0, 41.0), (-76.0, 42.0), (-77.0, 43.0)]
        total_route_distance_miles = 400
        max_range_miles = 100 # Force stops

        # Mock cumulative distances
        cumulative_dists = [0, 100, 200, 300, 400]
        mock_calculate_cumulative_distances.return_value = cumulative_dists

        # Mock find_route_point_index_by_distance
        def mock_find_route_point_index_side_effect(cumulative_distances, target_distance, start_index=0):
            for j in range(start_index, len(cumulative_distances)):
                 if cumulative_distances[j] >= target_distance:
                     return j
            return len(cumulative_distances) - 1
        mock_find_route_point_index_by_distance.side_effect = mock_find_route_point_index_side_effect


        # Configure mock_find_candidate_stations_near_segment to always return an empty list
        # Corrected side_effect function signature to accept positional arguments
        def find_candidates_side_effect(route_coords, cumulative_distances, segment_start_index, segment_end_index, proximity_threshold_miles, last_stop_distance_from_start):
             return [] # Always return empty list

        mock_find_candidate_stations_near_segment.side_effect = find_candidates_side_effect


        optimal_stops = find_stops(route_coords, total_route_distance_miles, max_range_miles)

        # Expect no optimal stops to be found
        self.assertEqual(len(optimal_stops), 0)
        # Ensure find_candidate_stations_near_segment was called multiple times as stops were needed
        # Based on trace, stop search is triggered when segment_start_index (i) is 2 and 3.
        # So find_candidate_stations_near_segment should be called twice.
        self.assertEqual(mock_find_candidate_stations_near_segment.call_count, 2) # Corrected assertion


    # Add more tests for edge cases in find_stops, e.g.,
    # - Route distance exactly equals max range
    # - Stops found exactly at max range points
    # - Stops found very close to each other
    # - Route with very few points
    # - Route with many points

