
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Product
from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice


class ProductModelTests(TestCase):

    def test_product_creation(self):
        product = Product.objects.create(
            name="Classic Burger",
            description="A classic beef burger",
            price=Decimal("5.99"),
            category="burgers",
            ingredients="Beef, lettuce, tomato, bun",
            stock=10,
            is_available=True,
        )

        self.assertEqual(product.name, "Classic Burger")
        self.assertEqual(product.price, Decimal("5.99"))
        self.assertEqual(product.category, "burgers")
        self.assertTrue(product.is_available)

    def test_product_string_representation(self):
        product = Product.objects.create(
            name="Classic Burger",
            price=Decimal("5.99"),
        )

        self.assertEqual(str(product), "Classic Burger")



class ProductAdminTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.admin_user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="testpassword123",
        )

        self.client.force_login(self.admin_user)

        device = TOTPDevice.objects.create(
            user=self.admin_user,
            name="Test device",
            confirmed=True,
        )

        session = self.client.session
        session["otp_device_id"] = device.persistent_id
        session.save()

    def test_admin_can_access_product_list(self):
        response = self.client.get(
            reverse("admin:products_product_changelist")
        )
        self.assertEqual(response.status_code, 200)

    def test_admin_can_access_product_add_page(self):
        response = self.client.get(
            reverse("admin:products_product_add")
        )
        self.assertEqual(response.status_code, 200)

