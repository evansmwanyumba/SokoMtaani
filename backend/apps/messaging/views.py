from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.accounts.services import account_is_active
from apps.community.models import Block
from apps.community.permissions import IsActiveMember
from apps.products.models import Product, ProductStatus
from apps.notifications.models import Notification
from apps.notifications.services import create_notification
from apps.profiles.models import SellerProfile

from .models import Conversation, Message
from .permissions import IsConversationMember
from .serializers import ConversationSerializer, MessageSerializer


User = get_user_model()


class ConversationListCreateView(generics.ListCreateAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated, IsActiveMember]
    parser_classes = [JSONParser, FormParser]

    def get_queryset(self):
        return Conversation.objects.filter(
            Q(buyer=self.request.user) | Q(seller=self.request.user)
        ).select_related("buyer", "seller", "product", "product__category").prefetch_related(
            "messages", "product__product_images"
        )

    def create(self, request, *args, **kwargs):
        recipient = get_object_or_404(User, pk=request.data.get("recipient"), is_active=True)
        if not account_is_active(recipient):
            raise PermissionDenied("This account is currently unavailable.")
        if recipient.pk == request.user.pk:
            raise ValidationError({"recipient": "You cannot start a conversation with yourself."})
        product_id = request.data.get("product")
        product = None
        if product_id:
            product = get_object_or_404(Product, pk=product_id, status=ProductStatus.ACTIVE)
            if product.seller_id != recipient.pk:
                raise ValidationError({"recipient": "The selected member does not sell this listing."})
        if Block.objects.filter(
            Q(blocker=request.user, blocked=recipient) | Q(blocker=recipient, blocked=request.user)
        ).exists():
            raise PermissionDenied("Messaging is unavailable between these accounts.")
        if product:
            buyer, seller = request.user, recipient
        elif hasattr(recipient, "seller_profile"):
            buyer, seller = request.user, recipient
        elif hasattr(request.user, "seller_profile"):
            buyer, seller = recipient, request.user
        else:
            raise ValidationError({"recipient": "Choose a seller to start a conversation."})
        conversation, created = Conversation.objects.get_or_create(
            buyer=buyer,
            seller=seller,
            product=product,
        )
        serializer = self.get_serializer(conversation)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class ConversationDetailView(APIView):
    permission_classes = [IsAuthenticated, IsActiveMember]

    @extend_schema(responses=ConversationSerializer)
    def get(self, request, conversation_id):
        conversation = get_object_or_404(
            Conversation.objects.filter(Q(buyer=request.user) | Q(seller=request.user)),
            pk=conversation_id,
        )
        Message.objects.filter(conversation=conversation).exclude(sender=request.user).filter(
            read_at__isnull=True
        ).update(read_at=timezone.now())
        conversation = Conversation.objects.select_related("buyer", "seller", "product", "product__category").prefetch_related(
            "messages", "product__product_images"
        ).get(pk=conversation.pk)
        return Response(ConversationSerializer(conversation, context={"request": request}).data)


class MessageListCreateView(generics.ListCreateAPIView):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated, IsActiveMember]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_conversation(self):
        return get_object_or_404(
            Conversation.objects.filter(Q(buyer=self.request.user) | Q(seller=self.request.user)),
            pk=self.kwargs["conversation_id"],
        )

    def get_queryset(self):
        return Message.objects.filter(conversation=self.get_conversation()).select_related("sender")

    def perform_create(self, serializer):
        conversation = self.get_conversation()
        recipient_id = conversation.seller_id if conversation.buyer_id == self.request.user.pk else conversation.buyer_id
        if Block.objects.filter(
            Q(blocker=self.request.user, blocked_id=recipient_id) | Q(blocker_id=recipient_id, blocked=self.request.user)
        ).exists():
            raise PermissionDenied("Messaging is unavailable between these accounts.")
        content = serializer.validated_data.get("content", "").strip()
        attachment = serializer.validated_data.get("attachment")
        if not content and not attachment:
            raise ValidationError({"content": "Write a message or attach an image."})
        message = serializer.save(conversation=conversation, sender=self.request.user, content=content)
        conversation.save(update_fields=["updated_at"])
        recipient = User.objects.get(pk=recipient_id)
        create_notification(
            recipient,
            Notification.Kind.MESSAGE,
            "You have a new message",
            "Open your messages to read and reply.",
            conversation.pk,
        )
