from rest_framework.permissions import BasePermission, SAFE_METHODS

from apps.accounts.models import AdminRole
from apps.accounts.services import account_is_active


class IsActiveMember(BasePermission):
    message = "An active, administrator-approved account is required."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and account_is_active(user)
            and user.is_admin_approved
        )


class IsReviewOwnerOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or IsActiveMember().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        return request.method in SAFE_METHODS or obj.reviewer_id == request.user.id


class IsMarketplaceAdmin(BasePermission):
    message = "A verified administrative account is required."

    resource_roles = {
        "analytics": {AdminRole.SUPER_ADMIN},
        "moderation-analytics": {AdminRole.SUPER_ADMIN, AdminRole.MODERATOR},
        "settings": {AdminRole.SUPER_ADMIN},
        "announcements": {AdminRole.SUPER_ADMIN},
        "conversations": {AdminRole.SUPER_ADMIN},
        "pending-approvals": {AdminRole.SUPER_ADMIN},
        "users": {AdminRole.SUPER_ADMIN, AdminRole.SUPPORT_ADMIN},
        "sellers": {AdminRole.SUPER_ADMIN, AdminRole.SUPPORT_ADMIN},
        "products": {AdminRole.SUPER_ADMIN, AdminRole.MODERATOR},
        "categories": {AdminRole.SUPER_ADMIN, AdminRole.MODERATOR},
        "category-suggestions": {AdminRole.SUPER_ADMIN, AdminRole.MODERATOR},
        "reports": {AdminRole.SUPER_ADMIN, AdminRole.MODERATOR, AdminRole.SUPPORT_ADMIN},
        "message-reports": {AdminRole.SUPER_ADMIN, AdminRole.MODERATOR},
        "reviews": {AdminRole.SUPER_ADMIN, AdminRole.MODERATOR},
        "security-activity": {AdminRole.SUPER_ADMIN},
        "audit-logs": {AdminRole.SUPER_ADMIN, AdminRole.MODERATOR},
    }

    def has_permission(self, request, view):
        user = request.user
        resource = view.kwargs.get("resource", "message-reports")
        allowed_roles = self.resource_roles.get(resource, set())
        return bool(
            user
            and user.is_authenticated
            and account_is_active(user)
            and user.is_admin_approved
            and user.is_staff
            and (user.is_superuser or user.admin_role in allowed_roles)
        )
