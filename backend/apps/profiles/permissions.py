from rest_framework.permissions import BasePermission, SAFE_METHODS

from apps.accounts.services import account_is_active


class IsActiveAccount(BasePermission):
    message = "This account cannot perform marketplace actions."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and account_is_active(user)
            and user.is_admin_approved
        )


class IsApprovedActiveUser(IsActiveAccount):
    message = "An administrator must approve your account before continuing."

    def has_permission(self, request, view):
        return super().has_permission(request, view)


class IsSellerOwner(IsApprovedActiveUser):
    message = "Active, phone-verified seller capability is required."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return (
            super().has_permission(request, view)
            and hasattr(request.user, "seller_profile")
            and request.user.seller_profile.is_active
        )

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return bool(
            super().has_permission(request, view)
            and obj.seller_id == request.user.id
        )


class IsActiveSeller(IsApprovedActiveUser):
    message = "Active, phone-verified seller capability is required."

    def has_permission(self, request, view):
        return bool(
            super().has_permission(request, view)
            and hasattr(request.user, "seller_profile")
            and request.user.seller_profile.is_active
        )
