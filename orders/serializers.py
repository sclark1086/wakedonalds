import re

from rest_framework import serializers

from .models import DeliveryZone, Order


def _digits(value):
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


class DeliveryAddressSerializer(serializers.Serializer):
    street = serializers.CharField(max_length=255)
    unit = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    city = serializers.CharField(max_length=100)
    state = serializers.RegexField(r"^[A-Za-z]{2}$", error_messages={"invalid": "Enter a 2-letter state code."})
    zip = serializers.RegexField(r"^\d{5}(-\d{4})?$", error_messages={"invalid": "Enter a 5-digit ZIP code."})
    instructions = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")

    def validate_state(self, value):
        return value.upper()

    def validate_zip(self, value):
        zip5 = value[:5]
        if not DeliveryZone.objects.filter(zip_code=zip5, active=True).exists():
            raise serializers.ValidationError(
                "We don't deliver to this ZIP code yet. Choose pickup instead."
            )
        return zip5


class FulfillmentSerializer(serializers.Serializer):
    """
    Validates the pickup/delivery part of a checkout.

    Needs context={"store_settings": FulfillmentSettings, "subtotal": Decimal}.
    Reuse it in the place-order view so the rules live in one place.
    """

    fulfillment_type = serializers.ChoiceField(
        choices=Order.FulfillmentType.choices,
        error_messages={"invalid_choice": "Choose pickup or delivery."},
    )
    contact_phone = serializers.CharField(required=False, allow_blank=True, default="")
    address = DeliveryAddressSerializer(required=False)

    def validate_contact_phone(self, value):
        digits = _digits(value)
        if digits and len(digits) != 10:
            raise serializers.ValidationError("Enter a 10-digit phone number.")
        return digits

    def validate(self, data):
        store = self.context["store_settings"]
        subtotal = self.context["subtotal"]
        kind = data["fulfillment_type"]
        errors = {}

        if kind == Order.FulfillmentType.PICKUP and not store.pickup_enabled:
            errors["fulfillment_type"] = "Pickup is not available right now."
        if kind == Order.FulfillmentType.DELIVERY:
            if not store.delivery_enabled:
                errors["fulfillment_type"] = "Delivery is not available right now."
            if not data.get("address"):
                errors["address"] = "Enter a delivery address."
            if not data.get("contact_phone"):
                errors["contact_phone"] = "Add a phone number so the driver can reach you."
            if subtotal < store.delivery_minimum_subtotal:
                errors["subtotal"] = (
                    f"Delivery orders need a subtotal of at least ${store.delivery_minimum_subtotal}."
                )
        else:
            data.pop("address", None)  # ignore an address sent with a pickup order

        if errors:
            raise serializers.ValidationError(errors)
        return data

    def to_order_fields(self):
        """Map validated data onto Order model fields."""
        d = self.validated_data
        a = d.get("address") or {}
        return {
            "fulfillment_type": d["fulfillment_type"],
            "contact_phone": d.get("contact_phone", ""),
            "delivery_street": a.get("street", ""),
            "delivery_unit": a.get("unit", ""),
            "delivery_city": a.get("city", ""),
            "delivery_state": a.get("state", ""),
            "delivery_zip": a.get("zip", ""),
            "delivery_instructions": a.get("instructions", ""),
        }


class QuoteRequestSerializer(FulfillmentSerializer):
    """Live price preview for the checkout page. The subtotal comes from the
    browser, so the real place-order view must recompute it from DB prices."""

    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)

    def validate(self, data):
        self.context["subtotal"] = data["subtotal"]
        return super().validate(data)


class OrderStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.Status.choices)
