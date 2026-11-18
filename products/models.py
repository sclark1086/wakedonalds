
from django.db import models


class Product(models.Model):

    CATEGORY_CHOICES = [
        ("burgers", "Burgers"),
        ("sides", "Sides"),
        ("drinks", "Drinks"),
        ("desserts", "Desserts"),
        ("combos", "Combos"),
    ]

    name = models.CharField(max_length=100)

    description = models.TextField(blank=True)

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default="burgers"
    )

    ingredients = models.TextField(blank=True)

    stock = models.PositiveIntegerField(default=0)

    is_available = models.BooleanField(default=True)

    def __str__(self):
        return self.name
