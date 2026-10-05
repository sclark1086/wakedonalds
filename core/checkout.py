from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from core.email_service import send_order_confirmation

TAX_RATE = Decimal("0.0725")


def calculate_tax(subtotal):
    subtotal = Decimal(str(subtotal))
    tax = subtotal * TAX_RATE

    return tax.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )


def calculate_total(subtotal):
    subtotal = Decimal(str(subtotal))
    tax = calculate_tax(subtotal)

    return (subtotal + tax).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )


def calculate_subtotal(cart_items):
    subtotal = Decimal("0.00")

    for item in cart_items:
        price = Decimal(str(item["price"]))
        quantity = int(item["quantity"])

        subtotal += price * quantity

    return subtotal.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )


def checkout_summary(subtotal):
    subtotal = Decimal(str(subtotal))
    tax = calculate_tax(subtotal)
    total = calculate_total(subtotal)

    return {
        "subtotal": subtotal,
        "tax": tax,
        "total": total
    }


def finalize_order(user_id, cart_items):

    if not cart_items:
        raise ValueError("Cannot finalize an empty cart.")

    subtotal = calculate_subtotal(cart_items)
    summary = checkout_summary(subtotal)

    order_items = []

    for item in cart_items:
        order_items.append({
            "item_number": item["item_number"],
            "quantity": int(item["quantity"]),
            "price": Decimal(str(item["price"]))
        })

    order = {
        "user_id": user_id,
        "subtotal": summary["subtotal"],
        "tax": summary["tax"],
        "total_price": summary["total"],
        "date": datetime.now(),
        "items": order_items
    }

    return order

def finalize_order_with_email(
    user_id,
    customer_email,
    cart_items,
    order_number
):
    order = finalize_order(user_id, cart_items)

    email_items = []

    for item in cart_items:
        email_items.append({
            "name": item.get(
                "name",
                f"Item {item['item_number']}"
            ),
            "quantity": int(item["quantity"]),
            "price": float(item["price"])
        })

    send_order_confirmation(
        customer_email=customer_email,
        order_number=order_number,
        items=email_items,
        total_price=float(order["total_price"])
    )

    return order