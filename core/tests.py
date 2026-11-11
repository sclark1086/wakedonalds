from django.test import SimpleTestCase, override_settings
from django.core import mail

from core.email_service import send_order_confirmation


class OrderConfirmationEmailTests(SimpleTestCase):

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
    )
    def test_order_confirmation_email(self):

        result = send_order_confirmation(
            customer_email="test@example.com",
            order_number="WD1001",
            items=[
                {
                    "name": "Classic Burger",
                    "quantity": 2,
                    "price": 5.99
                },
                {
                    "name": "French Fries",
                    "quantity": 1,
                    "price": 2.49
                }
            ],
            total_price=14.47
        )

        self.assertEqual(result, 1)
        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]

        self.assertIn("WD1001", email.subject)
        self.assertEqual(email.to, ["test@example.com"])
        self.assertIn("Classic Burger x2", email.body)
        self.assertIn("French Fries x1", email.body)
        self.assertIn("$14.47", email.body)

from django.test import TestCase
from django.urls import reverse

from products.models import Product


class MenuAvailabilityTests(TestCase):

    def test_menu_shows_available_and_out_of_stock_items(self):
        Product.objects.create(
            name="Classic Burger",
            price=5.99,
            stock=10
        )

        Product.objects.create(
            name="Cheeseburger",
            price=6.49,
            stock=0
        )

        response = self.client.get(reverse("menu"))

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "Classic Burger"
        )

        self.assertContains(
            response,
            "Available"
        )

        self.assertContains(
            response,
            "Stock: 10"
        )

        self.assertContains(
            response,
            "Cheeseburger"
        )

        self.assertContains(
            response,
            "Out of Stock"
        )