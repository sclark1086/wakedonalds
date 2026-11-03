from decimal import Decimal

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from products.models import Product

from .models import RewardOption, RewardsSettings
from .services import can_redeem, points_for_amount, points_value

User = get_user_model()


class RewardsSettingsTests(TestCase):
    def test_defaults(self):
        s = RewardsSettings.load()
        self.assertTrue(s.program_enabled)
        self.assertEqual(s.points_per_dollar, Decimal("1.00"))
        self.assertEqual(s.point_value, Decimal("0.0100"))
        self.assertEqual(s.minimum_redemption_points, 100)

    def test_only_one_row_is_ever_kept(self):
        RewardsSettings.load()
        RewardsSettings(points_per_dollar=Decimal("2.00")).save()
        self.assertEqual(RewardsSettings.objects.count(), 1)
        self.assertEqual(RewardsSettings.load().points_per_dollar, Decimal("2.00"))

    def test_negative_values_are_rejected(self):
        s = RewardsSettings.load()
        s.points_per_dollar = Decimal("-1.00")
        with self.assertRaises(ValidationError):
            s.full_clean()


class EarnAndRedeemMathTests(TestCase):
    def setUp(self):
        self.settings = RewardsSettings.load()

    def test_one_point_per_dollar_drops_partial_points(self):
        self.assertEqual(points_for_amount(Decimal("16.47")), 16)

    def test_custom_rate(self):
        self.settings.points_per_dollar = Decimal("2.50")
        self.settings.save()
        self.assertEqual(points_for_amount(Decimal("16.47")), 41)

    def test_admin_change_applies_to_the_next_calculation(self):
        self.assertEqual(points_for_amount(Decimal("10.00")), 10)
        s = RewardsSettings.load()
        s.points_per_dollar = Decimal("3.00")
        s.save()
        self.assertEqual(points_for_amount(Decimal("10.00")), 30)

    def test_disabled_program_earns_nothing(self):
        self.settings.program_enabled = False
        self.settings.save()
        self.assertEqual(points_for_amount(Decimal("50.00")), 0)

    def test_zero_or_negative_amount_earns_nothing(self):
        self.assertEqual(points_for_amount(Decimal("0")), 0)
        self.assertEqual(points_for_amount(Decimal("-5.00")), 0)

    def test_points_value(self):
        self.assertEqual(points_value(250), Decimal("2.50"))
        self.assertEqual(points_value(0), Decimal("0.00"))

    def test_can_redeem_needs_minimum_and_cost(self):
        self.assertFalse(can_redeem(99, 50))      # under the 100-point minimum
        self.assertFalse(can_redeem(120, 150))    # can't cover the cost
        self.assertTrue(can_redeem(150, 150))
        self.settings.program_enabled = False
        self.settings.save()
        self.assertFalse(can_redeem(500, 150))


class RewardOptionTests(TestCase):
    def setUp(self):
        self.fries = Product.objects.create(name="Fries", price=Decimal("2.49"), stock=10)

    def test_free_item_needs_a_product(self):
        option = RewardOption(name="Free fries", kind=RewardOption.Kind.FREE_ITEM, points_cost=150)
        with self.assertRaises(ValidationError) as ctx:
            option.full_clean()
        self.assertIn("product", ctx.exception.message_dict)

    def test_free_item_cannot_have_a_discount(self):
        option = RewardOption(
            name="Free fries", kind=RewardOption.Kind.FREE_ITEM, product=self.fries,
            discount_amount=Decimal("1.00"), points_cost=150,
        )
        with self.assertRaises(ValidationError) as ctx:
            option.full_clean()
        self.assertIn("discount_amount", ctx.exception.message_dict)

    def test_discount_needs_an_amount_and_no_product(self):
        option = RewardOption(name="$5 off", kind=RewardOption.Kind.DISCOUNT, points_cost=500)
        with self.assertRaises(ValidationError) as ctx:
            option.full_clean()
        self.assertIn("discount_amount", ctx.exception.message_dict)

        option.discount_amount = Decimal("5.00")
        option.product = self.fries
        with self.assertRaises(ValidationError) as ctx:
            option.full_clean()
        self.assertIn("product", ctx.exception.message_dict)

    def test_points_cost_must_be_at_least_one(self):
        option = RewardOption(
            name="$5 off", kind=RewardOption.Kind.DISCOUNT,
            discount_amount=Decimal("5.00"), points_cost=0,
        )
        with self.assertRaises(ValidationError):
            option.full_clean()

    def test_valid_options_save(self):
        RewardOption(name="Free fries", kind="free_item", product=self.fries, points_cost=150).full_clean()
        RewardOption(name="$5 off", kind="discount", discount_amount=Decimal("5.00"), points_cost=500).full_clean()

    def test_product_used_by_a_reward_cannot_be_deleted(self):
        from django.db.models import ProtectedError
        RewardOption.objects.create(name="Free fries", kind="free_item", product=self.fries, points_cost=150)
        with self.assertRaises(ProtectedError):
            self.fries.delete()


class RewardsProgramApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("rewards-program")
        self.fries = Product.objects.create(name="Fries", price=Decimal("2.49"), stock=10)
        self.burger = Product.objects.create(name="Wake Burger", price=Decimal("6.99"), stock=0)
        RewardOption.objects.create(name="Free fries", kind="free_item", product=self.fries, points_cost=150)
        RewardOption.objects.create(name="Free burger", kind="free_item", product=self.burger, points_cost=400)
        RewardOption.objects.create(name="$5 off", kind="discount", discount_amount=Decimal("5.00"), points_cost=500)
        RewardOption.objects.create(
            name="Retired reward", kind="discount", discount_amount=Decimal("1.00"), points_cost=50, active=False,
        )

    def test_anyone_can_read_the_program(self):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["program_enabled"])
        self.assertEqual(res.data["points_per_dollar"], "1.00")
        self.assertEqual(res.data["minimum_redemption_points"], 100)

    def test_only_active_rewards_are_listed_cheapest_first(self):
        names = [r["name"] for r in self.client.get(self.url).data["rewards"]]
        self.assertEqual(names, ["Free fries", "Free burger", "$5 off"])

    def test_out_of_stock_free_item_is_marked_unavailable(self):
        rewards = {r["name"]: r for r in self.client.get(self.url).data["rewards"]}
        self.assertTrue(rewards["Free fries"]["available"])
        self.assertFalse(rewards["Free burger"]["available"])
        self.assertEqual(rewards["Free fries"]["product_name"], "Fries")
        self.assertIsNone(rewards["$5 off"]["product_name"])

    def test_disabled_program_lists_no_rewards(self):
        s = RewardsSettings.load()
        s.program_enabled = False
        s.save()
        res = self.client.get(self.url)
        self.assertFalse(res.data["program_enabled"])
        self.assertEqual(res.data["rewards"], [])

    def test_customers_cannot_change_the_program(self):
        res = self.client.post(self.url, {"points_per_dollar": "100"}, format="json")
        self.assertEqual(res.status_code, 405)


class RewardsAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("boss", password="x")
        self.client.force_login(self.admin)
        if apps.is_installed("django_otp"):
            # When admin 2FA (PR #14) is merged, the admin needs a verified device.
            from django_otp import DEVICE_ID_SESSION_KEY
            from django_otp.plugins.otp_totp.models import TOTPDevice

            device = TOTPDevice.objects.create(user=self.admin, name="test", confirmed=True)
            session = self.client.session
            session[DEVICE_ID_SESSION_KEY] = device.persistent_id
            session.save()

    def test_admin_can_update_settings(self):
        settings = RewardsSettings.load()
        res = self.client.post(f"/admin/rewards/rewardssettings/{settings.pk}/change/", {
            "program_enabled": "on",
            "points_per_dollar": "2.00",
            "point_value": "0.0200",
            "minimum_redemption_points": "50",
        })
        self.assertEqual(res.status_code, 302)
        self.assertEqual(points_for_amount(Decimal("10.00")), 20)

    def test_settings_cannot_be_added_twice_or_deleted(self):
        RewardsSettings.load()
        self.assertEqual(self.client.get("/admin/rewards/rewardssettings/add/").status_code, 403)
        self.assertEqual(self.client.get("/admin/rewards/rewardssettings/1/delete/").status_code, 403)

    def test_admin_can_add_a_reward_and_sees_product_names(self):
        Product.objects.create(name="Fries", price=Decimal("2.49"), stock=10)
        page = self.client.get("/admin/rewards/rewardoption/add/")
        self.assertContains(page, "Fries ($2.49)")

        res = self.client.post("/admin/rewards/rewardoption/add/", {
            "name": "$5 off", "description": "", "kind": "discount",
            "product": "", "discount_amount": "5.00", "points_cost": "500",
            "active": "on", "sort_order": "0",
        })
        self.assertEqual(res.status_code, 302)
        self.assertTrue(RewardOption.objects.filter(name="$5 off").exists())

    def test_admin_form_shows_error_for_invalid_reward(self):
        res = self.client.post("/admin/rewards/rewardoption/add/", {
            "name": "Broken", "description": "", "kind": "free_item",
            "product": "", "discount_amount": "", "points_cost": "100",
            "active": "on", "sort_order": "0",
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Choose the menu item this reward gives away.")
        self.assertFalse(RewardOption.objects.exists())
