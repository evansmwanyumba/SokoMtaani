from django.urls import path

from .views import (
    MyProfileView,
    MySellerProfileView,
    MySellerProductsView,
    SellerAnalyticsView,
    PublicSellerDetailView,
    PublicSellerListView,
    PhoneVerificationConfirmView,
    PhoneVerificationRequestView,
    SellerActivationView,
)

urlpatterns = [
    path("users/me/", MyProfileView.as_view(), name="my-profile"),
    path("sellers/", PublicSellerListView.as_view(), name="public-sellers"),
    path("sellers/<uuid:user_id>/", PublicSellerDetailView.as_view(), name="public-seller-detail"),
    path("sellers/me/", MySellerProfileView.as_view(), name="my-seller-profile"),
    path("sellers/me/products/", MySellerProductsView.as_view(), name="my-seller-products"),
    path("analytics/seller/overview/", SellerAnalyticsView.as_view(), name="seller-analytics"),
    path("sellers/phone-verification/", PhoneVerificationRequestView.as_view(), name="phone-verification"),
    path("sellers/phone-verification/confirm/", PhoneVerificationConfirmView.as_view(), name="phone-verification-confirm"),
    path("sellers/activate/", SellerActivationView.as_view(), name="seller-activate"),
]
