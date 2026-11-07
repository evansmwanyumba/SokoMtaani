from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.accounts.services import account_is_active
from apps.profiles.permissions import IsSellerOwner


class IsVerifiedUserOrReadOnly(BasePermission):
    message = "An administrator must approve your account before posting marketplace content."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and account_is_active(request.user)
            and request.user.is_admin_approved
        )


class IsOwnerOrReadOnly(IsVerifiedUserOrReadOnly):
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return bool(
            request.user.is_authenticated
            and (request.user.is_superuser or obj.seller_id == request.user.id)
        )
