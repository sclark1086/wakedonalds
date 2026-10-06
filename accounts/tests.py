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
                "password": "SecurePassword123!"
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            User.objects.filter(username="testuser").exists()
        )

    def test_password_is_hashed(self):
        self.client.post(
            "/api/accounts/register/",
            {
                "username": "testuser2",
                "password": "SecurePassword123!"
            },
            format="json"
        )

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