import os

from rest_framework.permissions import BasePermission

from .models import SecurityAdminAccountState


def is_security_admin_user(user) -> bool:
    if not user or not user.is_authenticated:
        return False

    state = SecurityAdminAccountState.objects.filter(user=user).first()
    if state and state.must_reset_password:
        return False

    if user.is_superuser:
        return True
    if not user.is_staff:
        return False

    required_group = os.getenv("SECURITY_ADMIN_GROUP", "security_admin").strip() or "security_admin"
    return user.groups.filter(name=required_group).exists()


class IsSecurityAdmin(BasePermission):
    """Foundation permission for admin-only security analysis capabilities."""

    message = "You must be a designated security admin to access this resource."

    def has_permission(self, request, view):
        return is_security_admin_user(getattr(request, "user", None))
