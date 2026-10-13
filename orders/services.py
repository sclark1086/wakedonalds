"""Money math for pickup/delivery. Decimal only, never float."""

from decimal import Decimal, ROUND_HALF_UP

from .models import Order

CENT = Decimal("0.01")


def money(value):
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def delivery_fee_for(subtotal, store_settings):
    threshold = store_settings.free_delivery_minimum
    if threshold is not None and subtotal >= threshold:
        return Decimal("0.00")
    return money(store_settings.delivery_fee)


def calculate_totals(subtotal, fulfillment_type, store_settings):
    """FR2 totals. Tax applies to food only; confirm with the team whether
    the delivery fee should be taxed too."""
    subtotal = money(subtotal)
    fee = (
        delivery_fee_for(subtotal, store_settings)
        if fulfillment_type == Order.FulfillmentType.DELIVERY
        else Decimal("0.00")
    )
    tax = money(subtotal * store_settings.tax_rate)
    return {
        "subtotal": subtotal,
        "delivery_fee": fee,
        "tax": tax,
        "total_price": subtotal + fee + tax,
    }
