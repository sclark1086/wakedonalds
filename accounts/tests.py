from datetime import timedelta
from django_otp.plugins.otp_totp.models import TOTPDevice
from accounts.models import AccountSecurity
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from django_otp.oath import totp
from cart.models import Cart
from rest_framework.authtoken.models import Token
from accounts.authentication import TOKEN_LIFETIME_HOURS


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


class LoginLockoutTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="lockoutuser",
            password="SecurePassword123!",
        )
        self.login_url = "/api/accounts/login/"

    def test_three_failed_attempts_trigger_lockout(self):
        for _ in range(3):
            response = self.client.post(
                self.login_url,
                {
                    "username": "lockoutuser",
                    "password": "WrongPassword123!",
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(
            self.login_url,
            {
                "username": "lockoutuser",
                "password": "SecurePassword123!",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )
        self.assertNotIn("token", response.data)

    def test_expired_lockout_allows_login_again(self):
        from .models import AccountSecurity

        security = AccountSecurity.objects.create(
            user=self.user,
            failed_login_attempts=3,
            locked_until=timezone.now() - timedelta(minutes=1),
        )

        response = self.client.post(
            self.login_url,
            {
                "username": "lockoutuser",
                "password": "SecurePassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("token", response.data)

        security.refresh_from_db()
        self.assertEqual(security.failed_login_attempts, 0)
        self.assertIsNone(security.locked_until)



class AdminTwoFactorTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="testadmin",
            password="SecurePassword123!",
            is_staff=True,
        )
        self.login_url = "/api/accounts/login/"
        self.setup_url = "/api/accounts/2fa/setup/"
        self.confirm_url = "/api/accounts/2fa/confirm/"

    def credentials(self):
        return {
            "username": "testadmin",
            "password": "SecurePassword123!",
        }

    def test_admin_without_2fa_cannot_receive_token(self):
        response = self.client.post(
            self.login_url,
            self.credentials(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(response.data["requires_2fa_setup"])
        self.assertNotIn("token", response.data)

    def test_admin_can_enroll_and_confirm_2fa(self):
        setup = self.client.post(
            self.setup_url,
            self.credentials(),
            format="json",
        )

        self.assertEqual(setup.status_code, status.HTTP_200_OK)
        self.assertIn("config_url", setup.data)

        device = TOTPDevice.objects.get(user=self.admin, confirmed=False)

        confirm = self.client.post(
            self.confirm_url,
            {
                **self.credentials(),
                "token": totp(device.bin_key),
            },
            format="json",
        )

        self.assertEqual(confirm.status_code, status.HTTP_200_OK)

        device.refresh_from_db()
        self.assertTrue(device.confirmed)

        security = AccountSecurity.objects.get(user=self.admin)
        self.assertTrue(security.two_factor_enabled)

    def test_admin_login_requires_valid_otp(self):
        device = TOTPDevice.objects.create(
            user=self.admin,
            name="Test authenticator",
            confirmed=True,
        )

        # A malformed code must not issue a token.
        response = self.client.post(
            self.login_url,
            {
                **self.credentials(),
                "otp_token": "invalid",
            },
            format="json",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertNotIn("token", response.data)

        # An incorrect six-digit code must not issue a token.
        valid_code = totp(device.bin_key)
        wrong_code = f"{(int(valid_code) + 1) % 1_000_000:06d}"

        response = self.client.post(
            self.login_url,
            {
                **self.credentials(),
                "otp_token": wrong_code,
            },
            format="json",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertNotIn("token", response.data)

        # A valid current code should issue a token.
        response = self.client.post(
            self.login_url,
            {
                **self.credentials(),
                "otp_token": totp(device.bin_key),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("token", response.data)


class TokenExpirationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="expiryuser",
            password="SecurePassword123!",
        )
        self.token = Token.objects.create(user=self.user)

    def test_expired_token_is_rejected(self):
        self.token.created = timezone.now() - timedelta(
            hours=TOKEN_LIFETIME_HOURS + 1
        )
        self.token.save(update_fields=["created"])


        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {self.token.key}"
        )

        response = self.client.get("/api/cart/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(Token.objects.filter(pk=self.token.pk).exists())

    def test_fresh_token_is_accepted(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {self.token.key}"
        )

        response = self.client.get("/api/cart/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)



class AdminTwoFactorLockoutTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="otp_lockout_admin",
            password="SecurePassword123!",
            is_staff=True,
        )
        self.device = TOTPDevice.objects.create(
            user=self.admin,
            name="Test authenticator",
            confirmed=True,
        )
        self.login_url = "/api/accounts/login/"

    def test_failed_otp_attempts_trigger_lockout(self):
        for _ in range(3):
            response = self.client.post(
                self.login_url,
                {
                    "username": "otp_lockout_admin",
                    "password": "SecurePassword123!",
                    "otp_token": "000000",
                },
                format="json",
            )

        # The third failure should be rejected as an invalid OTP.
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        # Even correct credentials and OTP should be blocked.
        response = self.client.post(
            self.login_url,
            {
                "username": "otp_lockout_admin",
                "password": "SecurePassword123!",
                "otp_token": totp(self.device.bin_key),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )
        self.assertNotIn("token", response.data)



class TwoFactorEnrollmentLockoutTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="enrollment_admin",
            password="SecurePassword123!",
            is_staff=True,
        )
        self.setup_url = "/api/accounts/2fa/setup/"
        self.confirm_url = "/api/accounts/2fa/confirm/"
        self.credentials = {
            "username": "enrollment_admin",
            "password": "WrongPassword123!",
        }

    def test_failed_setup_password_attempts_trigger_lockout(self):
        # Three incorrect passwords should trigger the lockout.
        for _ in range(3):
            response = self.client.post(
                self.setup_url,
                self.credentials,
                format="json",
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        # Correct credentials must still be blocked by the lockout.
        response = self.client.post(
            self.setup_url,
            {
                "username": "enrollment_admin",
                "password": "SecurePassword123!",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )
        self.assertNotIn("config_url", response.data)

    def test_failed_confirmation_password_attempts_trigger_lockout(self):
        # Start setup so an unconfirmed device exists.
        setup = self.client.post(
            self.setup_url,
            {
                "username": "enrollment_admin",
                "password": "SecurePassword123!",
            },
            format="json",
        )
        self.assertEqual(setup.status_code, status.HTTP_200_OK)

        # Three incorrect passwords should trigger the lockout.
        for _ in range(3):
            response = self.client.post(
                self.confirm_url,
                {
                    "username": "enrollment_admin",
                    "password": "WrongPassword123!",
                    "token": "123456",
                },
                format="json",
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        # Correct credentials must still be blocked by the lockout.
        response = self.client.post(
            self.confirm_url,
            {
                "username": "enrollment_admin",
                "password": "SecurePassword123!",
                "token": "123456",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )
        self.assertNotIn(
            "message",
            response.data,
        )

    def test_failed_confirmation_otp_attempts_trigger_lockout(self):
        # Create an unconfirmed authenticator device.
        device = TOTPDevice.objects.create(
            user=self.admin,
            name="Test authenticator",
            confirmed=False,
        )

        # Generate an incorrect code based on this device.
        valid_code = totp(device.bin_key)
        wrong_code = f"{(int(valid_code) + 1) % 1_000_000:06d}"

        # Three incorrect OTP codes should trigger the lockout.
        for _ in range(3):
            response = self.client.post(
                self.confirm_url,
                {
                    "username": "enrollment_admin",
                    "password": "SecurePassword123!",
                    "token": wrong_code,
                },
                format="json",
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        # Even a valid code should be blocked after lockout.
        response = self.client.post(
            self.confirm_url,
            {
                "username": "enrollment_admin",
                "password": "SecurePassword123!",
                "token": totp(device.bin_key),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )
        self.assertNotIn("message", response.data)