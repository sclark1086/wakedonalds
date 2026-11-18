"""
Inventory threshold settings (Sprint 4, feature 4.4; SRS CFD2, FR5, BR2).

Every menu item gets a minimum and maximum inventory level. When an item's
stock drops below its minimum, it is flagged as low inventory and the
admins get one alert. The flag clears once the item is restocked to its
minimum or above, so the next drop sends a fresh alert.

The SRS doesn't say what happens above the maximum, so the maximum is used
as the restock target: reorder quantity = maximum - current stock.

Thresholds live in their own table (one row per product) instead of new
columns on Product, so this feature doesn't collide with other Sprint 4/5
branches that change products/models.py.
"""

from django.core.exceptions import ValidationError
from django.db import models

DEFAULT_MIN_LEVEL = 5
DEFAULT_MAX_LEVEL = 50


class InventoryThreshold(models.Model):
    product = models.OneToOneField(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="inventory_threshold",
    )
    min_level = models.PositiveIntegerField(
        "minimum level",
        default=DEFAULT_MIN_LEVEL,
        help_text="Flag the item as low stock and alert admins when stock drops below this.",
    )
    max_level = models.PositiveIntegerField(
        "maximum level",
        default=DEFAULT_MAX_LEVEL,
        help_text="Restock target. Reorder quantity is this minus current stock.",
    )
    # Set by the system, not by admins: True from the moment stock drops
    # below the minimum until it is restocked. Prevents repeat alerts.
    low_stock_flag = models.BooleanField("flagged low", default=False, editable=False)
    flagged_at = models.DateTimeField(null=True, blank=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["product__name"]
        verbose_name = "inventory threshold"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(min_level__lte=models.F("max_level")),
                name="inventory_min_not_above_max",
            ),
        ]

    def __str__(self):
        return f"{self.product.name}: min {self.min_level}, max {self.max_level}"

    def clean(self):
        super().clean()
        if (
            self.min_level is not None
            and self.max_level is not None
            and self.min_level > self.max_level
        ):
            raise ValidationError(
                {"min_level": "Minimum level can't be higher than the maximum level."}
            )

    @property
    def current_stock(self):
        return self.product.stock

    @property
    def is_low(self):
        return self.product.stock < self.min_level

    @property
    def reorder_quantity(self):
        return max(self.max_level - self.product.stock, 0)

    @property
    def status(self):
        if self.product.stock == 0:
            return "Out of Stock"
        if self.is_low:
            return "Low Stock"
        return "In Stock"


class LowStockAlert(models.Model):
    """One row per alert sent, so admins can see when items ran low."""

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="low_stock_alerts",
    )
    stock_at_alert = models.PositiveIntegerField()
    min_level_at_alert = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    emailed_to = models.TextField(blank=True, help_text="Who the alert email went to.")
    resolved_at = models.DateTimeField(
        null=True, blank=True, help_text="When stock was back at or above the minimum."
    )

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"Low stock: {self.product.name} ({self.stock_at_alert} left)"
