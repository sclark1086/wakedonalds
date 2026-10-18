"""
Signals for the orders app.

order_status_changed is sent after an order's status changes and the change
is saved to the database. It is also sent once when an order is created
(old_status is None then).

Example for SMS when an order is ready (3.4):

    from django.dispatch import receiver
    from orders.signals import order_status_changed

    @receiver(order_status_changed)
    def text_when_ready(sender, order, old_status, new_status, **kwargs):
        if new_status == "ready_for_pickup" and order.contact_phone:
            ...  # send the text
"""

from django.dispatch import Signal

# Sent with: order, old_status, new_status
order_status_changed = Signal()
