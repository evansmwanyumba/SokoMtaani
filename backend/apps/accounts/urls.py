from django.urls import path

from .views import (
    CurrentUserView,
    EmailVerificationView,
    LoginView,
    LogoutView,
    MfaVerificationView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegistrationView,
    ResendVerificationView,
    CsrfTokenView,
)


urlpatterns = [
    path("csrf/", CsrfTokenView.as_view(), name="csrf-cookie"),
    path("register/", RegistrationView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("mfa/verify/", MfaVerificationView.as_view(), name="mfa-verify"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", CurrentUserView.as_view(), name="current-user"),
    path("email-verification/", EmailVerificationView.as_view(), name="verify-email"),
    path(
        "email-verification/resend/",
        ResendVerificationView.as_view(),
        name="resend-verification",
    ),
    path(
        "password-reset/",
        PasswordResetRequestView.as_view(),
        name="password-reset-request",
    ),
    path(
        "password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path(
        "password-change/",
        PasswordChangeView.as_view(),
        name="password-change",
    ),
]
