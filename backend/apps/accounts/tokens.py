from django.conf import settings
from django.core import signing

from .models import User


EMAIL_VERIFICATION_SALT = "sokomtaani.accounts.email-verification"


def make_email_verification_token(user):
    return signing.dumps(str(user.pk), salt=EMAIL_VERIFICATION_SALT, compress=True)


def user_from_email_verification_token(token):
    user_id = signing.loads(
        token,
        salt=EMAIL_VERIFICATION_SALT,
        max_age=settings.EMAIL_VERIFICATION_MAX_AGE_SECONDS,
    )
    return User.objects.get(pk=user_id)
