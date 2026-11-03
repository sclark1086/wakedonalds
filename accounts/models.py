
from django.conf import settings
from django.db import models


class AccountSecurity(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="account_security",
    )
    two_factor_enabled = models.BooleanField(default=False)
    failed_login_attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    def __str__(self):
        return f"Security settings for {self.user.username}"

class RewardAccount(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="rewards",
    )

    points_balance = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.user.username} - {self.points_balance} points"


