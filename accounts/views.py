
from datetime import timedelta
from django.contrib.auth import authenticate
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from .authentication import ExpiringTokenAuthentication
from .models import AccountSecurity
from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    TwoFactorSetupSerializer,
    TwoFactorVerifySerializer,
)


MAX_FAILED_ATTEMPTS = 3
LOCKOUT_MINUTES = 5


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]



class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username", "")

        # Check for a temporary lockout before validating credentials.
        user_security = None
        if username:
            from django.contrib.auth.models import User

            user = User.objects.filter(username=username).first()
            if user:
                user_security, _ = AccountSecurity.objects.get_or_create(
                    user=user
                )

                if (
                    user_security.locked_until
                    and user_security.locked_until > timezone.now()
                ):
                    return Response(
                        {
                            "detail": (
                                "Too many failed login attempts. "
                                "Please try again later."
                            )
                        },
                        status=status.HTTP_429_TOO_MANY_REQUESTS,
                    )

                # Clear an expired lockout.
                if (
                    user_security.locked_until
                    and user_security.locked_until <= timezone.now()
                ):
                    user_security.failed_login_attempts = 0
                    user_security.locked_until = None
                    user_security.save(
                        update_fields=[
                            "failed_login_attempts",
                            "locked_until",
                        ]
                    )

        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError:
            if user_security:
                user_security.failed_login_attempts += 1

                if user_security.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
                    user_security.locked_until = (
                        timezone.now()
                        + timedelta(minutes=LOCKOUT_MINUTES)
                    )

                user_security.save(
                    update_fields=[
                        "failed_login_attempts",
                        "locked_until",
                    ]
                )
            raise

        user = serializer.validated_data["user"]
        user_security, _ = AccountSecurity.objects.get_or_create(user=user)

        # Admins must complete two-factor authentication before receiving a token.
        if user.is_staff or user.is_superuser:
            device = TOTPDevice.objects.filter(
                user=user,
                confirmed=True,
            ).first()

            if device is None:
                return Response(
                    {
                        "detail": (
                            "Two-factor authentication setup is required "
                            "for this administrator account."
                        ),
                        "requires_2fa_setup": True,
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            otp_token = request.data.get("otp_token", "")
            if not otp_token:
                return Response(
                    {
                        "detail": "Enter your authenticator code.",
                        "requires_2fa": True,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not device.verify_token(str(otp_token)):
                return Response(
                    {"detail": "Invalid authenticator code."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Successful login resets the failed-password counter.
        user_security.failed_login_attempts = 0
        user_security.locked_until = None
        user_security.save(
            update_fields=["failed_login_attempts", "locked_until"]
        )

        # Issue a fresh token after successful authentication.
        Token.objects.filter(user=user).delete()
        token = Token.objects.create(user=user)

        return Response(
            {
                "token": token.key,
                "username": user.username,
            },
            status=status.HTTP_200_OK,
        )



class LogoutView(generics.GenericAPIView):
    authentication_classes = [ExpiringTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.user.auth_token.delete()

        return Response(
            {"message": "Successfully logged out."},
            status=status.HTTP_200_OK,
        )


class TwoFactorSetupView(generics.GenericAPIView):
    serializer_class = TwoFactorSetupSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )

        if user is None:
            return Response(
                {"detail": "Invalid username or password."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Only staff/admin accounts can enroll through this endpoint.
        if not (user.is_staff or user.is_superuser):
            return Response(
                {"detail": "Two-factor enrollment is for administrators."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Never reveal the secret for an already-confirmed device.
        confirmed_device = TOTPDevice.objects.filter(
            user=user,
            confirmed=True,
        ).first()

        if confirmed_device:
            return Response(
                {"detail": "Two-factor authentication is already configured."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Reuse an unconfirmed device rather than creating a new secret
        # every time setup is requested.
        device = TOTPDevice.objects.filter(
            user=user,
            confirmed=False,
        ).first()

        if device is None:
            device = TOTPDevice.objects.create(
                user=user,
                name="Authenticator",
                confirmed=False,
            )

        return Response(
            {
                "message": "Scan the provisioning URI with your authenticator app, then verify a code.",
                "config_url": device.config_url,
            },
            status=status.HTTP_200_OK,
        )


class TwoFactorConfirmView(generics.GenericAPIView):
    serializer_class = TwoFactorVerifySerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )

        if user is None:
            return Response(
                {"detail": "Invalid username or password."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not (user.is_staff or user.is_superuser):
            return Response(
                {"detail": "Two-factor enrollment is for administrators."},
                status=status.HTTP_403_FORBIDDEN,
            )

        device = TOTPDevice.objects.filter(
            user=user,
            confirmed=False,
        ).first()

        if device is None:
            return Response(
                {"detail": "Start two-factor setup before confirming it."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not device.verify_token(serializer.validated_data["token"]):
            return Response(
                {"detail": "Invalid authenticator code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        device.confirmed = True
        device.save(update_fields=["confirmed"])

        security, _ = AccountSecurity.objects.get_or_create(user=user)
        security.two_factor_enabled = True
        security.save(update_fields=["two_factor_enabled"])

        return Response(
            {"message": "Two-factor authentication successfully enabled."},
            status=status.HTTP_200_OK,
        )