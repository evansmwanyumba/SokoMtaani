from rest_framework import serializers

from apps.products.serializers import ProductSerializer

from .models import Conversation, Message


class MessageSerializer(serializers.ModelSerializer):
    mine = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ("id", "sender", "content", "attachment", "created_at", "read_at", "mine")
        read_only_fields = ("id", "sender", "created_at", "read_at", "mine")

    def get_mine(self, obj):
        request = self.context.get("request")
        return bool(request and request.user.is_authenticated and obj.sender_id == request.user.pk)


class ConversationSerializer(serializers.ModelSerializer):
    other_user_id = serializers.SerializerMethodField()
    person = serializers.SerializerMethodField()
    product_detail = ProductSerializer(source="product", read_only=True)
    messages = MessageSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ("id", "buyer", "seller", "product", "product_detail", "admin_created", "other_user_id", "person", "messages", "last_message", "unread_count", "updated_at")
        read_only_fields = fields

    def get_other_user_id(self, obj):
        other_user_id = obj.seller_id if self.context["request"].user.pk == obj.buyer_id else obj.buyer_id
        return str(other_user_id)

    def get_person(self, obj):
        user = obj.seller if self.context["request"].user.pk == obj.buyer_id else obj.buyer
        return " ".join(part for part in (user.first_name, user.last_name) if part) or user.email.split("@")[0]

    def get_last_message(self, obj):
        last = obj.messages.order_by("-created_at").first()
        return MessageSerializer(last, context=self.context).data if last else None

    def get_unread_count(self, obj):
        user = self.context["request"].user
        return obj.messages.filter(read_at__isnull=True).exclude(sender=user).count()
