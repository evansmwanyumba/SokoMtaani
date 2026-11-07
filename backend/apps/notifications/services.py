from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.accounts.models import AccountStatus, AdminRole

from .models import Notification, NotificationPreference


def create_notification(user, kind, title, message="", target_id=""):
    preferences, _ = NotificationPreference.objects.get_or_create(user=user)
    if kind == Notification.Kind.MESSAGE and not preferences.messages:
        return None
    return Notification.objects.create(
        user=user,
        kind=kind,
        title=title,
        message=message,
        target_id=str(target_id),
    )


def notify_active_superusers(kind, title, message="", target_id=""):
    user_model = get_user_model()
    admins = user_model.objects.filter(
        is_active=True,
        account_status=AccountStatus.ACTIVE,
        is_admin_approved=True,
    ).filter(Q(is_superuser=True) | Q(admin_role=AdminRole.SUPER_ADMIN)).distinct()
    return Notification.objects.bulk_create([
        Notification(
            user=admin,
            kind=kind,
            title=title,
            message=message,
            target_id=str(target_id),
        )
        for admin in admins
    ])
