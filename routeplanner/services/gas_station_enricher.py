import time
import requests
from django.conf import settings
# Import specific requests exceptions for better error handling
from requests.exceptions import RequestException, Timeout, ConnectionError, HTTPError

class GasStationEnricherService:
    # Nominatim API endpoint for search
    NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search" # NOTE: NOMINATIM IS FREE BUT NOT GOOD AS GOOGLE MAPS NOT CLOSE

    def __init__(self):
        # User agent is required by Nominatim's usage policy
        self.user_agent = settings.NOMINATIM_USER_AGENT
        
        # Set headers, including the User-Agent
        self.headers = {
            'User-Agent': self.user_agent
        }


    def geocode_address(self, address):
        """
        Geocodes a single address using the Nominatim API via requests.

        Args:
            address: The address string to geocode.

        Returns:
            A tuple (latitude, longitude) if geocoding is successful, otherwise None.
        """
        # Parameters for the Nominatim search request
        params = {
            'q': address,
            'format': 'json', # Request JSON output
            'limit': 1,      # Request only the top result
        }

        # Retry logic will be handled by the caller (e.g., the management command)
        # This method will focus on making a single request and handling its immediate response.
        try:
            # Make the GET request to the Nominatim API
            # Use a timeout to prevent hanging indefinitely
            response = requests.get(
                self.NOMINATIM_SEARCH_URL,
                params=params,
                headers=self.headers,
                timeout=10
            )

            response.raise_for_status()

            data = response.json()

            if data and isinstance(data, list) and len(data) > 0:
                location = data[0]
                latitude = float(location.get('lat'))
                longitude = float(location.get('lon'))
                return (latitude, longitude)
            else:
                return None

        except Timeout:
            raise Timeout(f"Geocoding request timed out for address: {address}")
        except (ConnectionError, RequestException) as e:
            raise RequestException(f"Geocoding request error for address: {address}: {e}")
        except Exception as e:
            raise Exception(f"An unexpected error occurred during geocoding for address: {address}: {e}")

