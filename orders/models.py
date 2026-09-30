"""
Orders app — Sprint 2, feature 2.2 (pickup / delivery).

Covers SRS UC1 step 5 (choose delivery or pickup), FR2 (totals incl.
tax), FR4 / UC3 (order status tracking) and the admin configuration
pattern from CFD1-CFD3 (settings editable in Django admin, no redeploy).

Order follows the ORDERS table in the team's schema diagram
(order_num -> id, user_id, total_price, date -> created_at), extended
with the fulfillment fields this feature needs. ORDER_ITEM is left for
the checkout/place-order task because it depends on the Product model
on the cart branch, which isn't merged into main yet.
"""

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone


class FulfillmentSettings(models.Model):
    """Single-row store configuration, edited by admins in Django admin."""

    pickup_enabled = models.BooleanField(default=True)
    delivery_enabled = models.BooleanField(default=True)
    delivery_fee = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("3.99"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    free_delivery_minimum = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True, default=Decimal("30.00"),
        help_text="Subtotal at which delivery becomes free. Leave blank to never waive the fee.",
    )
    delivery_minimum_subtotal = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("10.00"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    tax_rate = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal("0.0725"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))],
        help_text="Sales tax as a decimal, e.g. 0.0725 for 7.25%.",
    )
    pickup_prep_minutes = models.PositiveSmallIntegerField(default=15)
    delivery_extra_minutes = models.PositiveSmallIntegerField(
        default=25, help_text="Added on top of prep time for delivery orders.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "fulfillment settings"
        verbose_name_plural = "fulfillment settings"

    def __str__(self):
        return "Pickup & delivery settings"

    def save(self, *args, **kwargs):
        self.pk = 1  # always a single row
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class DeliveryZone(models.Model):
    """ZIP codes the restaurant delivers to."""

    zip_code = models.CharField(max_length=5, unique=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["zip_code"]

    def __str__(self):
        return self.zip_code


class Order(models.Model):
    class FulfillmentType(models.TextChoices):
        PICKUP = "pickup", "Pickup"
        DELIVERY = "delivery", "Delivery"

    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        IN_PROGRESS = "in_progress", "In progress"
        READY_FOR_PICKUP = "ready_for_pickup", "Ready for pickup"
        COMPLETED = "completed", "Picked up"
        OUT_FOR_DELIVERY = "out_for_delivery", "Out for delivery"
        DELIVERED = "delivered", "Delivered"

    # Allowed order of statuses for each fulfillment type (UC3 tracking).
    STATUS_FLOW = {
        FulfillmentType.PICKUP: [
            Status.RECEIVED, Status.IN_PROGRESS, Status.READY_FOR_PICKUP, Status.COMPLETED,
        ],
        FulfillmentType.DELIVERY: [
            Status.RECEIVED, Status.IN_PROGRESS, Status.OUT_FOR_DELIVERY, Status.DELIVERED,
        ],
    }

    # Nullable so guests can order (UR2).
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="orders",
    )
    fulfillment_type = models.CharField(
        max_length=10, choices=FulfillmentType.choices, default=FulfillmentType.PICKUP,
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECEIVED)

    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    tax = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    contact_phone = models.CharField(max_length=10, blank=True)
    delivery_street = models.CharField(max_length=255, blank=True)
    delivery_unit = models.CharField(max_length=50, blank=True)
    delivery_city = models.CharField(max_length=100, blank=True)
    delivery_state = models.CharField(max_length=2, blank=True)
    delivery_zip = models.CharField(max_length=5, blank=True)
    delivery_instructions = models.CharField(max_length=255, blank=True)

    estimated_ready_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk} ({self.get_fulfillment_type_display()})"

    @property
    def order_num(self):
        return self.pk

    def next_status(self):
        flow = self.STATUS_FLOW[self.fulfillment_type]
        i = flow.index(self.status)
        return flow[i + 1] if i + 1 < len(flow) else None

    def can_transition_to(self, new_status):
        return new_status is not None and new_status == self.next_status()

    @staticmethod
    def estimate_ready_at(fulfillment_type, store_settings, now=None):
        now = now or timezone.now()
        minutes = store_settings.pickup_prep_minutes
        if fulfillment_type == Order.FulfillmentType.DELIVERY:
            minutes += store_settings.delivery_extra_minutes
        return now + timedelta(minutes=minutes)
