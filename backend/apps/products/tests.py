from io import BytesIO
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework.test import APITestCase

from apps.categories.models import Category
from apps.community.models import Review
from apps.profiles.models import SellerProfile

from .models import Comment, Product, ProductCondition, ProductStatus


User = get_user_model()


def png_content():
    output = BytesIO()
    Image.new("RGB", (2, 2), color="green").save(output, format="PNG")
    return output.getvalue()


class MarketplaceApiTests(APITestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_dir.cleanup)
        self.override_media = override_settings(MEDIA_ROOT=Path(self.media_dir.name))
        self.override_media.enable()
        self.addCleanup(self.override_media.disable)

        self.seller = User.objects.create_user(
            email="seller@example.com",
            password="SafePassword!123",
            first_name="Amina",
            last_name="Wanjiku",
            is_email_verified=True,
        )
        SellerProfile.objects.create(
            user=self.seller,
            display_name="Amina Wanjiku",
            phone_number="+254712345678",
            phone_verified_at=timezone.now(),
        )
        self.category = Category.objects.create(name="Home & Living", slug="home-living")
        self.product = Product.objects.create(
            seller=self.seller,
            category=self.category,
            name="Teak chair",
            description="A sturdy chair for a living room.",
            price="18500.00",
            condition=ProductCondition.GENTLY_USED,
            county="Nairobi",
            town="Westlands",
        )

    def test_public_categories_include_active_listing_counts(self):
        response = self.client.get(reverse("category-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["name"], "Home & Living")
        self.assertEqual(response.data["results"][0]["count"], 1)

    def test_product_list_search_location_price_and_condition_filters(self):
        url = reverse("product-list")
        response = self.client.get(
            url,
            {
                "search": "sturdy",
                "county": "nairobi",
                "min_price": "10000",
                "max_price": "20000",
                "condition": "Gently used",
                "category": "Home & Living",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(self.product.id))

    def test_invalid_price_range_is_rejected(self):
        response = self.client.get(
            reverse("product-list"),
            {"min_price": "20000", "max_price": "10000"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("max_price", response.data)

    def test_product_creation_requires_verified_session_and_uses_request_user(self):
        self.client.force_authenticate(self.seller)
        response = self.client.post(
            reverse("product-list"),
            {
                "category": self.category.name,
                "name": "New basket",
                "description": "Handwoven basket.",
                "price": "1200",
                "condition": "New",
                "county": "Mombasa",
                "town": "Nyali",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        created = Product.objects.get(pk=response.data["id"])
        self.assertEqual(created.seller, self.seller)
        self.assertEqual(created.condition, ProductCondition.NEW)

    def test_unverified_user_cannot_create_product(self):
        user = User.objects.create_user(
            email="unverified@example.com",
            password="SafePassword!123",
            is_email_verified=False,
        )
        self.client.force_authenticate(user)

        response = self.client.post(
            reverse("product-list"),
            {
                "category": self.category.name,
                "name": "Listing",
                "description": "Details",
                "price": "100",
                "condition": "New",
                "county": "Nairobi",
                "town": "Westlands",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_product_image_upload_is_saved_and_returned(self):
        self.client.force_authenticate(self.seller)
        upload = SimpleUploadedFile("chair.png", png_content(), content_type="image/png")
        response = self.client.post(
            reverse("product-list"),
            {
                "category": self.category.name,
                "name": "Chair with photo",
                "description": "Details",
                "price": "200",
                "condition": "Like new",
                "county": "Nairobi",
                "town": "Westlands",
                "images": [upload],
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(len(response.data["images"]), 1)
        self.assertTrue(response.data["primary_image"].endswith(".png"))

    def test_comments_are_public_and_verified_users_can_post(self):
        url = reverse("product-comments", kwargs={"product_id": self.product.id})
        self.client.force_authenticate(self.seller)
        response = self.client.post(url, {"content": "Is collection available?"}, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Comment.objects.get().author, self.seller)
        self.assertEqual(self.client.get(url).data["results"][0]["content"], "Is collection available?")

    def test_seller_can_update_own_listing_but_not_another_sellers(self):
        other = User.objects.create_user(
            email="other@example.com",
            password="SafePassword!123",
            is_email_verified=True,
        )
        SellerProfile.objects.create(
            user=other,
            display_name="Other seller",
            phone_number="+254722345678",
            phone_verified_at=timezone.now(),
        )
        self.client.force_authenticate(other)
        response = self.client.patch(
            reverse("product-detail", kwargs={"pk": self.product.id}),
            {"price": "15000"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

        self.client.force_authenticate(self.seller)
        response = self.client.patch(
            reverse("product-detail", kwargs={"pk": self.product.id}),
            {"price": "15000"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.product.refresh_from_db()
        self.assertEqual(str(self.product.price), "15000.00")

    def test_inactive_listings_are_not_public_but_owner_can_retrieve_them(self):
        self.product.status = ProductStatus.PAUSED
        self.product.save(update_fields=["status"])
        detail_url = reverse("product-detail", kwargs={"pk": self.product.id})

        self.assertEqual(self.client.get(detail_url).status_code, 404)
        self.client.force_authenticate(self.seller)
        self.assertEqual(self.client.get(reverse("product-list")).data["count"], 0)
        self.assertEqual(self.client.get(detail_url).status_code, 200)

    def test_seller_can_change_listing_availability(self):
        self.client.force_authenticate(self.seller)
        response = self.client.post(
            reverse("product-availability", kwargs={"pk": self.product.id}),
            {"status": "paused"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, ProductStatus.PAUSED)

        response = self.client.post(
            reverse("product-availability", kwargs={"pk": self.product.id}),
            {"status": "not-a-status"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_rating_filter_uses_visible_seller_reviews(self):
        reviewer = User.objects.create_user(
            email="reviewer@example.com",
            password="Secure-test-Password1",
            is_email_verified=True,
        )
        Review.objects.create(
            reviewer=reviewer,
            seller=self.seller,
            rating=5,
            content="Good communication.",
        )

        response = self.client.get(reverse("product-list"), {"rating": "4.5"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["seller_rating"], 5.0)

        invalid = self.client.get(reverse("product-list"), {"rating": "5.5"})
        self.assertEqual(invalid.status_code, 400)

    def test_contact_methods_are_hidden_until_seller_opts_in(self):
        response = self.client.get(reverse("product-detail", kwargs={"pk": self.product.id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["phone"], "")

        self.seller.seller_profile.allow_whatsapp = True
        self.seller.seller_profile.save(update_fields=["allow_whatsapp", "updated_at"])
        response = self.client.get(reverse("product-detail", kwargs={"pk": self.product.id}))
        self.assertEqual(response.data["phone"], "+254712345678")
        self.assertTrue(response.data["contact_preferences"]["allow_whatsapp"])

    def test_product_detail_records_non_owner_views_for_seller_analytics(self):
        self.client.force_authenticate(self.seller)
        seller_view = self.client.get(reverse("product-detail", kwargs={"pk": self.product.id}))
        self.assertEqual(seller_view.status_code, 200)
        self.assertEqual(self.product.view_events.count(), 0)

        viewer = User.objects.create_user(
            email="viewer@example.com",
            password="Secure-test-Password1",
            is_email_verified=True,
        )
        self.client.force_authenticate(viewer)
        self.client.get(reverse("product-detail", kwargs={"pk": self.product.id}))

        analytics = self.client.get(reverse("seller-analytics"))
        self.assertEqual(analytics.status_code, 403)

        self.client.force_authenticate(self.seller)
        analytics = self.client.get(reverse("seller-analytics"))
        self.assertEqual(analytics.status_code, 200, analytics.data)
        self.assertEqual(analytics.data["views"], 1)
        self.assertEqual(analytics.data["unique_visitors"], 1)
