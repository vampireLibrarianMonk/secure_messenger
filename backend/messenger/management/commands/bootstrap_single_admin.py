import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create exactly one active admin account in an idempotent way."

    def add_arguments(self, parser):
        parser.add_argument("--username", type=str, default=None)
        parser.add_argument("--email", type=str, default=None)
        parser.add_argument("--password", type=str, default=None)

    def handle(self, *args, **options):
        User = get_user_model()

        username = (options.get("username") or os.getenv("TEST_LAB_ADMIN_USERNAME") or "").strip()
        email = (options.get("email") or os.getenv("TEST_LAB_ADMIN_EMAIL") or "").strip()
        password = (options.get("password") or os.getenv("TEST_LAB_ADMIN_PASSWORD") or "").strip()

        active_admins = list(User.objects.filter(is_staff=True, is_active=True).order_by("id"))

        if len(active_admins) > 1:
            names = ", ".join(admin.username for admin in active_admins)
            raise CommandError(
                "Single-admin policy violation: more than one active admin exists "
                f"({len(active_admins)} found: {names})."
            )

        if len(active_admins) == 1:
            existing = active_admins[0]
            if username and existing.username != username:
                raise CommandError(
                    "Single-admin policy prevents creating another admin. "
                    f"Existing admin is '{existing.username}', requested '{username}'."
                )
            self.stdout.write(self.style.SUCCESS(f"Single admin already present: {existing.username}"))
            return

        # No active admin exists yet; bootstrap one deterministically.
        if not username or not password:
            raise CommandError(
                "No active admin found. Provide TEST_LAB_ADMIN_USERNAME and TEST_LAB_ADMIN_PASSWORD "
                "(or --username/--password) to bootstrap the single admin account."
            )

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "is_active": True,
                "is_staff": True,
                "is_superuser": False,
            },
        )

        changed_fields = []
        if created:
            user.set_password(password)
            changed_fields = ["password"]
        else:
            if not user.is_active:
                user.is_active = True
                changed_fields.append("is_active")
            if not user.is_staff:
                user.is_staff = True
                changed_fields.append("is_staff")
            if email and user.email != email:
                user.email = email
                changed_fields.append("email")
            # Allow password reset during deterministic bootstrap attempts.
            user.set_password(password)
            changed_fields.append("password")

        if not user.email and email:
            user.email = email
            if "email" not in changed_fields:
                changed_fields.append("email")

        user.save()

        action = "created" if created else "updated/promoted"
        self.stdout.write(self.style.SUCCESS(f"Single admin {action}: {user.username}"))
