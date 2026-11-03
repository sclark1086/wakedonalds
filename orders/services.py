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



def calculate_totals(subtotal,fulfillment_type,store_settings,redemption_discount=Decimal("0.00"),):
    """Calculate checkout totals with optional reward discount."""
    subtotal = money(subtotal)
    redemption_discount = money(redemption_discount)

    if redemption_discount < 0:
        raise ValueError("Discount cannot be negative.")

    if redemption_discount > subtotal:
        raise ValueError("Discount cannot exceed subtotal.")

    fee = (
        delivery_fee_for(subtotal, store_settings)
        if fulfillment_type == Order.FulfillmentType.DELIVERY
        else Decimal("0.00")
    )

    discounted_subtotal = subtotal - redemption_discount

    tax = money(discounted_subtotal * store_settings.tax_rate)

    return {"subtotal": subtotal,"delivery_fee": fee,"tax": tax,"total_price": money(discounted_subtotal + fee + tax),}
