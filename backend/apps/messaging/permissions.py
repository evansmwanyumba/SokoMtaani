from rest_framework.permissions import BasePermission


class IsConversationMember(BasePermission):
    message = "This conversation is not available to your account."

    def has_object_permission(self, request, view, obj):
        return request.user.pk in (obj.buyer_id, obj.seller_id)
