"""Tests for place order (UC1) and real-time order status tracking (3.3)."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from cart.models import Cart, CartItem
from products.models import Product

from .models import DeliveryZone, FulfillmentSettings, Order, OrderItem, OrderStatusEvent
from .signals import order_status_changed

User = get_user_model()
PLACE_URL = "/api/orders/"


def track_api(order):
    return f"/api/orders/track/{order.tracking_code}/"


def track_page(order):
    return f"/orders/track/{order.tracking_code}/"


class OrderTestBase(TestCase):
    def setUp(self):
        self.store = FulfillmentSettings.load()  # 7.25% tax, $3.99 delivery
        self.user = User.objects.create_user("amy", password="SecurePassword123!")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.burger = Product.objects.create(name="Classic Burger", price=Decimal("5.99"), stock=10)
        self.fries = Product.objects.create(name="French Fries", price=Decimal("2.49"), stock=10)

    def add_to_cart(self, user, product, quantity):
        cart, _ = Cart.objects.get_or_create(user=user)
        CartItem.objects.create(cart=cart, product=product, quantity=quantity)

    def place(self, **data):
        return self.client.post(PLACE_URL, {"fulfillment_type": "pickup", **data}, format="json")

    def make_order(self, fulfillment_type="pickup"):
        return Order.objects.create(
            user=self.user,
            fulfillment_type=fulfillment_type,
            subtotal=Decimal("10.00"),
            tax=Decimal("0.73"),
            total_price=Decimal("10.73"),
        )


class PlaceOrderTests(OrderTestBase):
    def test_pickup_order_is_created_from_cart(self):
        self.add_to_cart(self.user, self.burger, 2)
        self.add_to_cart(self.user, self.fries, 1)

        res = self.place(contact_phone="(919) 555-1234")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get()
        self.assertEqual(order.user, self.user)
        self.assertEqual(order.subtotal, Decimal("14.47"))
        self.assertEqual(order.tax, Decimal("1.05"))
        self.assertEqual(order.delivery_fee, Decimal("0.00"))
        self.assertEqual(order.total_price, Decimal("15.52"))
        self.assertEqual(order.contact_phone, "9195551234")
        self.assertEqual(order.status, Order.Status.RECEIVED)
        self.assertIsNotNone(order.estimated_ready_at)
        self.assertEqual(res.data["order_number"], order.pk)
        self.assertEqual(res.data["total_price"], "15.52")
        self.assertTrue(res.data["tracking_url"].endswith(track_page(order)))

    def test_items_are_saved_with_name_and_price_at_time_of_order(self):
        self.add_to_cart(self.user, self.burger, 2)
        self.place()

        self.burger.price = Decimal("9.99")
        self.burger.name = "Renamed Burger"
        self.burger.save()

        item = OrderItem.objects.get()
        self.assertEqual((item.name, item.unit_price, item.quantity), ("Classic Burger", Decimal("5.99"), 2))
        self.assertEqual(item.line_total, Decimal("11.98"))

    def test_stock_goes_down_and_cart_is_emptied(self):
        self.add_to_cart(self.user, self.burger, 3)
        self.place()

        self.burger.refresh_from_db()
        self.assertEqual(self.burger.stock, 7)
        self.assertFalse(CartItem.objects.filter(cart__user=self.user).exists())

    def test_browser_subtotal_is_ignored(self):
        self.add_to_cart(self.user, self.burger, 1)
        self.place(subtotal="0.01")
        self.assertEqual(Order.objects.get().subtotal, Decimal("5.99"))

    def test_delivery_order_adds_fee_and_saves_address(self):
        DeliveryZone.objects.create(zip_code="27587")
        self.add_to_cart(self.user, self.burger, 2)  # $11.98, under free-delivery minimum

        res = self.client.post(PLACE_URL, {
            "fulfillment_type": "delivery",
            "contact_phone": "9195551234",
            "address": {"street": "1 Main St", "city": "Wake Forest", "state": "nc", "zip": "27587"},
        }, format="json")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get()
        self.assertEqual(order.delivery_fee, Decimal("3.99"))
        self.assertEqual(order.total_price, Decimal("11.98") + Decimal("3.99") + Decimal("0.87"))
        self.assertEqual((order.delivery_street, order.delivery_state), ("1 Main St", "NC"))

    def test_delivery_without_address_is_rejected_and_nothing_changes(self):
        self.add_to_cart(self.user, self.burger, 2)

        res = self.client.post(PLACE_URL, {"fulfillment_type": "delivery"}, format="json")

        self.assertEqual(res.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertIn("address", res.data["errors"])
        self.assertFalse(Order.objects.exists())
        self.burger.refresh_from_db()
        self.assertEqual(self.burger.stock, 10)
        self.assertTrue(CartItem.objects.filter(cart__user=self.user).exists())

    def test_empty_cart_is_rejected(self):
        res = self.place()
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["errors"]["cart"], "Your cart is empty.")
        self.assertFalse(Order.objects.exists())

    def test_not_enough_stock_is_rejected_and_nothing_changes(self):
        self.add_to_cart(self.user, self.burger, 2)
        self.add_to_cart(self.user, self.fries, 1)
        Product.objects.filter(pk=self.burger.pk).update(stock=1)  # sold out since it was added

        res = self.place()

        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("Classic Burger", res.data["errors"]["cart"])
        self.assertEqual(res.data["out_of_stock"][0]["available"], 1)
        self.assertFalse(Order.objects.exists())
        self.fries.refresh_from_db()
        self.assertEqual(self.fries.stock, 10)
        self.assertEqual(CartItem.objects.filter(cart__user=self.user).count(), 2)

    def test_only_the_customers_own_cart_is_used(self):
        other = User.objects.create_user("bob", password="SecurePassword123!")
        self.add_to_cart(other, self.fries, 4)
        self.add_to_cart(self.user, self.burger, 1)

        self.place()

        self.assertEqual(list(Order.objects.get().items.values_list("name", flat=True)), ["Classic Burger"])
        self.assertEqual(CartItem.objects.filter(cart__user=other).count(), 1)

    def test_login_is_required(self):
        res = APIClient().post(PLACE_URL, {"fulfillment_type": "pickup"}, format="json")
        self.assertIn(res.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_works_with_token_login(self):
        self.add_to_cart(self.user, self.burger, 1)
        token = APIClient().post(
            "/api/accounts/login/",
            {"username": "amy", "password": "SecurePassword123!"},
            format="json",
        ).data["token"]
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Token " + token)

        res = client.post(PLACE_URL, {"fulfillment_type": "pickup"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)


class StatusHistoryTests(OrderTestBase):
    def test_new_order_records_received_event(self):
        order = self.make_order()
        self.assertEqual(list(order.status_events.values_list("status", flat=True)), ["received"])
        self.assertTrue(order.tracking_code)

    def test_tracking_codes_are_unique(self):
        codes = {self.make_order().tracking_code for _ in range(20)}
        self.assertEqual(len(codes), 20)

    def test_each_status_change_is_recorded_once(self):
        order = self.make_order()
        order.status = Order.Status.IN_PROGRESS
        order.save()
        order.save()  # saving again without a change adds nothing
        order.contact_phone = "9195551234"
        order.save()

        reloaded = Order.objects.get(pk=order.pk)
        reloaded.status = Order.Status.READY_FOR_PICKUP
        reloaded.save(update_fields=["status", "updated_at"])

        self.assertEqual(
            list(OrderStatusEvent.objects.filter(order=order).values_list("status", flat=True)),
            ["received", "in_progress", "ready_for_pickup"],
        )

    def test_staff_status_endpoint_records_event_and_sends_signal(self):
        order = self.make_order()
        staff = User.objects.create_user("staff", password="x", is_staff=True)
        client = APIClient()
        client.force_authenticate(staff)
        received = []

        def listener(sender, order, old_status, new_status, **kwargs):
            received.append((order.pk, old_status, new_status))

        order_status_changed.connect(listener)
        try:
            with self.captureOnCommitCallbacks(execute=True):
                res = client.patch(f"/api/orders/{order.pk}/status/", {"status": "in_progress"}, format="json")
        finally:
            order_status_changed.disconnect(listener)

        self.assertEqual(res.status_code, 200)
        self.assertEqual(received, [(order.pk, "received", "in_progress")])
        self.assertTrue(order.status_events.filter(status="in_progress").exists())

    def test_signal_is_sent_once_for_a_new_order(self):
        received = []

        def listener(sender, order, old_status, new_status, **kwargs):
            received.append((old_status, new_status))

        order_status_changed.connect(listener)
        try:
            with self.captureOnCommitCallbacks(execute=True):
                self.make_order()
        finally:
            order_status_changed.disconnect(listener)

        self.assertEqual(received, [(None, "received")])

    def test_admin_status_change_is_recorded(self):
        order = self.make_order()
        admin_user = User.objects.create_superuser("boss", password="x")
        self.client.force_login(admin_user)

        res = self.client.post(f"/admin/orders/order/{order.pk}/change/", {
            "fulfillment_type": "pickup",
            "status": "in_progress",
            "subtotal": "10.00",
            "delivery_fee": "0.00",
            "tax": "0.73",
            "total_price": "10.73",
            "items-TOTAL_FORMS": "0", "items-INITIAL_FORMS": "0",
            "status_events-TOTAL_FORMS": "1", "status_events-INITIAL_FORMS": "1",
            "status_events-0-id": str(order.status_events.get().pk),
            "status_events-0-order": str(order.pk),
        })

        self.assertEqual(res.status_code, 302, getattr(res, "context", None) and res.context["adminform"].form.errors)
        self.assertTrue(order.status_events.filter(status="in_progress").exists())


class TrackingTests(OrderTestBase):
    def test_tracking_shows_pickup_steps_and_current_status(self):
        order = self.make_order()
        order.status = Order.Status.IN_PROGRESS
        order.save()

        res = APIClient().get(track_api(order))  # no login needed, the code is the key

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "in_progress")
        self.assertEqual(res.data["status_label"], "In progress")
        self.assertEqual(res.data["status_message"], "Your food is being made.")
        self.assertFalse(res.data["is_final"])
        steps = res.data["steps"]
        self.assertEqual([s["status"] for s in steps],
                         ["received", "in_progress", "ready_for_pickup", "completed"])
        self.assertEqual([s["done"] for s in steps], [True, True, False, False])
        self.assertEqual([s["current"] for s in steps], [False, True, False, False])
        self.assertIsNotNone(steps[1]["reached_at"])
        self.assertIsNone(steps[2]["reached_at"])

    def test_delivery_orders_use_delivery_steps(self):
        order = self.make_order("delivery")
        res = APIClient().get(track_api(order))
        self.assertEqual([s["status"] for s in res.data["steps"]],
                         ["received", "in_progress", "out_for_delivery", "delivered"])

    def test_tracking_reflects_changes_straight_away(self):
        order = self.make_order()
        client = APIClient()
        self.assertEqual(client.get(track_api(order)).data["status"], "received")

        # Staff update the order through a separate copy, like another request would.
        staff_order = Order.objects.get(pk=order.pk)
        staff_order.status = Order.Status.IN_PROGRESS
        staff_order.save()

        self.assertEqual(client.get(track_api(order)).data["status"], "in_progress")

    def test_final_status_is_flagged(self):
        order = self.make_order()
        for s in ("in_progress", "ready_for_pickup", "completed"):
            order.status = s
            order.save()
        res = APIClient().get(track_api(order))
        self.assertTrue(res.data["is_final"])
        self.assertTrue(all(step["done"] for step in res.data["steps"]))

    def test_private_details_are_not_shown(self):
        order = self.make_order("delivery")
        order.contact_phone = "9195551234"
        order.delivery_street = "1 Main St"
        order.save()

        body = APIClient().get(track_api(order)).content.decode()

        self.assertNotIn("9195551234", body)
        self.assertNotIn("1 Main St", body)
        self.assertNotIn('"user"', body)

    def test_unknown_code_is_not_found(self):
        self.assertEqual(APIClient().get("/api/orders/track/not-a-real-code/").status_code, 404)
        self.assertEqual(self.client.get("/orders/track/not-a-real-code/").status_code, 404)

    def test_tracking_responses_are_not_cached(self):
        order = self.make_order()
        res = APIClient().get(track_api(order))
        self.assertIn("no-cache", res["Cache-Control"])

    def test_tracking_page_shows_receipt_and_live_script(self):
        self.add_to_cart(self.user, self.burger, 2)
        order = Order.objects.get(pk=self.place().data["order_number"])

        res = self.client.get(track_page(order))

        self.assertEqual(res.status_code, 200)
        self.assertContains(res, f"Order #{order.pk}")
        self.assertContains(res, "Classic Burger")
        self.assertContains(res, "$11.98")
        self.assertContains(res, "$12.85")  # 11.98 + 0.87 tax
        self.assertContains(res, "orders/order_status.js")
        self.assertContains(res, 'id="wd-initial-order"')
        self.assertContains(res, reverse("order-tracking", args=[order.tracking_code]))

    def test_checkout_page_has_place_order_button(self):
        res = self.client.get("/checkout/")
        self.assertContains(res, 'id="wd-place-order"')
        self.assertContains(res, reverse("place-order"))
        self.assertContains(res, "orders/place_order.js")
