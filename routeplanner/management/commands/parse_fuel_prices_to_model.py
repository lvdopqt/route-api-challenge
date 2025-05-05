import csv
import time
from django.core.management.base import BaseCommand
from django.db import transaction
from routeplanner.models import GasStation
from routeplanner.services.gas_station_enricher import GasStationEnricherService

class Command(BaseCommand):
    help = 'Import fuel prices from CSV file and geocode addresses using Nominatim service'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')

    def handle(self, *args, **kwargs):
        file_path = kwargs['csv_file']

        # Initialize the service
        self.enricher_service = GasStationEnricherService()

        self.stdout.write(self.style.SUCCESS(f'Starting import and geocoding from {file_path}'))

        self.processed_count = 0
        self.geocoded_count = 0
        self.failed_count = 0

        # Use a transaction to ensure data integrity
        try:
            with open(file_path, newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    self._process_row(row) # Call the new private method
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"Error: CSV file not found at {file_path}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An unexpected error occurred during file processing: {e}"))

        self.stdout.write(self.style.SUCCESS(f'Import process finished.'))
        self.stdout.write(self.style.SUCCESS(f'Successfully processed {self.processed_count} records.'))
        self.stdout.write(self.style.SUCCESS(f'Successfully geocoded {self.geocoded_count} addresses.'))
        self.stdout.write(self.style.WARNING(f'Failed to geocode or save {self.failed_count} records.'))


    def _process_row(self, row):
        """Processes a single row from the CSV, geocodes, and saves to the database."""
        full_address = self._construct_full_address(row)

        latitude = None
        longitude = None
        geocoding_successful = False

        if full_address:
            latitude, longitude, geocoding_successful = self._geocode_address_with_retries(full_address)

        self._save_gas_station_record(row, latitude, longitude, geocoding_successful)


    def _construct_full_address(self, row):
        """Constructs a full address string from a CSV row."""
        address_parts = [
            row.get('Address', '').strip(),
            row.get('City', '').strip(),
            row.get('State', '').strip(),
            'USA' # Assuming all addresses are in the USA
        ]
        return ", ".join(filter(None, address_parts))


    def _geocode_address_with_retries(self, full_address):
        """Attempts to geocode an address with retries and delays."""
        retries = 1 # retry disabled for tests
        for attempt in range(retries):
            try:
                coords = self.enricher_service.geocode_address(full_address)
                if coords:
                    self.stdout.write(self.style.SUCCESS(f'Geocoded "{full_address}"'))
                    return coords[0], coords[1], True # Return lat, lon, and success status
                else:
                    self.stdout.write(self.style.WARNING(f'Could not geocode address (attempt {attempt + 1}/{retries}): "{full_address}"'))
                    if attempt < retries - 1:
                         time.sleep(2) # Wait before retrying
                    else:
                         return None, None, False # Return None coords and failure status

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Unexpected error calling service for "{full_address}": {e}'))
                return None, None, False # Return None coords and failure status

        # Add a small delay between requests to respect Nominatim's usage policy
        # This delay is crucial even after retries for a single address
        time.sleep(1)
        return None, None, False # Should ideally not reach here if retries are exhausted


    def _save_gas_station_record(self, row, latitude, longitude, geocoding_successful):
        """Creates or updates a GasStation record."""
        try:
            # Use GasStation model
            GasStation.objects.update_or_create(
                opis_truckstop_id=row.get('OPIS Truckstop ID', '').strip(),
                defaults={
                    'truckstop_name': row.get('Truckstop Name', '').strip(),
                    'address': row.get('Address', '').strip(),
                    'city': row.get('City', '').strip(),
                    'state': row.get('State', '').strip(),
                    'rack_id': row.get('Rack ID', '').strip(),
                    'retail_price': float(row.get('Retail Price', 0.0)),
                    'latitude': latitude,
                    'longitude': longitude,
                }
            )
            self.processed_count += 1
            if not geocoding_successful:
                 self.stdout.write(self.style.ERROR(f'Failed to get the geolocation for OPIS ID {row.get("OPIS Truckstop ID", "")}'))

        except Exception as e:
             self.stdout.write(self.style.ERROR(f'Failed to save record for OPIS ID {row.get("OPIS Truckstop ID", "")}: {e}'))
             self.failed_count += 1 # Count as failed if saving fails

