from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BlockDetailView,
    BlockListCreateView,
    FavoriteDeleteView,
    FavoriteListCreateView,
    HelpfulVoteView,
    CartView,
    CategorySuggestionListCreateView,
    PublicSiteInfoView,
    PublicAnnouncementListView,
    ReportCreateView,
    SellerReviewViewSet,
    SupportConversationListCreateView,
    SupportMessageListCreateView,
)
from .admin_api import AdminActionView, AdminMessageEvidenceView, AdminObjectUpdateView, AdminResourceView

router = DefaultRouter()
router.register(r"sellers/(?P<seller_id>[0-9a-f-]+)/reviews", SellerReviewViewSet, basename="seller-reviews")

urlpatterns = [
    path("site-info/", PublicSiteInfoView.as_view(), name="public-site-info"),
    path("announcements/", PublicAnnouncementListView.as_view(), name="announcements"),
    path("cart/", CartView.as_view(), name="cart"),
    path("cart/<uuid:product_id>/", CartView.as_view(), name="cart-delete"),
    path("category-suggestions/", CategorySuggestionListCreateView.as_view(), name="category-suggestions"),
    path("support/conversations/", SupportConversationListCreateView.as_view(), name="support-conversations"),
    path(
        "support/conversations/<int:conversation_id>/messages/",
        SupportMessageListCreateView.as_view(),
        name="support-messages",
    ),
    path("favourites/", FavoriteListCreateView.as_view(), name="favourites"),
    path("favourites/<uuid:product_id>/", FavoriteDeleteView.as_view(), name="favourite-delete"),
    path("reports/", ReportCreateView.as_view(), name="report-create"),
    path("users/blocked/", BlockListCreateView.as_view(), name="blocked-users"),
    path("users/<uuid:user_id>/block/", BlockDetailView.as_view(), name="user-block"),
    path("admin/<str:resource>/", AdminResourceView.as_view(), name="admin-resource"),
    path("admin/<str:resource>/<str:object_id>/", AdminObjectUpdateView.as_view(), name="admin-resource-detail"),
    path("admin/<str:resource>/<str:object_id>/actions/", AdminActionView.as_view(), name="admin-action"),
    path("admin/message-reports/<uuid:report_id>/evidence/", AdminMessageEvidenceView.as_view(), name="admin-message-evidence"),
    path(
        "products/<uuid:product_id>/comments/<uuid:comment_id>/helpful/",
        HelpfulVoteView.as_view(),
        name="comment-helpful",
    ),
    path("", include(router.urls)),
]
