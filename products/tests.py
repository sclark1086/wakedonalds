from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from products.models import Product


class InventoryReportTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.staff_user = User.objects.create_user(
            username="staffuser",
            password="TestPass123!",
            is_staff=True,
        )

        self.regular_user = User.objects.create_user(
            username="regularuser",
            password="TestPass123!",
            is_staff=False,
        )

        Product.objects.create(
            name="Classic Burger",
            price=5.99,
            stock=10,
        )

        Product.objects.create(
            name="Apple Pie",
            price=2.99,
            stock=4,
        )

        Product.objects.create(
            name="Cheeseburger",
            price=6.49,
            stock=0,
        )

        self.url = reverse("inventory-report")

    def test_staff_user_can_view_inventory_report(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Wakedonalds Inventory Report")
        self.assertContains(response, "Classic Burger")
        self.assertContains(response, "Apple Pie")
        self.assertContains(response, "Cheeseburger")

    def test_inventory_statuses_display_correctly(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(self.url)

        self.assertContains(response, "In Stock")
        self.assertContains(response, "Low Stock")
        self.assertContains(response, "Out of Stock")

    def test_regular_user_cannot_access_inventory_report(self):
        self.client.force_login(self.regular_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)

    def test_anonymous_user_cannot_access_inventory_report(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)