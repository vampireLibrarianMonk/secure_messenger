import os

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
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
from .permissions import IsSecurityAdmin


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
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


class AdminSecurityBootstrapStatusView(APIView):
    permission_classes = [IsSecurityAdmin]

    def get(self, request):
        required_group = os.getenv("SECURITY_ADMIN_GROUP", "security_admin").strip() or "security_admin"
        return Response(
            {
                "admin_security_access": "ok",
                "required_group": required_group,
                "active_superusers": User.objects.filter(is_superuser=True, is_active=True).count(),
                "bootstrap_enabled": os.getenv("BOOTSTRAP_ADMIN_ENABLED", "0") == "1",
            }
        )


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
    "AdminSecurityBootstrapStatusView",
]
