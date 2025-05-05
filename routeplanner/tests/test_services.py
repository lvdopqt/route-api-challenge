import unittest
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from requests.exceptions import RequestException, HTTPError, ConnectionError, Timeout
from django.conf import settings

from routeplanner.services.route_planner import RoutePlanner
from routeplanner.services.gas_station_enricher import GasStationEnricherService


# Mock Django settings for the API key
@override_settings(OPENROUTESERVICE_API_KEY="fake_api_key")
class RoutePlannerGetInitialRouteTests(TestCase):

    def setUp(self):
        """Set up a RoutePlanner instance for each test."""
        # Example coordinates (start and end)
        self.start_coords = [-74.0060, 40.7128]  # New York City
        self.end_coords = [-77.0369, 38.9072]    # Washington D.C.
        self.planner = RoutePlanner(self.start_coords, self.end_coords)


    @patch('requests.get') # Patch requests.get for this test method
    def test_get_initial_route_success(self, mock_get):
        """Test successful API call to _get_initial_route."""
        # Configure the mock requests.get to return a successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None # Simulate no HTTP errors
        # Simulate a successful OpenRouteService JSON response structure
        mock_response.json.return_value = {
            "features": [{
                "geometry": {"coordinates": [[-74.0, 40.7], [-75.0, 39.8], [-77.0, 38.9]]},
                "properties": {"summary": {"distance": 350000, "duration": 12600}} # Example distance in meters, duration in seconds
            }]
        }
        mock_get.return_value = mock_response

        # Call the method being tested
        coords, distance_m, duration_s = self.planner._get_initial_route(
            self.start_coords, self.end_coords
        )

        # Assert that requests.get was called with the correct URL and parameters
        expected_url = self.planner.ROUTE_SERVICE_BASE_URL
        expected_params = {
            'api_key': settings.OPENROUTESERVICE_API_KEY,
            'start': f"{self.start_coords[0]},{self.start_coords[1]}",
            'end': f"{self.end_coords[0]},{self.end_coords[1]}",
            'geometry': 'true',
            'details': 'distance,duration',
        }
        mock_get.assert_called_once_with(expected_url, params=expected_params)

        # Assert that the method returned the expected data
        self.assertEqual(coords, [[-74.0, 40.7], [-75.0, 39.8], [-77.0, 38.9]])
        self.assertEqual(distance_m, 350000)
        self.assertEqual(duration_s, 12600)



    @patch('requests.get')
    def test_get_initial_route_http_error(self, mock_get):
        """Test API call returning an HTTP error (e.g., 403, 404, 500)."""
        # Configure the mock requests.get to raise an HTTPError
        mock_response = MagicMock()
        mock_response.status_code = 403 # Example: Forbidden
        # Simulate raise_for_status() raising an HTTPError
        mock_response.raise_for_status.side_effect = HTTPError("Forbidden", response=mock_response)
        mock_get.return_value = mock_response

        # Assert that calling the method raises an Exception
        with self.assertRaisesRegex(Exception, 'Failed to get initial route from OpenRouteService'):
             self.planner._get_initial_route(self.start_coords, self.end_coords)

        # Assert that requests.get was called
        mock_get.assert_called_once()
        # Assert that raise_for_status was called
        mock_response.raise_for_status.assert_called_once()


    @patch('requests.get')
    def test_get_initial_route_request_exception(self, mock_get):
        """Test API call raising a requests.exceptions.RequestException (e.g., network error)."""
        # Configure the mock requests.get to raise a RequestException
        mock_get.side_effect = RequestException("Network is unreachable")

        # Assert that calling the method raises an Exception
        with self.assertRaisesRegex(Exception, 'Failed to get initial route from OpenRouteService'):
             self.planner._get_initial_route(self.start_coords, self.end_coords)

        # Assert that requests.get was called
        mock_get.assert_called_once()


    @patch('requests.get')
    def test_get_initial_route_empty_features(self, mock_get):
        """Test API call returning a response with no features."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "features": [] # Empty features list
        }
        mock_get.return_value = mock_response

        # Assert that calling the method raises an Exception due to missing features
        with self.assertRaisesRegex(Exception, 'No route features found in initial route response'):
             self.planner._get_initial_route(self.start_coords, self.end_coords)

        # Assert that requests.get was called
        mock_get.assert_called_once()


    @patch('requests.get')
    def test_get_initial_route_missing_geometry(self, mock_get):
        """Test API call returning a response missing geometry."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        # Simulate a response missing the geometry key
        mock_response.json.return_value = {
            "features": [{
                "properties": {"summary": {"distance": 350000, "duration": 12600}}
            }]
        }
        mock_get.return_value = mock_response

        # Assert that calling the method raises an Exception (e.g., KeyError)
        with self.assertRaises(Exception) as cm: # Catch generic Exception or specific KeyError
             self.planner._get_initial_route(self.start_coords, self.end_coords)

        # Check if the exception message indicates a processing error
        self.assertIn('Error processing OpenRouteService initial route response', str(cm.exception))


        # Assert that requests.get was called
        mock_get.assert_called_once()


    @patch('requests.get')
    def test_get_initial_route_missing_summary(self, mock_get):
        """Test API call returning a response missing summary."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        # Simulate a response missing the summary key
        mock_response.json.return_value = {
            "features": [{
                "geometry": {"coordinates": [[-74.0, 40.7], [-75.0, 39.8], [-77.0, 38.9]]},
            }]
        }
        mock_get.return_value = mock_response

        # Assert that calling the method raises an Exception (e.g., KeyError)
        with self.assertRaises(Exception) as cm: # Catch generic Exception or specific KeyError
             self.planner._get_initial_route(self.start_coords, self.end_coords)

        # Check if the exception message indicates a processing error
        self.assertIn('Error processing OpenRouteService initial route response', str(cm.exception))


        # Assert that requests.get was called
        mock_get.assert_called_once()

@override_settings(NOMINATIM_USER_AGENT="fake_test_user_agent")
class GasStationEnricherServiceTests(TestCase):

    def setUp(self):
        """Set up a service instance for each test."""
        self.service = GasStationEnricherService()
        # Define a test address
        self.test_address = "1600 Amphitheatre Parkway, Mountain View, CA"

    @patch('requests.get') # Patch requests.get for this test method
    def test_geocode_address_success(self, mock_get):
        """Test successful geocoding of an address."""
        # Configure the mock requests.get to return a successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None # Simulate no HTTP errors
        # Simulate a successful Nominatim JSON response structure as expected by the service
        mock_response.json.return_value = [
            {
                "lat": "37.4220", # Nominatim returns lat/lon as strings
                "lon": "-122.0840",
                "display_name": "Googleplex, Mountain View, CA, USA"
            }
        ]
        mock_get.return_value = mock_response

        # Call the method being tested
        coords = self.service.geocode_address(self.test_address)

        # Assert that requests.get was called with the correct URL, parameters, and headers
        expected_url = self.service.NOMINATIM_SEARCH_URL
        expected_params = {
            'q': self.test_address,
            'format': 'json',
            'limit': 1,
        }
        expected_headers = {
            'User-Agent': 'fake_test_user_agent' # Should use the overridden setting
        }
        mock_get.assert_called_once_with(
            expected_url,
            params=expected_params,
            headers=expected_headers,
            timeout=10 # Assert the timeout is passed
        )

        # Assert that the method returned the correct coordinates as floats
        self.assertEqual(coords, (37.4220, -122.0840))


    @patch('requests.get')
    def test_geocode_address_no_results(self, mock_get):
        """Test geocoding an address that returns no results."""
        # Configure the mock requests.get to return a response with no results
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = [] # Simulate an empty results list
        mock_get.return_value = mock_response

        # Call the method being tested
        coords = self.service.geocode_address(self.test_address)

        # Assert that requests.get was called
        mock_get.assert_called_once()

        # Assert that the method returned None
        self.assertIsNone(coords)


    @patch('requests.get')
    def test_geocode_address_http_error(self, mock_get):
        """Test API call returning an HTTP error (e.g., 403, 404, 500)."""
        # Configure the mock requests.get to raise an HTTPError
        mock_response = MagicMock()
        mock_response.status_code = 403 # Example: Forbidden
        # Simulate raise_for_status() raising an HTTPError
        mock_response.raise_for_status.side_effect = HTTPError("Forbidden", response=mock_response)
        mock_get.return_value = mock_response

        # Assert that calling the method re-raises a RequestException (as per the service's current implementation)
        with self.assertRaises(RequestException):
             self.service.geocode_address(self.test_address)

        # Assert that requests.get was called
        mock_get.assert_called_once()
        # Assert that raise_for_status was called (this is called internally before the exception is caught and re-raised)
        mock_response.raise_for_status.assert_called_once()


    @patch('requests.get')
    def test_geocode_address_request_exception(self, mock_get):
        """Test API call raising a requests.exceptions.RequestException (e.g., network error)."""
        # Configure the mock requests.get to raise a RequestException
        mock_get.side_effect = RequestException("Network is unreachable")

        # Assert that calling the method re-raises the RequestException
        with self.assertRaises(RequestException):
             self.service.geocode_address(self.test_address)

        # Assert that requests.get was called
        mock_get.assert_called_once()


    @patch('requests.get')
    def test_geocode_address_timeout(self, mock_get):
        """Test API call raising a requests.exceptions.Timeout."""
        # Configure the mock requests.get to raise a Timeout
        mock_get.side_effect = Timeout("Request timed out")

        # Assert that calling the method re-raises the Timeout exception
        with self.assertRaises(Timeout):
             self.service.geocode_address(self.test_address)

        # Assert that requests.get was called
        mock_get.assert_called_once()
