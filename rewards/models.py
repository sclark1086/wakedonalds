from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class RewardsSettings(models.Model):
    """Single-row program configuration, edited by admins in Django admin."""

    program_enabled = models.BooleanField(
        default=True,
        help_text="Turn off to stop customers earning or redeeming points.",
    )
    points_per_dollar = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Points earned for each $1 spent. Partial points are dropped.",
    )
    point_value = models.DecimalField(
        max_digits=6, decimal_places=4, default=Decimal("0.0100"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Dollar value of one point when redeemed, e.g. 0.01 means 100 points = $1.00.",
    )
    minimum_redemption_points = models.PositiveIntegerField(
        default=100,
        help_text="Customers need at least this many points before they can redeem.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "rewards settings"
        verbose_name_plural = "rewards settings"

    def __str__(self):
        return "Rewards program settings"

    def save(self, *args, **kwargs):
        self.pk = 1  # always a single row
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class RewardOption(models.Model):
    """Something customers can spend points on: a free menu item or a discount."""

    class Kind(models.TextChoices):
        FREE_ITEM = "free_item", "Free menu item"
        DISCOUNT = "discount", "Dollar-off discount"

    name = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.FREE_ITEM)
    product = models.ForeignKey(
        "products.Product", on_delete=models.PROTECT, null=True, blank=True,
        related_name="reward_options",
        help_text="The menu item given for free. Only for free item rewards.",
    )
    discount_amount = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Dollars taken off the order. Only for discount rewards.",
    )
    points_cost = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    active = models.BooleanField(default=True, help_text="Uncheck to hide this reward from customers.")
    sort_order = models.PositiveSmallIntegerField(default=0, help_text="Lower numbers show first.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "points_cost", "name"]

    def __str__(self):
        return f"{self.name} ({self.points_cost} pts)"

    def clean(self):
        errors = {}
        if self.kind == self.Kind.FREE_ITEM:
            if self.product_id is None:
                errors["product"] = "Choose the menu item this reward gives away."
            if self.discount_amount is not None:
                errors["discount_amount"] = "Leave blank for free item rewards."
        elif self.kind == self.Kind.DISCOUNT:
            if self.discount_amount is None:
                errors["discount_amount"] = "Enter how many dollars this reward takes off."
            if self.product_id is not None:
                errors["product"] = "Leave blank for discount rewards."
        if errors:
            raise ValidationError(errors)

    @property
    def is_available(self):
        """False when a free item reward's product is out of stock."""
        if self.kind == self.Kind.FREE_ITEM and self.product is not None:
            return self.product.stock > 0
        return True
