from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import (
    Attachment,
    Channel,
    Conversation,
    ConversationMember,
    Device,
    MessageEnvelope,
    SessionEvent,
    Workspace,
    WorkspaceMembership,
)
from .serializers import (
    AttachmentSerializer,
    ChannelSerializer,
    ConversationMemberSerializer,
    ConversationSerializer,
    DeviceSerializer,
    MessageEnvelopeSerializer,
    SessionEventSerializer,
    UserRegistrationSerializer,
    WorkspaceMembershipSerializer,
    WorkspaceSerializer,
)


def _configured_admin_usernames() -> set[str]:
    return {
        value.strip()
        for value in settings.TEST_LAB_ADMIN_USERNAMES
        if value and value.strip()
    }


def _configured_test_usernames() -> set[str]:
    return {
        value.strip()
        for value in settings.TEST_LAB_TEST_USER_USERNAMES
        if value and value.strip()
    }


def _is_security_admin_user(user: User) -> bool:
    return bool(user.is_staff or user.username in _configured_admin_usernames())


def _is_test_user_account(user: User) -> bool:
    configured = _configured_test_usernames()
    return bool(user.username in configured or user.username.startswith("test_user_"))


def _test_user_limit() -> int:
    if settings.TEST_LAB_FEATURE_FLAGS.get("group_testing_enabled", False):
        return int(settings.TEST_LAB_POLICY_LIMITS["max_active_test_users_group_enabled"])
    return int(settings.TEST_LAB_POLICY_LIMITS["max_active_test_users_default"])


def _governance_snapshot() -> dict:
    active_users = User.objects.filter(is_active=True)
    configured_admins = _configured_admin_usernames()

    active_admins = list(
        active_users.filter(is_staff=True) | active_users.filter(username__in=configured_admins)
    )
    # Remove duplicates from the OR query.
    active_admins_unique = {user.id: user for user in active_admins}.values()

    active_test_users = [user for user in active_users if _is_test_user_account(user)]

    admin_limit = int(settings.TEST_LAB_POLICY_LIMITS["max_active_admins"])
    test_user_limit = _test_user_limit()

    return {
        "active_admin_accounts": len(active_admins_unique),
        "max_active_admins": admin_limit,
        "active_test_users": len(active_test_users),
        "max_active_test_users": test_user_limit,
        "group_testing_slot_enabled": bool(settings.TEST_LAB_FEATURE_FLAGS.get("group_testing_enabled", False)),
        "group_testing_slot_usage": max(0, len(active_test_users) - int(settings.TEST_LAB_POLICY_LIMITS["max_active_test_users_default"])),
        "admin_limit_compliant": len(active_admins_unique) <= admin_limit,
        "test_user_limit_compliant": len(active_test_users) <= test_user_limit,
        "active_admin_usernames": sorted(user.username for user in active_admins_unique),
        "active_test_usernames": sorted(user.username for user in active_test_users),
    }


def _audit_governance_event(actor: User, action: str, metadata: dict | None = None) -> None:
    SessionEvent.objects.create(
        user=actor,
        event_type=SessionEvent.EVENT_REVOKE,
        metadata={
            "category": "test_lab_governance",
            "action": action,
            **(metadata or {}),
        },
    )


def _is_test_lab_operator(user: User) -> bool:
    return bool(_is_security_admin_user(user) or _is_test_user_account(user))


def _contains_prohibited_output(value) -> bool:
    prohibited_markers = (
        "plaintext",
        "decrypted",
        "private_key",
        "raw_key",
        "token",
        "password",
        "media_payload",
        "secret",
    )

    if isinstance(value, dict):
        for key, nested in value.items():
            if any(marker in str(key).lower() for marker in prohibited_markers):
                return True
            if _contains_prohibited_output(nested):
                return True
        return False
    if isinstance(value, list):
        return any(_contains_prohibited_output(item) for item in value)
    return any(marker in str(value).lower() for marker in prohibited_markers)


def _extract_test_lab_artifact_events(user: User) -> list[SessionEvent]:
    is_admin = _is_security_admin_user(user)
    queryset = SessionEvent.objects.filter(event_type=SessionEvent.EVENT_REVOKE).select_related("user").order_by("-created_at")
    events: list[SessionEvent] = []
    for event in queryset:
        metadata = event.metadata or {}
        if metadata.get("category") != "test_lab_run_artifact":
            continue
        if is_admin or event.user_id == user.id:
            events.append(event)
    return events


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        requested_username = str(request.data.get("username", "")).strip()
        if requested_username and _is_test_user_account(User(username=requested_username)):
            raise ValidationError("Test-user accounts must be managed through admin test-lab governance controls.")

        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": {"id": user.id, "username": user.username, "email": user.email},
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


class LogoutView(APIView):
    def post(self, request):
        refresh = request.data.get("refresh")
        if refresh:
            try:
                token = RefreshToken(refresh)
                token.blacklist()
            except Exception:
                pass
        SessionEvent.objects.create(user=request.user, event_type=SessionEvent.EVENT_LOGOUT, metadata={})
        return Response({"detail": "Logged out."})


class MeView(APIView):
    def get(self, request):
        return Response(
            {
                "id": request.user.id,
                "username": request.user.username,
                "email": request.user.email,
            }
        )


class DeviceViewSet(viewsets.ModelViewSet):
    serializer_class = DeviceSerializer

    def get_queryset(self):
        return Device.objects.filter(user=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def directory(self, request):
        username = request.query_params.get("username")
        if not username:
            return Response({"detail": "username query param is required"}, status=status.HTTP_400_BAD_REQUEST)
        user = get_object_or_404(User, username=username)
        devices = Device.objects.filter(user=user).order_by("-created_at")
        return Response(DeviceSerializer(devices, many=True).data)


class WorkspaceViewSet(viewsets.ModelViewSet):
    serializer_class = WorkspaceSerializer

    def get_queryset(self):
        return Workspace.objects.filter(memberships__user=self.request.user).distinct().order_by("name")

    def perform_create(self, serializer):
        workspace = serializer.save(created_by=self.request.user)
        WorkspaceMembership.objects.create(workspace=workspace, user=self.request.user, role=WorkspaceMembership.ROLE_OWNER)

    @action(detail=True, methods=["get", "post"], url_path="members")
    def members(self, request, pk=None):
        workspace = self.get_object()
        if request.method == "GET":
            memberships = workspace.memberships.select_related("user").all()
            return Response(WorkspaceMembershipSerializer(memberships, many=True).data)

        username = request.data.get("username")
        role = request.data.get("role", WorkspaceMembership.ROLE_MEMBER)
        user = get_object_or_404(User, username=username)
        membership, _ = WorkspaceMembership.objects.get_or_create(
            workspace=workspace, user=user, defaults={"role": role}
        )
        if membership.role != role:
            membership.role = role
            membership.save(update_fields=["role", "updated_at"])
        return Response(WorkspaceMembershipSerializer(membership).data, status=status.HTTP_201_CREATED)


class ChannelViewSet(viewsets.ModelViewSet):
    serializer_class = ChannelSerializer

    def get_queryset(self):
        queryset = Channel.objects.filter(workspace__memberships__user=self.request.user).distinct().order_by("name")
        workspace = self.request.query_params.get("workspace")
        if workspace:
            queryset = queryset.filter(workspace_id=workspace)
        return queryset

    def perform_create(self, serializer):
        channel = serializer.save(created_by=self.request.user)
        conversation = Conversation.objects.create(
            workspace=channel.workspace,
            channel=channel,
            kind=Conversation.TYPE_CHANNEL,
            title=channel.name,
            created_by=self.request.user,
        )
        members = WorkspaceMembership.objects.filter(workspace=channel.workspace).values_list("user_id", flat=True)
        ConversationMember.objects.bulk_create(
            [ConversationMember(conversation=conversation, user_id=user_id) for user_id in members],
            ignore_conflicts=True,
        )


class ConversationViewSet(viewsets.ModelViewSet):
    serializer_class = ConversationSerializer

    def get_queryset(self):
        return Conversation.objects.filter(members__user=self.request.user).distinct().order_by("-updated_at")

    def perform_create(self, serializer):
        conversation = serializer.save(created_by=self.request.user)
        member_ids = self.request.data.get("member_ids") or []
        member_ids = {int(uid) for uid in member_ids} | {self.request.user.id}

        member_usernames = self.request.data.get("member_usernames") or []
        if member_usernames:
            users = User.objects.filter(username__in=member_usernames).values_list("id", flat=True)
            member_ids = member_ids | set(users)

        if len(member_ids) <= 1:
            raise ValidationError("Conversation must include at least one other valid user.")

        ConversationMember.objects.bulk_create(
            [ConversationMember(conversation=conversation, user_id=user_id) for user_id in member_ids],
            ignore_conflicts=True,
        )

    def destroy(self, request, *args, **kwargs):
        conversation = self.get_object()
        if conversation.created_by_id != request.user.id:
            return Response(
                {"detail": "Only conversation creator can delete the conversation."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["get", "post"], url_path="members")
    def members(self, request, pk=None):
        conversation = self.get_object()
        if request.method == "GET":
            members = conversation.members.select_related("user")
            return Response(ConversationMemberSerializer(members, many=True).data)

        user_id = request.data.get("user")
        member = ConversationMember.objects.create(conversation=conversation, user_id=user_id)
        return Response(ConversationMemberSerializer(member).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="leave")
    def leave(self, request, pk=None):
        conversation = self.get_object()
        deleted, _ = ConversationMember.objects.filter(conversation=conversation, user=request.user).delete()
        if deleted == 0:
            return Response({"detail": "Not a member."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Left conversation."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="nuke")
    def nuke(self, request, pk=None):
        conversation = self.get_object()
        if conversation.kind != Conversation.TYPE_DM:
            return Response({"detail": "Nuke is only allowed for 1:1 DM conversations."}, status=status.HTTP_400_BAD_REQUEST)
        if not ConversationMember.objects.filter(conversation=conversation, user=request.user).exists():
            return Response({"detail": "Not a member of this conversation."}, status=status.HTTP_403_FORBIDDEN)
        conversation.delete()
        return Response({"detail": "Conversation nuked."}, status=status.HTTP_200_OK)


class MessageEnvelopeViewSet(viewsets.ModelViewSet):
    serializer_class = MessageEnvelopeSerializer

    def get_queryset(self):
        queryset = (
            MessageEnvelope.objects.filter(conversation__members__user=self.request.user)
            .select_related("sender", "sender_device")
            .prefetch_related("attachments")
            .distinct()
            .order_by("created_at")
        )
        conversation = self.request.query_params.get("conversation")
        if conversation:
            queryset = queryset.filter(conversation_id=conversation)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversation = serializer.validated_data["conversation"]
        if not ConversationMember.objects.filter(conversation=conversation, user=request.user).exists():
            return Response({"detail": "Not a member of this conversation."}, status=status.HTTP_403_FORBIDDEN)

        message = serializer.save(sender=request.user)
        payload = MessageEnvelopeSerializer(message).data
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"conversation_{conversation.id}",
            {"type": "chat.message", "message": payload},
        )
        headers = self.get_success_headers(serializer.data)
        return Response(payload, status=status.HTTP_201_CREATED, headers=headers)


class AttachmentViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = AttachmentSerializer
    parser_classes = [MultiPartParser]

    def get_queryset(self):
        return Attachment.objects.filter(message__conversation__members__user=self.request.user).distinct().order_by("-created_at")

    def perform_create(self, serializer):
        blob = self.request.FILES["blob"]
        serializer.save(uploaded_by=self.request.user, size=blob.size)


class SessionEventViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = SessionEventSerializer

    def get_queryset(self):
        return SessionEvent.objects.filter(user=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class PresenceView(APIView):
    def post(self, request):
        device_id = request.data.get("device_id")
        if device_id:
            from django.utils import timezone

            Device.objects.filter(id=device_id, user=request.user).update(last_seen_at=timezone.now())
        return Response({"status": "ok"})


class TestLabBootstrapView(APIView):
    """Bootstrap contract for test-lab role/flag gating and governance status."""

    def get(self, request):
        is_security_admin = _is_security_admin_user(request.user)
        is_test_user = _is_test_user_account(request.user)

        current_env = settings.TEST_LAB_ENV
        env_allowed = current_env in settings.TEST_LAB_ALLOWED_ENVIRONMENTS
        governance = _governance_snapshot()
        can_access_test_lab = bool(
            (is_security_admin or is_test_user)
            and env_allowed
            and settings.TEST_LAB_FEATURE_FLAGS.get("test_menu_enabled", False)
            and settings.TEST_LAB_FEATURE_FLAGS.get("synthetic_scenarios_enabled", False)
            and governance["admin_limit_compliant"]
            and governance["test_user_limit_compliant"]
        )

        roles = ["ordinary_user"]
        if is_test_user:
            roles.append("test_user")
        if is_security_admin:
            roles.append("security_admin")

        return Response(
            {
                "roles": roles,
                "is_security_admin": is_security_admin,
                "can_access_test_lab": can_access_test_lab,
                "environment": {
                    "current": current_env,
                    "allowed": settings.TEST_LAB_ALLOWED_ENVIRONMENTS,
                    "is_allowed": env_allowed,
                },
                "feature_flags": settings.TEST_LAB_FEATURE_FLAGS,
                "policy_limits": settings.TEST_LAB_POLICY_LIMITS,
                "governance_status": governance,
                "stage": "stage_10_hardening",
            }
        )


class TestLabRunArtifactView(APIView):
    """Stage 6+ synthetic run artifact persistence/review without plaintext exposure."""

    def _assert_operator(self, request):
        if not _is_test_lab_operator(request.user):
            raise PermissionDenied("Only security admins or dedicated test users can access test-lab artifacts.")

    def get(self, request):
        self._assert_operator(request)
        run_id = str(request.query_params.get("run_id", "")).strip()

        events = _extract_test_lab_artifact_events(request.user)

        if run_id:
            for event in events:
                run_data = (event.metadata or {}).get("run", {})
                if str(run_data.get("run_id", "")).strip() == run_id:
                    return Response(
                        {
                            "id": event.id,
                            "run": run_data,
                            "created_at": event.created_at,
                            "created_by": event.user.username,
                        }
                    )
            return Response({"detail": "Run artifact not found."}, status=status.HTTP_404_NOT_FOUND)

        summaries = []
        for event in events[:100]:
            run_data = (event.metadata or {}).get("run", {})
            summaries.append(
                {
                    "id": event.id,
                    "run_id": run_data.get("run_id"),
                    "scenario": run_data.get("scenario"),
                    "result": run_data.get("result"),
                    "state": run_data.get("state"),
                    "duration_ms": run_data.get("duration_ms"),
                    "warnings": run_data.get("warnings"),
                    "created_at": event.created_at,
                    "created_by": event.user.username,
                }
            )
        return Response({"runs": summaries})

    def post(self, request):
        self._assert_operator(request)
        payload = request.data or {}
        run = payload.get("run") if isinstance(payload, dict) else None
        if not isinstance(run, dict):
            raise ValidationError("run payload is required.")

        run_id = str(run.get("run_id", "")).strip()
        scenario = str(run.get("scenario", "")).strip()
        result = str(run.get("result", "")).strip()
        if not run_id or not scenario or not result:
            raise ValidationError("run_id, scenario, and result are required.")

        if _contains_prohibited_output(run):
            raise ValidationError("Artifact payload contains prohibited plaintext/secret fields.")

        SessionEvent.objects.create(
            user=request.user,
            event_type=SessionEvent.EVENT_REVOKE,
            metadata={
                "category": "test_lab_run_artifact",
                "run": run,
            },
        )
        return Response({"detail": "Run artifact stored."}, status=status.HTTP_201_CREATED)


class TestLabTestUserManagementView(APIView):
    """Controlled Stage 4 pathway for activating/deactivating pre-provisioned test users."""

    def _assert_security_admin(self, request):
        if not _is_security_admin_user(request.user):
            raise PermissionDenied("Only security admins can manage test users.")

    def get(self, request):
        self._assert_security_admin(request)
        users = [
            {
                "id": user.id,
                "username": user.username,
                "is_active": user.is_active,
                "is_test_user": _is_test_user_account(user),
            }
            for user in User.objects.order_by("username")
            if _is_test_user_account(user)
        ]
        return Response({"users": users, "governance_status": _governance_snapshot()})

    @transaction.atomic
    def post(self, request):
        self._assert_security_admin(request)
        action = str(request.data.get("action", "")).strip().lower()
        username = str(request.data.get("username", "")).strip()
        if not action or not username:
            raise ValidationError("Both action and username are required.")

        if not (username.startswith("test_user_") or username in _configured_test_usernames()):
            raise ValidationError("Managed test-user usernames must start with 'test_user_' or be configured test users.")

        if action == "activate":
            user = get_object_or_404(User, username=username)
            if not _is_test_user_account(user):
                raise ValidationError("Target account is not a managed pre-provisioned test user.")

            active_test_users = [user for user in User.objects.filter(is_active=True) if _is_test_user_account(user)]
            limit = _test_user_limit()

            was_active_test_user = bool(user.is_active)

            if not was_active_test_user and len(active_test_users) >= limit:
                raise ValidationError(f"Test-user limit reached: {len(active_test_users)} / {limit} active.")

            user.is_active = True
            user.save(update_fields=["is_active"])

            _audit_governance_event(
                request.user,
                "test_user_activated",
                {
                    "target_username": username,
                    "governance_status": _governance_snapshot(),
                },
            )
            return Response(
                {
                    "detail": "Pre-provisioned test user activated.",
                    "username": user.username,
                    "governance_status": _governance_snapshot(),
                },
                status=status.HTTP_200_OK,
            )

        if action == "deactivate":
            user = get_object_or_404(User, username=username)
            if not _is_test_user_account(user):
                raise ValidationError("Target account is not a managed pre-provisioned test user.")
            if not user.is_active:
                return Response({"detail": "Test user already inactive.", "governance_status": _governance_snapshot()})

            user.is_active = False
            user.save(update_fields=["is_active"])
            _audit_governance_event(
                request.user,
                "test_user_deactivated",
                {
                    "target_username": username,
                    "governance_status": _governance_snapshot(),
                },
            )
            return Response({"detail": "Test user deactivated.", "governance_status": _governance_snapshot()})

        raise ValidationError("Unsupported action. Use 'activate' or 'deactivate'.")


__all__ = [
    "RegisterView",
    "LogoutView",
    "MeView",
    "TokenObtainPairView",
    "TokenRefreshView",
    "DeviceViewSet",
    "WorkspaceViewSet",
    "ChannelViewSet",
    "ConversationViewSet",
    "MessageEnvelopeViewSet",
    "AttachmentViewSet",
    "SessionEventViewSet",
    "PresenceView",
    "TestLabBootstrapView",
    "TestLabTestUserManagementView",
    "TestLabRunArtifactView",
]
