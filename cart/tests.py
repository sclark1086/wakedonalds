from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from products.models import Product
from .models import CartItem


class CartAPITestCase(TestCase):

    def setUp(self):
        self.client = APIClient()

        self.user = User.objects.create_user(
            username="testuser",
            password="testpassword123"
        )

        self.client.force_authenticate(user=self.user)

    def test_get_cart(self):
        response = self.client.get("/api/cart/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"], self.user.id)
        self.assertEqual(response.data["items"], [])

    def test_add_product_to_cart(self):
        product = Product.objects.create(
            name="Big Mac",
            price=5.99,
            stock=10
        )

        response = self.client.post(
            "/api/cart/items/",
            {
                "product_id": product.id,
                "quantity": 2
            },
            format="json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["product"], "Big Mac")
        self.assertEqual(response.data["quantity"], 2)

        item = CartItem.objects.get(
            product=product,
            cart__user=self.user
        )

        self.assertEqual(item.quantity, 2)


    def test_adding_same_product_increases_quantity(self):
        product = Product.objects.create(
            name="Big Mac",
            price=5.99,
            stock=10
        )

        first_response = self.client.post(
            "/api/cart/items/",
            {
                "product_id": product.id,
                "quantity": 2
            },
            format="json"
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(first_response.data["quantity"], 2)

        second_response = self.client.post(
            "/api/cart/items/",
            {
                "product_id": product.id,
                "quantity": 3
            },
            format="json"
        )

        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.data["quantity"], 5)

        self.assertEqual(
            CartItem.objects.filter(
                product=product,
                cart__user=self.user
            ).count(),
            1
        )

    def test_cannot_add_more_than_stock(self):
        product = Product.objects.create(
            name="Big Mac",
            price=5.99,
            stock=5
        )

        response = self.client.post(
            "/api/cart/items/",
            {
                "product_id": product.id,
                "quantity": 6
            },
            format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["error"],
            "Not enough stock available"
        )

        self.assertFalse(
            CartItem.objects.filter(
                product=product,
                cart__user=self.user
            ).exists()
        )

    def test_update_cart_item_quantity(self):
        product = Product.objects.create(
            name="Big Mac",
            price=5.99,
            stock=10
        )

        response = self.client.post(
            "/api/cart/items/",
            {
                "product_id": product.id,
                "quantity": 2
            },
            format="json"
        )

        self.assertEqual(response.status_code, 200)

        item = CartItem.objects.get(
            product=product,
            cart__user=self.user
        )

        response = self.client.patch(
            f"/api/cart/items/{item.id}/",
            {
                "quantity": 5
            },
            format="json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["quantity"], 5)

        item.refresh_from_db()

        self.assertEqual(item.quantity, 5)

    def test_cannot_update_quantity_to_zero(self):
        product = Product.objects.create(
            name="Big Mac",
            price=5.99,
            stock=10
        )

        self.client.post(
            "/api/cart/items/",
            {
                "product_id": product.id,
                "quantity": 2
            },
            format="json"
        )

        item = CartItem.objects.get(
            product=product,
            cart__user=self.user
        )

        response = self.client.patch(
            f"/api/cart/items/{item.id}/",
            {
                "quantity": 0
            },
            format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["error"],
            "quantity must be at least 1"
        )

        item.refresh_from_db()

        self.assertEqual(item.quantity, 2)

    def test_cannot_update_quantity_with_text(self):
        product = Product.objects.create(
            name="Big Mac",
            price=5.99,
            stock=10
        )

        self.client.post(
            "/api/cart/items/",
            {
                "product_id": product.id,
                "quantity": 2
            },
            format="json"
        )

        item = CartItem.objects.get(
            product=product,
            cart__user=self.user
        )

        response = self.client.patch(
            f"/api/cart/items/{item.id}/",
            {
                "quantity": "hello"
            },
            format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["error"],
            "quantity must be a whole number"
        )

        item.refresh_from_db()

        self.assertEqual(item.quantity, 2)

    def test_cannot_update_quantity_above_stock(self):
        product = Product.objects.create(
            name="Big Mac",
            price=5.99,
            stock=10
        )

        self.client.post(
            "/api/cart/items/",
            {
                "product_id": product.id,
                "quantity": 2
            },
            format="json"
        )

        item = CartItem.objects.get(
            product=product,
            cart__user=self.user
        )

        response = self.client.patch(
            f"/api/cart/items/{item.id}/",
            {
                "quantity": 11
            },
            format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["error"],
            "Not enough stock available"
        )

        item.refresh_from_db()

        self.assertEqual(item.quantity, 2)

    def test_cannot_update_quantity_with_decimal(self):
        product = Product.objects.create(
            name="Big Mac",
            price=5.99,
            stock=10
        )

        self.client.post(
            "/api/cart/items/",
            {
                "product_id": product.id,
                "quantity": 2
            },
            format="json"
        )

        item = CartItem.objects.get(
            product=product,
            cart__user=self.user
        )

        response = self.client.patch(
            f"/api/cart/items/{item.id}/",
            {
                "quantity": 1.5
            },
            format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["error"],
            "quantity must be a whole number"
        )

        item.refresh_from_db()

        self.assertEqual(item.quantity, 2)

    def test_remove_cart_item(self):
        product = Product.objects.create(
            name="Big Mac",
            price=5.99,
            stock=10
        )

        self.client.post(
            "/api/cart/items/",
            {
                "product_id": product.id,
                "quantity": 2
            },
            format="json"
        )

        item = CartItem.objects.get(
            product=product,
            cart__user=self.user
        )

        response = self.client.delete(
            f"/api/cart/items/{item.id}/"
        )

        self.assertEqual(response.status_code, 204)

        self.assertFalse(
            CartItem.objects.filter(
                id=item.id
            ).exists()
        )

    def test_user_cannot_update_another_users_cart_item(self):
        product = Product.objects.create(
            name="Big Mac",
            price=5.99,
            stock=10
        )

        # User 1 adds the product to their cart
        self.client.post(
            "/api/cart/items/",
            {
                "product_id": product.id,
                "quantity": 2
            },
            format="json"
        )

        item = CartItem.objects.get(
            product=product,
            cart__user=self.user
        )

        # Create a second user
        other_user = User.objects.create_user(
            username="otheruser",
            password="testpassword123"
        )

        # Log in as User 2
        self.client.force_authenticate(user=other_user)

        # User 2 tries to modify User 1's cart item
        response = self.client.patch(
            f"/api/cart/items/{item.id}/",
            {
                "quantity": 5
            },
            format="json"
        )

        self.assertEqual(response.status_code, 404)

        item.refresh_from_db()

        # User 1's item should still be quantity 2
        self.assertEqual(item.quantity, 2)