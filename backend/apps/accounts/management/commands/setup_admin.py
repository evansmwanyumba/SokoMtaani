import os
from django.core.management.base import BaseCommand
from apps.accounts.models import AdminRole, User, UserRole


class Command(BaseCommand):
    help = "Automatically creates or promotes a super administrator using environment variables."

    def handle(self, *args, **options):
        email = os.getenv("DJANGO_SUPERUSER_EMAIL", "").strip()
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD", "").strip()

        if not email or not password:
            self.stdout.write(
                "DJANGO_SUPERUSER_EMAIL or DJANGO_SUPERUSER_PASSWORD not set; skipping setup_admin."
            )
            return

        normalized_email = User.objects.normalize_address(email)
        user = User.objects.filter(email=normalized_email).first()

        if user:
            user.is_superuser = True
            user.is_staff = True
            user.role = UserRole.ADMINISTRATOR
            user.admin_role = AdminRole.SUPER_ADMIN
            user.is_admin_approved = True
            user.is_active = True
            user.set_password(password)
            user.save()
            self.stdout.write(
                f"Super administrator {normalized_email} updated with configured credentials."
            )
        else:
            User.objects.create_superuser(
                email=normalized_email,
                password=password,
                first_name="Super",
                last_name="Admin",
            )
            self.stdout.write(
                f"Super administrator {normalized_email} created successfully."
            )
