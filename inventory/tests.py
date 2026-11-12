"""Tests for feature 4.4, inventory threshold settings (SRS CFD2, FR5, BR2)."""

from decimal import Decimal

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from cart.models import Cart, CartItem
from orders.models import FulfillmentSettings
from products.models import Product

from .models import DEFAULT_MAX_LEVEL, DEFAULT_MIN_LEVEL, InventoryThreshold, LowStockAlert
from .services import alert_recipients, stock_status

User = get_user_model()


class InventoryTestBase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            "manager", email="manager@example.com", password="SecurePassword123!", is_staff=True
        )
        self.burger = Product.objects.create(name="Classic Burger", price=Decimal("5.99"), stock=20)
        self.threshold = self.burger.inventory_threshold
        self.threshold.min_level = 10
        self.threshold.max_level = 40
        self.threshold.save()

    def set_stock(self, product, stock):
        """Change stock the way the app does (save), committing on_commit hooks."""
        with self.captureOnCommitCallbacks(execute=True):
            product.stock = stock
            product.save(update_fields=["stock"])

    def refresh(self):
        self.burger.refresh_from_db()
        self.threshold.refresh_from_db()


class ThresholdSettingsTests(InventoryTestBase):
    def test_every_new_product_gets_default_thresholds(self):
        fries = Product.objects.create(name="Fries", price=Decimal("2.49"), stock=100)
        t = InventoryThreshold.objects.get(product=fries)
        self.assertEqual((t.min_level, t.max_level), (DEFAULT_MIN_LEVEL, DEFAULT_MAX_LEVEL))

    def test_min_above_max_fails_validation(self):
        self.threshold.min_level, self.threshold.max_level = 50, 10
        with self.assertRaises(ValidationError):
            self.threshold.full_clean()

    def test_database_also_rejects_min_above_max(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            InventoryThreshold.objects.filter(pk=self.threshold.pk).update(min_level=99, max_level=1)

    def test_min_equal_to_max_is_allowed(self):
        self.threshold.min_level = self.threshold.max_level = 15
        self.threshold.full_clean()

    def test_reorder_quantity_tops_up_to_maximum(self):
        self.set_stock(self.burger, 7)
        self.refresh()
        self.assertEqual(self.threshold.reorder_quantity, 33)

    def test_reorder_quantity_never_negative(self):
        self.set_stock(self.burger, 60)
        self.refresh()
        self.assertEqual(self.threshold.reorder_quantity, 0)

    def test_status_labels(self):
        self.assertEqual(stock_status(self.burger), "In Stock")
        self.set_stock(self.burger, 3)
        self.assertEqual(stock_status(self.burger), "Low Stock")
        self.set_stock(self.burger, 0)
        self.assertEqual(stock_status(self.burger), "Out of Stock")


class LowStockFlagAndAlertTests(InventoryTestBase):
    def test_dropping_below_minimum_flags_item_and_emails_admin(self):
        self.set_stock(self.burger, 9)
        self.refresh()
        self.assertTrue(self.threshold.low_stock_flag)
        self.assertIsNotNone(self.threshold.flagged_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Classic Burger", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ["manager@example.com"])
        self.assertIn("Suggested reorder: 31", mail.outbox[0].body)
        alert = LowStockAlert.objects.get()
        self.assertEqual((alert.stock_at_alert, alert.min_level_at_alert), (9, 10))
        self.assertEqual(alert.emailed_to, "manager@example.com")

    def test_stock_exactly_at_minimum_is_not_low(self):
        self.set_stock(self.burger, 10)
        self.refresh()
        self.assertFalse(self.threshold.low_stock_flag)
        self.assertEqual(len(mail.outbox), 0)

    def test_alert_is_sent_once_not_on_every_sale(self):
        for stock in (9, 8, 5, 1):
            self.set_stock(self.burger, stock)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(LowStockAlert.objects.count(), 1)

    def test_restock_clears_flag_and_next_drop_alerts_again(self):
        self.set_stock(self.burger, 5)
        self.set_stock(self.burger, 40)
        self.refresh()
        self.assertFalse(self.threshold.low_stock_flag)
        self.assertIsNotNone(LowStockAlert.objects.get().resolved_at)

        self.set_stock(self.burger, 2)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(LowStockAlert.objects.filter(resolved_at__isnull=True).count(), 1)

    def test_raising_the_minimum_flags_item_immediately(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.threshold.min_level = 25
            self.threshold.save()
        self.refresh()
        self.assertTrue(self.threshold.low_stock_flag)
        self.assertEqual(len(mail.outbox), 1)

    def test_lowering_the_minimum_clears_the_flag(self):
        self.set_stock(self.burger, 8)
        self.threshold.min_level = 5
        self.threshold.save()
        self.refresh()
        self.assertFalse(self.threshold.low_stock_flag)

    def test_no_email_if_order_transaction_rolls_back(self):
        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    self.burger.stock = 2
                    self.burger.save(update_fields=["stock"])
                    raise RuntimeError("order failed")
            except RuntimeError:
                pass
        self.refresh()
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(self.threshold.low_stock_flag)

    @override_settings(LOW_STOCK_ALERT_EMAILS=["kitchen@example.com", "owner@example.com"])
    def test_alert_list_setting_overrides_staff_emails(self):
        self.set_stock(self.burger, 1)
        self.assertEqual(mail.outbox[0].to, ["kitchen@example.com", "owner@example.com"])

    def test_only_active_staff_with_email_get_alerts(self):
        User.objects.create_user("cust", email="cust@example.com", password="x")
        User.objects.create_user("old", email="old@example.com", password="x",
                                 is_staff=True, is_active=False)
        User.objects.create_user("noemail", password="x", is_staff=True)
        self.assertEqual(alert_recipients(), ["manager@example.com"])

    def test_no_recipients_still_flags_without_crashing(self):
        User.objects.all().delete()
        with self.assertLogs("inventory.services", "WARNING"):
            self.set_stock(self.burger, 1)
        self.refresh()
        self.assertTrue(self.threshold.low_stock_flag)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND="inventory.tests.BrokenEmailBackend")
    def test_email_failure_does_not_break_the_stock_change(self):
        with self.assertLogs("inventory.services", "ERROR"):
            self.set_stock(self.burger, 1)
        self.refresh()
        self.assertEqual(self.burger.stock, 1)
        self.assertTrue(self.threshold.low_stock_flag)


class BrokenEmailBackend:
    def __init__(self, *args, **kwargs):
        pass

    def send_messages(self, messages):
        raise ConnectionError("mail server down")


class PlaceOrderIntegrationTests(InventoryTestBase):
    """Stock taken by a real order (UC1) triggers the alert right away (BR2)."""

    def test_order_that_drops_stock_below_minimum_alerts_admin(self):
        FulfillmentSettings.load()
        customer = User.objects.create_user("amy", password="SecurePassword123!")
        cart, _ = Cart.objects.get_or_create(user=customer)
        CartItem.objects.create(cart=cart, product=self.burger, quantity=12)
        client = APIClient()
        client.force_authenticate(customer)

        with self.captureOnCommitCallbacks(execute=True):
            res = client.post("/api/orders/", {"fulfillment_type": "pickup"}, format="json")

        self.assertEqual(res.status_code, 201, res.content)
        self.refresh()
        self.assertEqual(self.burger.stock, 8)
        self.assertTrue(self.threshold.low_stock_flag)
        self.assertEqual(len(mail.outbox), 1)


class ThresholdApiTests(InventoryTestBase):
    def setUp(self):
        super().setUp()
        self.fries = Product.objects.create(name="Fries", price=Decimal("2.49"), stock=2)
        self.api = APIClient()
        self.api.force_authenticate(self.admin)

    def test_list_shows_every_item_with_status(self):
        res = self.api.get("/api/inventory/thresholds/")
        self.assertEqual(res.status_code, 200)
        by_name = {row["product_name"]: row for row in res.data}
        self.assertEqual(by_name["Classic Burger"]["min_level"], 10)
        self.assertFalse(by_name["Classic Burger"]["is_low"])
        self.assertTrue(by_name["Fries"]["is_low"])
        self.assertEqual(by_name["Fries"]["reorder_quantity"], DEFAULT_MAX_LEVEL - 2)

    def test_low_filter(self):
        res = self.api.get("/api/inventory/thresholds/?low=true")
        self.assertEqual([r["product_name"] for r in res.data], ["Fries"])

    def test_admin_can_change_thresholds(self):
        url = f"/api/inventory/thresholds/{self.burger.pk}/"
        with self.captureOnCommitCallbacks(execute=True):
            res = self.api.patch(url, {"min_level": 30, "max_level": 60}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual((res.data["min_level"], res.data["max_level"]), (30, 60))
        self.assertTrue(res.data["is_low"])  # 20 in stock is now below 30
        self.assertEqual(len(mail.outbox), 1)

    def test_min_above_max_is_rejected(self):
        url = f"/api/inventory/thresholds/{self.burger.pk}/"
        res = self.api.patch(url, {"min_level": 41}, format="json")  # max is 40
        self.assertEqual(res.status_code, 400)
        self.assertIn("min_level", res.data)
        self.refresh()
        self.assertEqual(self.threshold.min_level, 10)

    def test_negative_levels_are_rejected(self):
        url = f"/api/inventory/thresholds/{self.burger.pk}/"
        res = self.api.patch(url, {"min_level": -1}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_flag_and_stock_cannot_be_set_through_the_api(self):
        url = f"/api/inventory/thresholds/{self.burger.pk}/"
        self.api.patch(url, {"stock": 999, "is_low": True, "flagged_at": "2026-01-01T00:00:00Z"},
                       format="json")
        self.refresh()
        self.assertEqual(self.burger.stock, 20)
        self.assertFalse(self.threshold.low_stock_flag)

    def test_unknown_product_is_404(self):
        self.assertEqual(self.api.get("/api/inventory/thresholds/9999/").status_code, 404)

    def test_customers_and_guests_are_blocked(self):
        customer = User.objects.create_user("amy", password="SecurePassword123!")
        client = APIClient()
        self.assertIn(client.get("/api/inventory/thresholds/").status_code, (401, 403))
        client.force_authenticate(customer)
        self.assertEqual(client.get("/api/inventory/thresholds/").status_code, 403)
        url = f"/api/inventory/thresholds/{self.burger.pk}/"
        self.assertEqual(client.patch(url, {"min_level": 0}, format="json").status_code, 403)


class AdminPageTests(InventoryTestBase):
    def setUp(self):
        super().setUp()
        self.boss = User.objects.create_superuser("boss", password="x")
        self.client.force_login(self.boss)
        if apps.is_installed("django_otp"):
            from django_otp import DEVICE_ID_SESSION_KEY
            from django_otp.plugins.otp_totp.models import TOTPDevice

            device = TOTPDevice.objects.create(user=self.boss, name="test", confirmed=True)
            session = self.client.session
            session[DEVICE_ID_SESSION_KEY] = device.persistent_id
            session.save()

    def test_threshold_list_shows_low_stock_warning(self):
        self.set_stock(self.burger, 3)
        res = self.client.get("/admin/inventory/inventorythreshold/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Classic Burger")
        self.assertContains(res, "Low Stock")
        self.assertContains(res, "below their minimum level")

    def test_low_stock_filter(self):
        Product.objects.create(name="Shake", price=Decimal("3.00"), stock=100)
        self.set_stock(self.burger, 3)
        res = self.client.get("/admin/inventory/inventorythreshold/?level=low")
        self.assertContains(res, "Classic Burger")
        self.assertNotContains(res, "Shake")

    def test_admin_form_rejects_min_above_max(self):
        url = f"/admin/inventory/inventorythreshold/{self.threshold.pk}/change/"
        res = self.client.post(url, {"min_level": 50, "max_level": 10})
        self.assertEqual(res.status_code, 200)  # form redisplayed with error
        self.assertContains(res, "can&#x27;t be higher than the maximum")
        self.refresh()
        self.assertEqual(self.threshold.min_level, 10)

    def test_admin_stock_edit_triggers_alert(self):
        """Lowering stock on the product (as an admin edit would) raises the alert."""
        self.set_stock(self.burger, 4)
        self.assertEqual(len(mail.outbox), 1)
        res = self.client.get("/admin/inventory/lowstockalert/")
        self.assertContains(res, "Classic Burger")
