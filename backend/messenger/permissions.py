import os

from rest_framework.permissions import BasePermission


class IsSecurityAdmin(BasePermission):
    """Foundation permission for admin-only security analysis capabilities."""

    message = "You must be a designated security admin to access this resource."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if not user.is_staff:
            return False

        required_group = os.getenv("SECURITY_ADMIN_GROUP", "security_admin").strip() or "security_admin"
        return user.groups.filter(name=required_group).exists()
