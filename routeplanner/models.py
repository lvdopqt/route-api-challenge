from django.db import models

class GasStation(models.Model):
    opis_truckstop_id = models.CharField(max_length=100)
    truckstop_name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)
    rack_id = models.CharField(max_length=100)
    retail_price = models.DecimalField(max_digits=6, decimal_places=2)

    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    def __str__(self):
        return f"{self.truckstop_name} - {self.city}, {self.state}"

