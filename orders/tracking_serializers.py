"""Receipt and tracking output for place order and 3.3 order tracking."""

from django.urls import reverse
from rest_framework import serializers

from .models import Order, OrderItem

STATUS_MESSAGES = {
    Order.Status.RECEIVED: "We've got your order.",
    Order.Status.IN_PROGRESS: "Your food is being made.",
    Order.Status.READY_FOR_PICKUP: "Your order is ready. Come pick it up!",
    Order.Status.COMPLETED: "Picked up. Enjoy your meal!",
    Order.Status.OUT_FOR_DELIVERY: "Your order is on its way.",
    Order.Status.DELIVERED: "Delivered. Enjoy your meal!",
}


class OrderItemSerializer(serializers.ModelSerializer):
    line_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ["name", "quantity", "unit_price", "line_total"]


class OrderTrackingSerializer(serializers.ModelSerializer):
    """
    Everything the tracking page shows. Contact phone and delivery address
    are left out on purpose, because anyone with the link can see this.
    """

    order_number = serializers.IntegerField(source="pk", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    status_message = serializers.SerializerMethodField()
    fulfillment_label = serializers.CharField(source="get_fulfillment_type_display", read_only=True)
    is_final = serializers.BooleanField(read_only=True)
    steps = serializers.SerializerMethodField()
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "order_number", "status", "status_label", "status_message",
            "fulfillment_type", "fulfillment_label", "is_final", "steps",
            "estimated_ready_at", "items", "subtotal", "delivery_fee", "tax",
            "total_price", "created_at", "updated_at",
        ]

    def get_status_message(self, order):
        return STATUS_MESSAGES.get(order.status, "")

    def get_steps(self, order):
        """The pickup or delivery steps, marking which are done and when."""
        flow = Order.STATUS_FLOW.get(order.fulfillment_type, [])
        reached = {}
        for event in order.status_events.all():  # oldest first
            reached[event.status] = event.created_at
        current = flow.index(order.status) if order.status in flow else -1
        as_text = serializers.DateTimeField().to_representation

        return [
            {
                "status": step,
                "label": Order.Status(step).label,
                "done": i <= current,
                "current": i == current,
                "reached_at": (
                    as_text(reached[step]) if i <= current and step in reached else None
                ),
            }
            for i, step in enumerate(flow)
        ]


class OrderReceiptSerializer(OrderTrackingSerializer):
    """Returned when an order is placed: the receipt plus the tracking link."""

    tracking_code = serializers.CharField(read_only=True)
    tracking_url = serializers.SerializerMethodField()

    class Meta(OrderTrackingSerializer.Meta):
        fields = OrderTrackingSerializer.Meta.fields + ["tracking_code", "tracking_url"]

    def get_tracking_url(self, order):
        path = reverse("order-tracking-page", args=[order.tracking_code])
        request = self.context.get("request")
        return request.build_absolute_uri(path) if request else path
