from rest_framework import serializers
from rest_framework.exceptions import ValidationError

class RouteParametersSerializer(serializers.Serializer):
    """
    Serializer to validate and parse start and end coordinates from query parameters.
    Coordinates are expected as comma-separated longitude,latitude strings (e.g., "-74.0060,40.7128").
    """
    start = serializers.CharField(help_text="Start coordinates as 'longitude,latitude'")
    end = serializers.CharField(help_text="End coordinates as 'longitude,latitude'")

    def validate_start(self, value):
        """
        Validates and converts the start coordinate string.
        """
        return self._validate_coordinate(value, 'start')

    def validate_end(self, value):
        """
        Validates and converts the end coordinate string.
        """
        return self._validate_coordinate(value, 'end')

    def _validate_coordinate(self, value, field_name):
        """
        Helper method to validate and convert a single coordinate string.
        Expected format: "longitude,latitude" (both floats).
        """
        try:
            # Split the string by comma
            lon_str, lat_str = value.split(',')
            # Convert to floats
            longitude = float(lon_str)
            latitude = float(lat_str)

            # Optional: Add checks for valid coordinate ranges if needed
            # e.g., -180 <= longitude <= 180 and -90 <= latitude <= 90
            if not (-180 <= longitude <= 180):
                 raise ValidationError(f"Invalid longitude value for {field_name}.")
            if not (-90 <= latitude <= 90):
                 raise ValidationError(f"Invalid latitude value for {field_name}.")

            return [latitude, longitude]

        except ValueError:
            # Handle cases where splitting or float conversion fails
            raise ValidationError(f"Invalid format for {field_name}. Expected 'longitude,latitude'.")
        except Exception as e:
            # Catch any other unexpected errors during validation
            raise ValidationError(f"Error validating {field_name}: {e}")


