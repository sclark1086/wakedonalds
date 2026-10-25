from django.conf import settings
from django.core.mail import send_mail


def send_order_confirmation(customer_email, order_number, items, total_price):
    """
    Send an order confirmation email to the customer.
    """

    item_details = "\n".join(
        f"{item['name']} x{item['quantity']} - ${item['price']:.2f} each"
        for item in items
    )

    subject = f"Wakedonalds Order Confirmation #{order_number}"

    message = (
        "Thank you for ordering from Wakedonalds!\n\n"
        f"Order Number: {order_number}\n\n"
        "Your Items:\n"
        f"{item_details}\n\n"
        f"Total: ${total_price:.2f}\n\n"
        "We appreciate your order!"
    )

    return send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [customer_email],
        fail_silently=False,
    )
