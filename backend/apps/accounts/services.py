from django.utils import timezone

from .models import AccountStatus


def account_is_active(user):
    if (
        user.account_status == AccountStatus.TEMPORARILY_SUSPENDED
        and user.suspension_expires_at
        and user.suspension_expires_at <= timezone.now()
    ):
        user.account_status = AccountStatus.ACTIVE
        user.suspension_expires_at = None
        user.save(update_fields=["account_status", "suspension_expires_at", "updated_at"])
    return user.is_active and user.account_status == AccountStatus.ACTIVE
