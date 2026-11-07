import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone

from apps.products.models import validate_image_size


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="buyer_conversations", on_delete=models.PROTECT)
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="seller_conversations", on_delete=models.PROTECT)
    product = models.ForeignKey("products.Product", related_name="conversations", null=True, blank=True, on_delete=models.SET_NULL)
    admin_created = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["buyer", "updated_at"]), models.Index(fields=["seller", "updated_at"])]
        constraints = [
            models.CheckConstraint(condition=~models.Q(buyer=models.F("seller")), name="conversation_members_differ"),
        ]

    def __str__(self):
        return f"Conversation {self.pk}"


def message_attachment_path(instance, filename):
    return f"messages/{instance.conversation_id}/{uuid.uuid4().hex}"


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, related_name="messages", on_delete=models.CASCADE)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="sent_messages", on_delete=models.PROTECT)
    content = models.CharField(max_length=2000, blank=True)
    attachment = models.ImageField(
        upload_to=message_attachment_path,
        blank=True,
        validators=[
            FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "webp"]),
            validate_image_size,
        ],
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(content="") | ~models.Q(attachment=""),
                name="message_has_content_or_attachment",
            ),
        ]

    def clean(self):
        if not self.content.strip() and not self.attachment:
            raise ValidationError("A message must contain text or an attachment.")

    def __str__(self):
        return f"Message {self.pk}"
