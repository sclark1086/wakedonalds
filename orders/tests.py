from datetime import datetime, timezone as dt_tz
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import DeliveryZone, FulfillmentSettings, Order
from .serializers import FulfillmentSerializer
from .services import calculate_totals

GOOD_ADDRESS = {"street": "1 Main St", "city": "Springfield", "state": "nc", "zip": "12345"}


class TotalsTests(TestCase):
    def setUp(self):
        self.store = FulfillmentSettings.load()  # defaults: $3.99 fee, free at $30, 7.25% tax

    def test_pickup_has_no_fee(self):
        t = calculate_totals(Decimal("10.00"), "pickup", self.store)
        self.assertEqual(t["delivery_fee"], Decimal("0.00"))
        self.assertEqual(t["tax"], Decimal("0.73"))
        self.assertEqual(t["total_price"], Decimal("10.73"))

    def test_delivery_adds_fee_below_threshold(self):
        t = calculate_totals(Decimal("20.00"), "delivery", self.store)
        self.assertEqual(t["delivery_fee"], Decimal("3.99"))
        self.assertEqual(t["total_price"], Decimal("25.44"))

    def test_delivery_free_at_threshold(self):
        t = calculate_totals(Decimal("30.00"), "delivery", self.store)
        self.assertEqual(t["delivery_fee"], Decimal("0.00"))

    def test_blank_threshold_never_free(self):
        self.store.free_delivery_minimum = None
        t = calculate_totals(Decimal("500.00"), "delivery", self.store)
        self.assertEqual(t["delivery_fee"], Decimal("3.99"))


class FulfillmentSerializerTests(TestCase):
    def setUp(self):
        self.store = FulfillmentSettings.load()
        DeliveryZone.objects.create(zip_code="12345")

    def check(self, data, subtotal="20.00"):
        s = FulfillmentSerializer(data=data, context={"store_settings": self.store, "subtotal": Decimal(subtotal)})
        return s, s.is_valid()

    def test_pickup_without_phone_is_valid(self):
        s, ok = self.check({"fulfillment_type": "pickup"}, subtotal="5.00")
        self.assertTrue(ok, s.errors)

    def test_pickup_ignores_address(self):
        s, ok = self.check({"fulfillment_type": "pickup", "address": GOOD_ADDRESS})
        self.assertTrue(ok, s.errors)
        self.assertEqual(s.to_order_fields()["delivery_street"], "")

    def test_unknown_type_rejected(self):
        s, ok = self.check({"fulfillment_type": "drone"})
        self.assertFalse(ok)
        self.assertIn("fulfillment_type", s.errors)

    def test_valid_delivery_normalizes_phone_and_state(self):
        s, ok = self.check({"fulfillment_type": "delivery", "contact_phone": "(919) 555-0100", "address": GOOD_ADDRESS})
        self.assertTrue(ok, s.errors)
        fields = s.to_order_fields()
        self.assertEqual(fields["contact_phone"], "9195550100")
        self.assertEqual(fields["delivery_state"], "NC")

    def test_zip_outside_delivery_area(self):
        s, ok = self.check({"fulfillment_type": "delivery", "contact_phone": "9195550100",
                            "address": {**GOOD_ADDRESS, "zip": "99999"}})
        self.assertFalse(ok)
        self.assertIn("zip", s.errors["address"])

    def test_inactive_zone_rejected(self):
        DeliveryZone.objects.filter(zip_code="12345").update(active=False)
        s, ok = self.check({"fulfillment_type": "delivery", "contact_phone": "9195550100", "address": GOOD_ADDRESS})
        self.assertFalse(ok)

    def test_delivery_needs_address_phone_and_minimum(self):
        s, ok = self.check({"fulfillment_type": "delivery"}, subtotal="5.00")
        self.assertFalse(ok)
        self.assertEqual(set(s.errors), {"address", "contact_phone", "subtotal"})

    def test_delivery_disabled_by_admin(self):
        self.store.delivery_enabled = False
        s, ok = self.check({"fulfillment_type": "delivery", "contact_phone": "9195550100", "address": GOOD_ADDRESS})
        self.assertFalse(ok)
        self.assertIn("fulfillment_type", s.errors)


class OrderModelTests(TestCase):
    def make(self, kind, status="received"):
        return Order.objects.create(fulfillment_type=kind, status=status, subtotal=10, tax=1, total_price=11)

    def test_pickup_flow(self):
        o = self.make("pickup", "in_progress")
        self.assertTrue(o.can_transition_to("ready_for_pickup"))
        self.assertFalse(o.can_transition_to("out_for_delivery"))

    def test_delivery_flow(self):
        o = self.make("delivery", "in_progress")
        self.assertTrue(o.can_transition_to("out_for_delivery"))
        self.assertFalse(o.can_transition_to("delivered"))  # can't skip a step

    def test_last_status_has_no_next(self):
        self.assertIsNone(self.make("delivery", "delivered").next_status())

    def test_ready_estimate(self):
        store = FulfillmentSettings.load()
        now = datetime(2026, 4, 1, 12, 0, tzinfo=dt_tz.utc)
        self.assertEqual(Order.estimate_ready_at("pickup", store, now).minute, 15)
        self.assertEqual(Order.estimate_ready_at("delivery", store, now).minute, 40)

    def test_settings_is_single_row(self):
        FulfillmentSettings.load()
        FulfillmentSettings(delivery_fee=5).save()
        self.assertEqual(FulfillmentSettings.objects.count(), 1)
        self.assertEqual(FulfillmentSettings.load().delivery_fee, Decimal("5.00"))


class FulfillmentApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        DeliveryZone.objects.create(zip_code="12345")

    def test_options(self):
        res = self.client.get(reverse("fulfillment-options"))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["pickup_enabled"])
        self.assertEqual(res.data["delivery_minutes"], 40)

    def test_quote_delivery(self):
        res = self.client.post(reverse("fulfillment-quote"), {
            "fulfillment_type": "delivery", "subtotal": "20.00",
            "contact_phone": "9195550100", "address": GOOD_ADDRESS,
        }, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["delivery_fee"], Decimal("3.99"))
        self.assertEqual(res.data["total_price"], Decimal("25.44"))
        self.assertIn("estimated_ready_at", res.data)

    def test_quote_invalid_returns_field_errors(self):
        res = self.client.post(reverse("fulfillment-quote"),
                               {"fulfillment_type": "delivery", "subtotal": "20.00"}, format="json")
        self.assertEqual(res.status_code, 422)
        self.assertIn("address", res.data["errors"])

    def test_quote_rejects_negative_subtotal(self):
        res = self.client.post(reverse("fulfillment-quote"),
                               {"fulfillment_type": "pickup", "subtotal": "-1"}, format="json")
        self.assertEqual(res.status_code, 422)
        self.assertIn("subtotal", res.data["errors"])

    def test_checkout_page_renders(self):
        res = self.client.get(reverse("checkout"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "How do you want your order?")


class OrderStatusApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.order = Order.objects.create(fulfillment_type="pickup", subtotal=10, tax=1, total_price=11)
        self.url = reverse("order-status", args=[self.order.pk])
        User = get_user_model()
        self.staff = User.objects.create_user("staff", password="x", is_staff=True)
        self.customer = User.objects.create_user("cust", password="x")

    def test_requires_staff(self):
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.patch(self.url, {"status": "in_progress"}, format="json").status_code, 403)

    def test_staff_advances_status(self):
        self.client.force_authenticate(self.staff)
        res = self.client.patch(self.url, {"status": "in_progress"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["next_status"], "ready_for_pickup")

    def test_wrong_flow_rejected(self):
        self.client.force_authenticate(self.staff)
        res = self.client.patch(self.url, {"status": "out_for_delivery"}, format="json")
        self.assertEqual(res.status_code, 409)
