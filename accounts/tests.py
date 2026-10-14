from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase
from cart.models import Cart


class RegistrationTests(APITestCase):

    def test_user_can_register(self):
        response = self.client.post(
            "/api/accounts/register/",
            {
                "username": "testuser",
                "email": "testuser@example.com",
                "password": "TestPassword123!"
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            User.objects.filter(username="testuser").exists()
        )

    def test_password_is_hashed(self):
        response = self.client.post(
            "/api/accounts/register/",
            {
                "username": "testuser2",
                "email": "testuser2@example.com",
                "password": "SecurePassword123!"
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(username="testuser2")

        self.assertNotEqual(
            user.password,
            "SecurePassword123!"
        )

        self.assertTrue(
            user.check_password("SecurePassword123!")
        )

class LoginTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="loginuser",
            password="SecurePassword123!"
        )

    def test_login_with_correct_password(self):
        response = self.client.post(
            "/api/accounts/login/",
            {
                "username": "loginuser",
                "password": "SecurePassword123!"
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("token", response.data)
        self.assertEqual(
            response.data["username"],
            "loginuser"
        )

    def test_login_with_wrong_password(self):
        response = self.client.post(
            "/api/accounts/login/",
            {
                "username": "loginuser",
                "password": "WrongPassword123!"
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn("token", response.data)


class LogoutTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="logoutuser",
            password="SecurePassword123!"
        )

    def test_logout_deletes_token(self):
        response = self.client.post(
            "/api/accounts/login/",
            {
                "username": "logoutuser",
                "password": "SecurePassword123!"
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        token = response.data["token"]

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {token}"
        )

        logout_response = self.client.post(
            "/api/accounts/logout/"
        )

        self.assertEqual(
            logout_response.status_code,
            status.HTTP_200_OK
        )

        self.assertFalse(
            hasattr(self.user, "auth_token")
        )

    def test_logout_requires_authentication(self):
        response = self.client.post(
            "/api/accounts/logout/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )

class AuthenticationIntegrationTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="cartuser",
            password="SecurePassword123!"
        )

    def test_cart_requires_authentication(self):
        response = self.client.get(
            "/api/cart/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )

    def test_authenticated_user_can_access_cart(self):
        login_response = self.client.post(
            "/api/accounts/login/",
            {
                "username": "cartuser",
                "password": "SecurePassword123!"
            },
            format="json"
        )

        self.assertEqual(
            login_response.status_code,
            status.HTTP_200_OK
        )

        token = login_response.data["token"]

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {token}"
        )

        response = self.client.get(
            "/api/cart/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )


class RegistrationValidationTests(APITestCase):

    def test_weak_password_is_rejected(self):
        response = self.client.post(
            "/api/accounts/register/",
            {
                "username": "weak",
                "email": "weak@example.com",
                "password": "1",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn("password", response.data)

    def test_email_is_required(self):
        response = self.client.post(
            "/api/accounts/register/",
            {
                "username": "noemail",
                "password": "SecurePassword123!",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn("email", response.data)


class TokenCartAccessTests(APITestCase):

    def setUp(self):
        from products.models import Product

        User.objects.create_user(
            username="shopper",
            password="SecurePassword123!",
        )

        login = self.client.post(
            "/api/accounts/login/",
            {
                "username": "shopper",
                "password": "SecurePassword123!",
            },
            format="json",
        )

        self.assertEqual(login.status_code, status.HTTP_200_OK)

        self.client.credentials(
            HTTP_AUTHORIZATION="Token " + login.data["token"]
        )

        self.product = Product.objects.create(
            name="Classic Burger",
            price=5.99,
            stock=10,
        )

    def test_token_user_can_add_update_and_remove_items(self):
        add = self.client.post(
            "/api/cart/items/",
            {
                "product_id": self.product.id,
                "quantity": 1,
            },
            format="json",
        )
        self.assertEqual(add.status_code, status.HTTP_200_OK)

        cart = self.client.get("/api/cart/")
        self.assertEqual(cart.status_code, status.HTTP_200_OK)
        self.assertTrue(cart.data["items"])

        item_id = cart.data["items"][0]["id"]

        update = self.client.patch(
            f"/api/cart/items/{item_id}/",
            {"quantity": 3},
            format="json",
        )
        self.assertEqual(update.status_code, status.HTTP_200_OK)

        delete = self.client.delete(
            f"/api/cart/items/{item_id}/"
        )
        self.assertEqual(
            delete.status_code,
            status.HTTP_204_NO_CONTENT,
        )
