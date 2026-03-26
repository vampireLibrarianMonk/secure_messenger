import os

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

class Command(BaseCommand):
    help = "Bootstrap first admin user from environment variables in an idempotent way."

    def handle(self, *args, **options):
        enabled = os.getenv("BOOTSTRAP_ADMIN_ENABLED", "0") == "1"
        if not enabled:
            return

        username = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "").strip()
        email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip()
        password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
        group_name = os.getenv("BOOTSTRAP_ADMIN_GROUP", "security_admin").strip() or "security_admin"

        if not username or not email or not password:
            raise CommandError(
                "Missing required bootstrap admin env vars: "
                "BOOTSTRAP_ADMIN_USERNAME, BOOTSTRAP_ADMIN_EMAIL, BOOTSTRAP_ADMIN_PASSWORD"
            )

        existing_admin = User.objects.filter(is_superuser=True).exists()

        with transaction.atomic():
            user = User.objects.filter(username=username).first()
            created = False
            if user is None:
                user = User.objects.filter(email=email).first()

            if user is None:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    is_staff=True,
                    is_superuser=True,
                    is_active=True,
                )
                created = True
            else:
                # Idempotent privilege reconciliation for pre-existing principal.
                user.username = username
                user.email = email
                user.is_staff = True
                user.is_superuser = True
                user.is_active = True
                user.save(update_fields=["username", "email", "is_staff", "is_superuser", "is_active"])

            group, _ = Group.objects.get_or_create(name=group_name)
            user.groups.add(group)

        _ = existing_admin  # kept for future policy hooks; intentionally no admin-specific log output
        _ = created
