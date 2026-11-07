from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, serializers, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.products.models import Comment, Product
from apps.notifications.models import Notification
from apps.notifications.services import create_notification
from apps.notifications.services import notify_active_superusers
from apps.profiles.models import SellerProfile

from .models import (
    Announcement,
    Block,
    CartItem,
    CategorySuggestion,
    Favorite,
    HelpfulVote,
    PlatformSettings,
    Report,
    Review,
    SupportConversation,
    SupportMessage,
)
from .permissions import IsActiveMember, IsReviewOwnerOrReadOnly
from .serializers import (
    BlockedMemberSerializer,
    AnnouncementSerializer,
    CartItemSerializer,
    CategorySuggestionSerializer,
    FavoriteSerializer,
    HelpfulVoteResponseSerializer,
    PlatformSettingsSerializer,
    ReportSerializer,
    ReviewSerializer,
    SupportConversationCreateSerializer,
    SupportConversationSerializer,
    SupportMessageSerializer,
)


User = get_user_model()


class FavoriteListCreateView(generics.ListCreateAPIView):
    serializer_class = FavoriteSerializer
    permission_classes = [IsAuthenticated, IsActiveMember]

    def get_queryset(self):
        return Favorite.objects.filter(user=self.request.user).select_related(
            "product", "product__category", "product__seller"
        ).prefetch_related("product__product_images")


class FavoriteDeleteView(APIView):
    permission_classes = [IsAuthenticated, IsActiveMember]

    @extend_schema(request=None, responses={204: None})
    def delete(self, request, product_id):
        favorite = get_object_or_404(Favorite, user=request.user, product_id=product_id)
        favorite.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SellerReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [IsReviewOwnerOrReadOnly]
    http_method_names = ["get", "post", "patch", "put", "head", "options"]
    lookup_field = "pk"

    def get_seller(self):
        return get_object_or_404(SellerProfile, user_id=self.kwargs["seller_id"], is_active=True).user

    def get_queryset(self):
        return Review.objects.filter(seller=self.get_seller(), is_visible=True).select_related("reviewer")

    def perform_create(self, serializer):
        seller = self.get_seller()
        if seller.pk == self.request.user.pk:
            raise PermissionDenied("You cannot review your own seller account.")
        review = serializer.save(seller=seller, reviewer=self.request.user)
        create_notification(
            seller,
            Notification.Kind.REVIEW,
            "You received a seller review",
            "A member shared community feedback about your seller profile.",
            review.pk,
        )


class ReportCreateView(generics.CreateAPIView):
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticated, IsActiveMember]

    def perform_create(self, serializer):
        report = serializer.save()
        account_was_suspended = report.suspensions.exists()
        notify_active_superusers(
            Notification.Kind.REPORT,
            (
                "A reported account was suspended"
                if account_was_suspended
                else "A community report needs review"
            ),
            (
                "A member account was suspended automatically pending administrator investigation."
                if account_was_suspended
                else f"A member reported {report.target_type} content."
            ),
            report.pk,
        )


class PublicSiteInfoView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses=PlatformSettingsSerializer)
    def get(self, request):
        settings_obj = PlatformSettings.get_solo()
        return Response(PlatformSettingsSerializer(settings_obj).data)


class BlockListCreateView(generics.ListCreateAPIView):
    serializer_class = BlockedMemberSerializer
    permission_classes = [IsAuthenticated, IsActiveMember]

    def get_queryset(self):
        return Block.objects.filter(blocker=self.request.user).select_related("blocked")

    def list(self, request, *args, **kwargs):
        rows = self.get_queryset()
        results = [{
            "id": str(row.blocked_id),
            "display_name": " ".join(part for part in (row.blocked.first_name, row.blocked.last_name) if part)
            or row.blocked.email.split("@")[0],
        } for row in rows]
        return Response({"count": len(results), "next": None, "previous": None, "results": results})

    def create(self, request, *args, **kwargs):
        blocked_id = request.data.get("user")
        blocked = get_object_or_404(User, pk=blocked_id, is_active=True)
        if blocked.pk == request.user.pk:
            return Response({"user": "You cannot block yourself."}, status=status.HTTP_400_BAD_REQUEST)
        Block.objects.get_or_create(blocker=request.user, blocked=blocked)
        return Response(status=status.HTTP_201_CREATED)


class BlockDetailView(APIView):
    permission_classes = [IsAuthenticated, IsActiveMember]

    @extend_schema(request=None, responses={201: None})
    def post(self, request, user_id):
        blocked = get_object_or_404(User, pk=user_id, is_active=True)
        if blocked.pk == request.user.pk:
            return Response({"detail": "You cannot block yourself."}, status=status.HTTP_400_BAD_REQUEST)
        Block.objects.get_or_create(blocker=request.user, blocked=blocked)
        return Response(status=status.HTTP_201_CREATED)

    @extend_schema(responses={204: None})
    def delete(self, request, user_id):
        block = get_object_or_404(Block, blocker=request.user, blocked_id=user_id)
        block.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CartView(APIView):
    permission_classes = [IsAuthenticated, IsActiveMember]

    def get(self, request):
        items = CartItem.objects.filter(user=request.user).select_related(
            "product", "product__category", "product__seller"
        ).prefetch_related("product__product_images")
        return Response(CartItemSerializer(items, many=True, context={"request": request}).data)

    def post(self, request):
        serializer = CartItemSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        item, _ = CartItem.objects.get_or_create(
            user=request.user,
            product=serializer.validated_data["product"],
        )
        return Response(CartItemSerializer(item, context={"request": request}).data, status=status.HTTP_201_CREATED)

    def delete(self, request, product_id):
        item = get_object_or_404(CartItem, user=request.user, product_id=product_id)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PublicAnnouncementListView(generics.ListAPIView):
    serializer_class = AnnouncementSerializer
    permission_classes = [AllowAny]
    queryset = Announcement.objects.filter(is_published=True).select_related("author")


class CategorySuggestionListCreateView(generics.ListCreateAPIView):
    serializer_class = CategorySuggestionSerializer
    permission_classes = [IsAuthenticated, IsActiveMember]

    def get_queryset(self):
        suggestions = CategorySuggestion.objects.select_related("requester")
        if SupportConversationListCreateView.is_support_admin(self.request.user):
            return suggestions
        return suggestions.filter(requester=self.request.user)


class SupportConversationListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsActiveMember]

    @staticmethod
    def is_support_admin(user):
        return bool(
            user.is_staff
            and (user.is_superuser or user.admin_role in {"super_admin", "support_admin"})
        )

    def get(self, request):
        conversations = SupportConversation.objects.select_related("user").prefetch_related("messages__sender")
        if not self.is_support_admin(request.user):
            conversations = conversations.filter(user=request.user)
        return Response(SupportConversationSerializer(conversations, many=True).data)

    def post(self, request):
        serializer = SupportConversationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        body = serializers.CharField(max_length=4000).run_validation(request.data.get("message", ""))
        with transaction.atomic():
            conversation = serializer.save(user=request.user)
            SupportMessage.objects.create(conversation=conversation, sender=request.user, body=body)
            notify_active_superusers(
                Notification.Kind.SYSTEM,
                "New customer support message",
                f"{request.user.email} contacted SokoMtaani support.",
                conversation.pk,
            )
        conversation = SupportConversation.objects.prefetch_related("messages__sender").get(pk=conversation.pk)
        return Response(SupportConversationSerializer(conversation).data, status=status.HTTP_201_CREATED)


class SupportMessageListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsActiveMember]

    def get_conversation(self, request, conversation_id):
        conversation = get_object_or_404(
            SupportConversation.objects.select_related("user").prefetch_related("messages__sender"),
            pk=conversation_id,
        )
        if conversation.user_id != request.user.pk and not SupportConversationListCreateView.is_support_admin(request.user):
            raise PermissionDenied("You do not have access to this support conversation.")
        return conversation

    def get(self, request, conversation_id):
        conversation = self.get_conversation(request, conversation_id)
        return Response(SupportMessageSerializer(conversation.messages.all(), many=True).data)

    def post(self, request, conversation_id):
        conversation = self.get_conversation(request, conversation_id)
        body = serializers.CharField(max_length=4000).run_validation(request.data.get("body", ""))
        message = SupportMessage.objects.create(conversation=conversation, sender=request.user, body=body)
        conversation.save(update_fields=("updated_at",))
        if conversation.user_id != request.user.pk:
            create_notification(
                conversation.user,
                Notification.Kind.SYSTEM,
                "SokoMtaani support replied",
                body[:500],
                conversation.pk,
            )
        else:
            notify_active_superusers(
                Notification.Kind.SYSTEM,
                "New customer support reply",
                f"{request.user.email} replied to a support conversation.",
                conversation.pk,
            )
        return Response(SupportMessageSerializer(message).data, status=status.HTTP_201_CREATED)

class HelpfulVoteView(APIView):
    permission_classes = [IsAuthenticated, IsActiveMember]

    @extend_schema(request=None, responses=HelpfulVoteResponseSerializer)
    def post(self, request, product_id, comment_id):
        comment = get_object_or_404(Comment, pk=comment_id, product_id=product_id, is_visible=True)
        HelpfulVote.objects.get_or_create(user=request.user, comment=comment)
        return Response({"detail": "Vote recorded."}, status=status.HTTP_201_CREATED)


class ProductFavoriteStatusView(APIView):
    permission_classes = [IsAuthenticated, IsActiveMember]

    def get(self, request, product_id):
        return Response({"is_favorite": Favorite.objects.filter(user=request.user, product_id=product_id).exists()})
