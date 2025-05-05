from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from unittest.mock import patch, MagicMock
from routeplanner.services.route_planner import RoutePlanner
from routeplanner.serializers import RouteParametersSerializer


class RouteAPIViewTests(APITestCase):
    """Tests for the RouteAPIView."""

    def setUp(self):
        """Set up the API client and test data."""
        self.client = APIClient()
        self.url = reverse('route-plan') 

    # Patch both the Serializer and the RoutePlanner
    @patch('routeplanner.views.RouteParametersSerializer')
    @patch('routeplanner.views.RoutePlanner')
    def test_missing_parameters(self, MockRoutePlanner, MockRouteParametersSerializer):
        """Test the API returns 400 if start or end parameters are missing (handled by serializer)."""
        # Configure the mocked Serializer instance to be invalid due to missing fields
        mock_serializer_instance = MockRouteParametersSerializer.return_value
        mock_serializer_instance.is_valid.return_value = False
        # Define the mock errors dictionary for missing required fields as expected from the serializer
        mock_serializer_errors_missing_all = {
            'start': ['This field is required.'],
            'end': ['This field is required.']
        }
        mock_serializer_errors_missing_end = {
            'end': ['This field is required.']
        }
        mock_serializer_errors_missing_start = {
            'start': ['This field is required.']
        }


        # Test with no parameters
        mock_serializer_instance.errors = mock_serializer_errors_missing_all
        response = self.client.get(self.url)

        # Assert that the Serializer was initialized with the request query parameters
        # Use response.wsgi_request.GET to access query parameters in test client
        MockRouteParametersSerializer.assert_called_once_with(data=response.wsgi_request.GET)
        # Assert that is_valid was called on the serializer instance
        mock_serializer_instance.is_valid.assert_called_once()

        # Assert that RoutePlanner was NOT initialized or called
        MockRoutePlanner.assert_not_called()

        # Assert the response status code and data match the serializer errors for missing fields
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, mock_serializer_errors_missing_all)

        # Test with only start parameter - will result in serializer errors for missing 'end'
        MockRouteParametersSerializer.reset_mock() # Reset mock call counts for the next assertion
        mock_serializer_instance.is_valid.return_value = False
        mock_serializer_instance.errors = mock_serializer_errors_missing_end # Errors for missing 'end'
        # Provide valid format for start, but end is missing
        response = self.client.get(self.url, {'start': '40.7128,-74.0060'})
        MockRouteParametersSerializer.assert_called_once_with(data=response.wsgi_request.GET)
        mock_serializer_instance.is_valid.assert_called_once()
        MockRoutePlanner.assert_not_called()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, mock_serializer_errors_missing_end)


        # Test with only end parameter - will result in serializer errors for missing 'start'
        MockRouteParametersSerializer.reset_mock() # Reset mock call counts
        mock_serializer_instance.is_valid.return_value = False
        mock_serializer_instance.errors = mock_serializer_errors_missing_start # Errors for missing 'start'
        # Provide valid format for end, but start is missing
        response = self.client.get(self.url, {'end': '38.9072,-77.0369'})
        MockRouteParametersSerializer.assert_called_once_with(data=response.wsgi_request.GET)
        mock_serializer_instance.is_valid.assert_called_once()
        MockRoutePlanner.assert_not_called()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, mock_serializer_errors_missing_start)


    # Patch both the Serializer and the RoutePlanner
    @patch('routeplanner.views.RouteParametersSerializer')
    @patch('routeplanner.views.RoutePlanner')
    def test_successful_route_planning(self, MockRoutePlanner, MockRouteParametersSerializer):
        """Test the API returns a successful response with route data."""
        # Configure the mocked Serializer instance
        mock_serializer_instance = MockRouteParametersSerializer.return_value
        mock_serializer_instance.is_valid.return_value = True
        # Define the validated data that the serializer should return (as [lon, lat] lists)
        validated_start_coords = [-74.0060, 40.7128]
        validated_end_coords = [-77.0369, 38.9072]
        mock_serializer_instance.validated_data = {
            'start': validated_start_coords,
            'end': validated_end_coords
        }

        # Configure the mocked RoutePlanner instance and its plan method
        mock_planner_instance = MockRoutePlanner.return_value
        mock_plan_result = {
            'total_distance_miles': 500.5,
            'total_duration_seconds': 18000,
            'total_fuel_cost_usd': 50.25,
            'fuel_stops': [{'location': [40.0, -75.0], 'fuel_price_per_gallon': 3.00, 'distance_from_start_miles': 250.0}],
            'route_geometry': [[40.0, -74.0], [40.5, -74.5], [40.0, -75.0], [39.5, -75.5], [38.9, -77.0]]
        }
        mock_planner_instance.plan.return_value = mock_plan_result

        # Call the API with valid parameters in the expected string format (lat,lon)
        response = self.client.get(self.url, {'start': '40.7128,-74.0060', 'end': '38.9072,-77.0369'})

        # Assert that the Serializer was initialized with the request query parameters
        MockRouteParametersSerializer.assert_called_once_with(data=response.wsgi_request.GET)
        # Assert that is_valid was called on the serializer instance
        mock_serializer_instance.is_valid.assert_called_once()

        # Assert that RoutePlanner was initialized with the validated data from the serializer
        MockRoutePlanner.assert_called_once_with(validated_start_coords, validated_end_coords)
        # Assert that the plan method was called on the planner instance
        mock_planner_instance.plan.assert_called_once()

        # Assert the response status code and data
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, mock_plan_result)


    # Patch both the Serializer and the RoutePlanner
    @patch('routeplanner.views.RouteParametersSerializer')
    @patch('routeplanner.views.RoutePlanner')
    def test_route_planning_exception(self, MockRoutePlanner, MockRouteParametersSerializer):
        """Test the API handles exceptions raised by RoutePlanner."""
        # Configure the mocked Serializer instance
        mock_serializer_instance = MockRouteParametersSerializer.return_value
        mock_serializer_instance.is_valid.return_value = True
        # Define the validated data (still needed even if plan raises exception)
        validated_start_coords = [-74.0060, 40.7128]
        validated_end_coords = [-77.0369, 38.9072]
        mock_serializer_instance.validated_data = {
            'start': validated_start_coords,
            'end': validated_end_coords
        }

        # Configure the mocked RoutePlanner instance to raise an exception when plan() is called
        mock_planner_instance = MockRoutePlanner.return_value
        mock_exception_message = "Failed to calculate route"
        mock_planner_instance.plan.side_effect = Exception(mock_exception_message)

        # Call the API with valid parameters in the expected string format (lat,lon)
        response = self.client.get(self.url, {'start': '40.7128,-74.0060', 'end': '38.9072,-77.0369'})

        # Assert that the Serializer was initialized and validated
        # Use response.wsgi_request.GET to access query parameters in test client
        MockRouteParametersSerializer.assert_called_once_with(data=response.wsgi_request.GET)
        mock_serializer_instance.is_valid.assert_called_once()

        # Assert that RoutePlanner was initialized with the validated data
        MockRoutePlanner.assert_called_once_with(validated_start_coords, validated_end_coords)
        # Assert that the plan method was called on the planner instance
        mock_planner_instance.plan.assert_called_once()

        # Assert the response status code and error message
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data, {'error': mock_exception_message})

    # Add a new test case for invalid serializer data format
    @patch('routeplanner.views.RouteParametersSerializer')
    @patch('routeplanner.views.RoutePlanner') # Still patch RoutePlanner, though it shouldn't be called
    def test_invalid_serializer_data(self, MockRoutePlanner, MockRouteParametersSerializer):
        """Test the API returns 400 if serializer data is invalid (e.g., wrong format)."""
        # Configure the mocked Serializer instance to be invalid
        mock_serializer_instance = MockRouteParametersSerializer.return_value
        mock_serializer_instance.is_valid.return_value = False
        # Define the mock errors dictionary that the serializer should return for invalid format
        mock_serializer_errors = {
            'start': ['Invalid format for start. Expected "longitude,latitude".']
        }
        mock_serializer_instance.errors = mock_serializer_errors

        # Call the API with invalid parameters (e.g., wrong format for start)
        response = self.client.get(self.url, {'start': 'invalid-coords', 'end': '38.9072,-77.0369'})

        # Assert that the Serializer was initialized and validated
        # Use response.wsgi_request.GET to access query parameters in test client
        MockRouteParametersSerializer.assert_called_once_with(data=response.wsgi_request.GET)
        mock_serializer_instance.is_valid.assert_called_once()

        # Assert that RoutePlanner was NOT initialized or called
        MockRoutePlanner.assert_not_called()

        # Assert the response status code and data match the serializer errors
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, mock_serializer_errors)

