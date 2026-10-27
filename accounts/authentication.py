
from datetime import timedelta

from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


TOKEN_LIFETIME_HOURS = 8


class ExpiringTokenAuthentication(TokenAuthentication):
    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)

        expiration_time = token.created + timedelta(
            hours=TOKEN_LIFETIME_HOURS
        )

        if timezone.now() >= expiration_time:
            token.delete()
            raise AuthenticationFailed(
                "Your authentication token has expired. Please log in again."
            )

        return user, token
