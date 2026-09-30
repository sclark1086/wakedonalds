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
