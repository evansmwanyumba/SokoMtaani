from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .tokens import make_email_verification_token


def send_verification_email(user):
    token = make_email_verification_token(user)
    link = f"{settings.FRONTEND_BASE_URL}/#/verify-email?{urlencode({'token': token})}"
    send_mail(
        "Verify your SokoMtaani email",
        f"Confirm your email address by opening this link:\n\n{link}\n",
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


def send_password_reset_email(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    query = urlencode({"uid": uid, "token": token})
    link = f"{settings.FRONTEND_BASE_URL}/#/reset-password?{query}"
    send_mail(
        "Reset your SokoMtaani password",
        f"Reset your password by opening this link:\n\n{link}\n",
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )
