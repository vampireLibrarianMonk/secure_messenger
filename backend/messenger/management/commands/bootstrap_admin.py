import os
import logging

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from messenger.models import SecurityAdminAccountState


logger = logging.getLogger("security.bootstrap")

class Command(BaseCommand):
    help = "Bootstrap first admin user from environment variables in an idempotent way."

    def handle(self, *args, **options):
        enabled = os.getenv("BOOTSTRAP_ADMIN_ENABLED", "0") == "1"
        if not enabled:
            logger.info("bootstrap_admin_skipped_disabled", extra={"actor": "bootstrap_process"})
            return

        username = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "").strip()
        email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip()
        password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
        group_name = os.getenv("BOOTSTRAP_ADMIN_GROUP", "security_admin").strip() or "security_admin"

        if not username or not email or not password:
            logger.error(
                "bootstrap_admin_failed_missing_env",
                extra={"actor": "bootstrap_process", "username": username, "email": email},
            )
            raise CommandError(
                "Missing required bootstrap admin env vars: "
                "BOOTSTRAP_ADMIN_USERNAME, BOOTSTRAP_ADMIN_EMAIL, BOOTSTRAP_ADMIN_PASSWORD"
            )

        existing_admin = User.objects.filter(is_superuser=True).exists()
        allow_reconcile = os.getenv("BOOTSTRAP_ADMIN_ALLOW_RECONCILE", "0") == "1"

        if existing_admin and not allow_reconcile:
            logger.info(
                "bootstrap_admin_skipped_existing_admin",
                extra={"actor": "bootstrap_process", "username": username, "email": email},
            )
            return

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

            state, _ = SecurityAdminAccountState.objects.get_or_create(user=user)
            state.must_reset_password = True
            state.last_bootstrap_at = timezone.now()
            state.bootstrap_source = "docker_bootstrap"
            state.save(update_fields=["must_reset_password", "last_bootstrap_at", "bootstrap_source", "updated_at"])

        logger.info(
            "bootstrap_admin_success",
            extra={
                "actor": "bootstrap_process",
                "username": username,
                "email": email,
                "was_created": created,
                "reconciled": not created,
            },
        )
