from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User, UserRole
from apps.categories.models import Category
from apps.messaging.models import Conversation, Message
from apps.products.models import Product, ProductCondition
from apps.profiles.models import SellerProfile, UserProfile


class Command(BaseCommand):
    help = "Create clearly labeled local demo users, categories, listings and a conversation."

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo data can only be seeded when DEBUG=True.")

        categories = {
            name: Category.objects.get_or_create(
                slug=slug,
                defaults={"name": name, "description": "Local development sample category."},
            )[0]
            for name, slug in (
                ("Home & Living", "demo-home-living"),
                ("Phones & Electronics", "demo-phones-electronics"),
                ("Fashion", "demo-fashion"),
            )
        }

        buyer = self.get_demo_user("buyer.demo@example.test", "Demo", "Buyer")
        sellers = [
            self.get_demo_user("seller.home@example.test", "Amina", "Demo Seller"),
            self.get_demo_user("seller.tech@example.test", "Brian", "Demo Seller"),
        ]
        UserProfile.objects.get_or_create(
            user=buyer,
            defaults={"county": "Nairobi", "town": "Nairobi", "neighbourhood": "Westlands"},
        )

        for seller, display_name, phone, bio, county, town in (
            (sellers[0], "Amina's Demo Finds", "+254000000001", "A sample home and living seller.", "Nairobi", "Nairobi"),
            (sellers[1], "Brian's Demo Tech", "+254000000002", "A sample electronics seller.", "Kiambu", "Kiambu"),
        ):
            SellerProfile.objects.get_or_create(
                user=seller,
                defaults={
                    "display_name": display_name,
                    "phone_number": phone,
                    "phone_verified_at": timezone.now(),
                    "bio": bio,
                    "county": county,
                    "town": town,
                    "neighbourhood": "Demo neighbourhood",
                    "allow_email": True,
                },
            )

        products = []
        samples = (
            (sellers[0], categories["Home & Living"], "Demo rattan accent chair", "A sample listing for local UI testing.", "12500.00", ProductCondition.GENTLY_USED, "Nairobi", "Nairobi"),
            (sellers[0], categories["Fashion"], "Demo handmade tote bag", "A sample locally made accessory listing.", "1800.00", ProductCondition.NEW, "Nairobi", "Nairobi"),
            (sellers[1], categories["Phones & Electronics"], "Demo wireless headphones", "A sample electronics listing. This is not a real offer.", "4200.00", ProductCondition.LIKE_NEW, "Kiambu", "Kiambu"),
        )
        for seller, category, name, description, price, condition, county, town in samples:
            product, _ = Product.objects.get_or_create(
                seller=seller,
                name=name,
                defaults={
                    "category": category,
                    "description": description,
                    "price": price,
                    "condition": condition,
                    "county": county,
                    "town": town,
                    "neighbourhood": "Demo neighbourhood",
                    "admin_created": True,
                },
            )
            products.append(product)

        conversation, created = Conversation.objects.get_or_create(
            buyer=buyer,
            seller=sellers[0],
            product=products[0],
            defaults={"admin_created": True},
        )
        if created:
            Message.objects.create(
                conversation=conversation,
                sender=buyer,
                content="This is a demo conversation for local testing.",
            )

        self.stdout.write(self.style.SUCCESS(
            "Demo data is ready: 1 buyer, 2 sellers, 3 listings, and 1 sample conversation."
        ))
        self.stdout.write("Demo accounts use reserved .test email addresses and have no usable passwords.")

    @staticmethod
    def get_demo_user(email, first_name, last_name):
        user = User.objects.filter(email=email).first()
        if user is not None:
            return user
        return User.objects.create_user(
            email=email,
            password=None,
            first_name=first_name,
            last_name=last_name,
            role=UserRole.BUYER,
            is_active=True,
            is_admin_approved=True,
            is_demo_account=True,
        )
