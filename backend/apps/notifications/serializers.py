from rest_framework import serializers

from .models import Notification, NotificationPreference


class NotificationSerializer(serializers.ModelSerializer):
    text = serializers.CharField(source="message", read_only=True)
    unread = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ("id", "kind", "title", "message", "text", "target_id", "read_at", "unread", "created_at")
        read_only_fields = fields

    def get_unread(self, obj):
        return obj.read_at is None


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = ("email", "messages", "price_changes")
