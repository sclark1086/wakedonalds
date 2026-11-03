
from django.urls import path
from .views import (
    RegisterView,
    LoginView,
    LogoutView,
    TwoFactorSetupView,
    TwoFactorConfirmView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("2fa/setup/", TwoFactorSetupView.as_view(), name="two_factor_setup"),
    path("2fa/confirm/", TwoFactorConfirmView.as_view(), name="two_factor_confirm"),
]
