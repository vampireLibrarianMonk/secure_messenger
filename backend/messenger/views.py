import os
import json
import hashlib

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
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
    SecurityAnalysisAuditEvent,
    SecurityAdminAccountState,
    SecurityGapItem,
    SecurityLoggingFieldPolicy,
    SecurityNextTestItem,
    SecurityJourneyReport,
    SecurityJourneyStage,
    SecurityScopeCoverageItem,
    SecurityAnalysisRun,
    SecurityReportSnapshot,
    SecurityThreatModelItem,
    SecurityVerificationMatrixItem,
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
    SecurityAnalysisAuditEventSerializer,
    SecurityGapItemSerializer,
    SecurityLoggingFieldPolicySerializer,
    SecurityNextTestItemSerializer,
    SecurityJourneyReportSerializer,
    SecurityJourneyStageSerializer,
    SecurityScopeCoverageItemSerializer,
    SecurityAnalysisRunSerializer,
    SecurityReportSnapshotSerializer,
    SecurityThreatModelItemSerializer,
    SecurityVerificationMatrixItemSerializer,
    SessionEventSerializer,
    UserRegistrationSerializer,
    WorkspaceMembershipSerializer,
    WorkspaceSerializer,
)
from .permissions import IsSecurityAdmin, is_security_admin_user


REALITY_CHECK_KEYS = (
    "is_system_truly_e2ee_or_transport_only",
    "can_server_read_dm_bodies",
    "can_server_read_media",
    "can_push_notifications_leak_sensitive_content",
    "can_logs_backups_analytics_or_moderation_expose_plaintext",
    "can_admins_or_cloud_operators_access_secrets_or_session_data",
    "proof_required_before_claiming_secure",
)


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
        admin_state = SecurityAdminAccountState.objects.filter(user=request.user).first()
        return Response(
            {
                "id": request.user.id,
                "username": request.user.username,
                "email": request.user.email,
                "must_reset_password": bool(admin_state and admin_state.must_reset_password),
                "is_security_admin": is_security_admin_user(request.user),
            }
        )


class PasswordResetView(APIView):
    def post(self, request):
        old_password = request.data.get("old_password", "")
        new_password = request.data.get("new_password", "")

        if not request.user.check_password(old_password):
            return Response({"detail": "Current password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            validate_password(new_password, user=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)

        request.user.set_password(new_password)
        request.user.save(update_fields=["password"])

        state = SecurityAdminAccountState.objects.filter(user=request.user).first()
        if state and state.must_reset_password:
            state.must_reset_password = False
            state.save(update_fields=["must_reset_password", "updated_at"])

        return Response({"detail": "Password updated."}, status=status.HTTP_200_OK)


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


class SecurityJourneyReportViewSet(viewsets.ModelViewSet):
    serializer_class = SecurityJourneyReportSerializer
    permission_classes = [IsSecurityAdmin]

    def get_queryset(self):
        return (
            SecurityJourneyReport.objects.select_related("created_by")
            .prefetch_related("stages", "verification_items")
            .order_by("-created_at")
        )

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["get"], url_path="compiled")
    def compiled(self, request, pk=None):
        report = self.get_object()
        dm_stages = SecurityJourneyStageSerializer(report.stages.filter(flow_type=SecurityJourneyStage.FLOW_DM), many=True).data
        video_stages = SecurityJourneyStageSerializer(report.stages.filter(flow_type=SecurityJourneyStage.FLOW_VIDEO), many=True).data
        verification_matrix = SecurityVerificationMatrixItemSerializer(report.verification_items.all(), many=True).data
        logging_design = SecurityLoggingFieldPolicySerializer(report.logging_field_policies.all(), many=True).data
        threat_model = SecurityThreatModelItemSerializer(report.threat_items.all(), many=True).data
        top_gaps = SecurityGapItemSerializer(report.gap_items.all(), many=True).data
        next_tests = SecurityNextTestItemSerializer(report.next_test_items.all(), many=True).data

        reality_answers = {key: "unknown/unverified" for key in REALITY_CHECK_KEYS}
        reality_answers.update(report.reality_check_answers or {})

        payload = {
            "report_id": report.id,
            "executive_summary": report.executive_summary,
            "dm_stage_by_stage_journey": dm_stages,
            "video_stage_by_stage_journey": video_stages,
            "verification_matrix": verification_matrix,
            "scope_coverage": SecurityScopeCoverageItemSerializer(report.scope_coverage_items.all(), many=True).data,
            "logging_design": logging_design,
            "top_10_likely_security_gaps": top_gaps,
            "highest_value_next_tests": next_tests,
            "threat_model": threat_model,
            "reality_check_answers": reality_answers,
        }
        SecurityAnalysisAuditEvent.objects.create(
            actor=request.user,
            report=report,
            action=SecurityAnalysisAuditEvent.ACTION_COMPILED_VIEW,
            details={"report_id": report.id},
        )
        return Response(payload)

    @action(detail=True, methods=["get"], url_path="export")
    def export(self, request, pk=None):
        report = self.get_object()
        compiled_response = self.compiled(request, pk=pk)
        SecurityAnalysisAuditEvent.objects.create(
            actor=request.user,
            report=report,
            action=SecurityAnalysisAuditEvent.ACTION_EXPORT,
            details={"report_id": report.id, "format": "json"},
        )
        return compiled_response

    @action(detail=True, methods=["post"], url_path="snapshots")
    def snapshots(self, request, pk=None):
        report = self.get_object()
        compiled_response = self.compiled(request, pk=pk)
        payload = compiled_response.data
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        snapshot = SecurityReportSnapshot.objects.create(
            report=report,
            generated_by=request.user,
            snapshot_format=SecurityReportSnapshot.FORMAT_JSON,
            payload=payload,
            payload_sha256=digest,
            notes=request.data.get("notes", ""),
        )
        SecurityAnalysisAuditEvent.objects.create(
            actor=request.user,
            report=report,
            action=SecurityAnalysisAuditEvent.ACTION_SNAPSHOT_CREATE,
            details={"report_id": report.id, "snapshot_id": snapshot.id, "sha256": digest},
        )
        return Response(SecurityReportSnapshotSerializer(snapshot).data, status=status.HTTP_201_CREATED)


class SecurityReportSnapshotViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = SecurityReportSnapshotSerializer
    permission_classes = [IsSecurityAdmin]

    def get_queryset(self):
        queryset = SecurityReportSnapshot.objects.select_related("report", "generated_by").order_by("-created_at")
        report_id = self.request.query_params.get("report")
        if report_id:
            queryset = queryset.filter(report_id=report_id)
        return queryset

    @action(detail=True, methods=["get"], url_path="verify")
    def verify(self, request, pk=None):
        snapshot = self.get_object()
        payload_json = json.dumps(snapshot.payload, sort_keys=True, separators=(",", ":"))
        recomputed = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        return Response(
            {
                "snapshot_id": snapshot.id,
                "stored_sha256": snapshot.payload_sha256,
                "recomputed_sha256": recomputed,
                "match": snapshot.payload_sha256 == recomputed,
            }
        )


class SecurityJourneyStageViewSet(viewsets.ModelViewSet):
    serializer_class = SecurityJourneyStageSerializer
    permission_classes = [IsSecurityAdmin]

    def get_queryset(self):
        queryset = SecurityJourneyStage.objects.select_related("report").order_by("flow_type", "stage_number", "id")
        report_id = self.request.query_params.get("report")
        if report_id:
            queryset = queryset.filter(report_id=report_id)
        flow_type = self.request.query_params.get("flow_type")
        if flow_type:
            queryset = queryset.filter(flow_type=flow_type)
        return queryset


class SecurityScopeCoverageItemViewSet(viewsets.ModelViewSet):
    serializer_class = SecurityScopeCoverageItemSerializer
    permission_classes = [IsSecurityAdmin]

    def get_queryset(self):
        queryset = SecurityScopeCoverageItem.objects.select_related("report").order_by("area", "id")
        report_id = self.request.query_params.get("report")
        if report_id:
            queryset = queryset.filter(report_id=report_id)
        return queryset


class SecurityVerificationMatrixItemViewSet(viewsets.ModelViewSet):
    serializer_class = SecurityVerificationMatrixItemSerializer
    permission_classes = [IsSecurityAdmin]

    def get_queryset(self):
        queryset = SecurityVerificationMatrixItem.objects.select_related("report", "stage").order_by("created_at")
        report_id = self.request.query_params.get("report")
        if report_id:
            queryset = queryset.filter(report_id=report_id)
        return queryset


class SecurityLoggingFieldPolicyViewSet(viewsets.ModelViewSet):
    serializer_class = SecurityLoggingFieldPolicySerializer
    permission_classes = [IsSecurityAdmin]

    def get_queryset(self):
        queryset = SecurityLoggingFieldPolicy.objects.select_related("report").order_by("field_name")
        report_id = self.request.query_params.get("report")
        if report_id:
            queryset = queryset.filter(report_id=report_id)
        return queryset


class SecurityThreatModelItemViewSet(viewsets.ModelViewSet):
    serializer_class = SecurityThreatModelItemSerializer
    permission_classes = [IsSecurityAdmin]

    def get_queryset(self):
        queryset = SecurityThreatModelItem.objects.select_related("report").order_by("flow_type", "threat", "id")
        report_id = self.request.query_params.get("report")
        if report_id:
            queryset = queryset.filter(report_id=report_id)
        flow_type = self.request.query_params.get("flow_type")
        if flow_type:
            queryset = queryset.filter(flow_type=flow_type)
        return queryset


class SecurityGapItemViewSet(viewsets.ModelViewSet):
    serializer_class = SecurityGapItemSerializer
    permission_classes = [IsSecurityAdmin]

    def get_queryset(self):
        queryset = SecurityGapItem.objects.select_related("report").order_by("rank", "id")
        report_id = self.request.query_params.get("report")
        if report_id:
            queryset = queryset.filter(report_id=report_id)
        return queryset


class SecurityNextTestItemViewSet(viewsets.ModelViewSet):
    serializer_class = SecurityNextTestItemSerializer
    permission_classes = [IsSecurityAdmin]

    def get_queryset(self):
        queryset = SecurityNextTestItem.objects.select_related("report").order_by("priority", "id")
        report_id = self.request.query_params.get("report")
        if report_id:
            queryset = queryset.filter(report_id=report_id)
        return queryset


class SecurityAnalysisAuditEventViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = SecurityAnalysisAuditEventSerializer
    permission_classes = [IsSecurityAdmin]

    def get_queryset(self):
        queryset = SecurityAnalysisAuditEvent.objects.select_related("actor", "report").order_by("-created_at")
        report_id = self.request.query_params.get("report")
        if report_id:
            queryset = queryset.filter(report_id=report_id)
        action = self.request.query_params.get("action")
        if action:
            queryset = queryset.filter(action=action)
        return queryset


class SecurityAnalysisRunViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SecurityAnalysisRunSerializer
    permission_classes = [IsSecurityAdmin]

    def get_queryset(self):
        queryset = SecurityAnalysisRun.objects.select_related("report", "triggered_by").order_by("-created_at")
        report_id = self.request.query_params.get("report")
        if report_id:
            queryset = queryset.filter(report_id=report_id)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset


class SecurityRunView(APIView):
    permission_classes = [IsSecurityAdmin]

    def post(self, request):
        report_id = request.data.get("report_id")
        if not report_id:
            return Response({"detail": "report_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        report = get_object_or_404(SecurityJourneyReport, id=report_id)
        requested_checks = request.data.get("requested_checks", [])
        flow_type = request.data.get("flow_type", SecurityAnalysisRun.FLOW_BOTH)

        run = SecurityAnalysisRun.objects.create(
            report=report,
            triggered_by=request.user,
            flow_type=flow_type,
            requested_checks=requested_checks,
            status=SecurityAnalysisRun.STATUS_RUNNING,
            run_summary={"no_content_read_mode": True},
        )

        run.status = SecurityAnalysisRun.STATUS_COMPLETED
        run.run_summary = {
            "no_content_read_mode": True,
            "dm_stages": report.stages.filter(flow_type=SecurityJourneyStage.FLOW_DM).count(),
            "video_stages": report.stages.filter(flow_type=SecurityJourneyStage.FLOW_VIDEO).count(),
            "verification_items": report.verification_items.count(),
            "scope_items": report.scope_coverage_items.count(),
            "threat_items": report.threat_items.count(),
            "gap_items": report.gap_items.count(),
            "next_test_items": report.next_test_items.count(),
        }
        run.save(update_fields=["status", "run_summary", "updated_at"])

        SecurityAnalysisAuditEvent.objects.create(
            actor=request.user,
            report=report,
            action=SecurityAnalysisAuditEvent.ACTION_RUN_TRIGGERED,
            details={
                "report_id": report.id,
                "run_triggered": True,
                "no_content_read_mode": True,
                "requested_checks": requested_checks,
                "run_id": run.id,
            },
        )
        return Response(
            {
                "status": "accepted",
                "report_id": report.id,
                "run_id": run.id,
                "run_status": run.status,
                "no_content_read_mode": True,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class SecurityDashboardView(APIView):
    permission_classes = [IsSecurityAdmin]

    def get(self, request):
        report_id = request.query_params.get("report")
        report = None
        if report_id:
            report = get_object_or_404(SecurityJourneyReport, id=report_id)

        runs = SecurityAnalysisRun.objects.all()
        reports = SecurityJourneyReport.objects.all()
        gaps = SecurityGapItem.objects.all()
        if report is not None:
            runs = runs.filter(report=report)
            reports = reports.filter(id=report.id)
            gaps = gaps.filter(report=report)

        latest_run = runs.order_by("-created_at").first()
        payload = {
            "report_count": reports.count(),
            "draft_report_count": reports.filter(status=SecurityJourneyReport.STATUS_DRAFT).count(),
            "review_report_count": reports.filter(status=SecurityJourneyReport.STATUS_REVIEW).count(),
            "final_report_count": reports.filter(status=SecurityJourneyReport.STATUS_FINAL).count(),
            "latest_run": SecurityAnalysisRunSerializer(latest_run).data if latest_run else None,
            "open_high_severity_gaps": gaps.filter(severity__iexact="high").count(),
            "recent_runs": SecurityAnalysisRunSerializer(runs.order_by("-created_at")[:10], many=True).data,
        }
        return Response(payload)


class SecurityMenuView(APIView):
    permission_classes = [IsSecurityAdmin]

    def get(self, request):
        sections = [
            {"key": "overview", "label": "Overview / Dashboard"},
            {"key": "run_analysis", "label": "Run Analysis"},
            {"key": "dm_journey", "label": "DM Journey"},
            {"key": "video_journey", "label": "Video Journey"},
            {"key": "verification_matrix", "label": "Verification Matrix"},
            {"key": "scope_coverage", "label": "Scope Coverage"},
            {"key": "logging_design", "label": "Logging Design"},
            {"key": "threat_model", "label": "Threat Model"},
            {"key": "gaps_next_tests", "label": "Top Gaps & Next Tests"},
            {"key": "reality_check", "label": "Reality Check"},
            {"key": "evidence_snapshots", "label": "Evidence & Snapshots"},
            {"key": "audit_trail", "label": "Audit Trail"},
        ]
        return Response({"sections": sections})


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
    "PasswordResetView",
    "TokenObtainPairView",
    "TokenRefreshView",
    "DeviceViewSet",
    "WorkspaceViewSet",
    "ChannelViewSet",
    "ConversationViewSet",
    "MessageEnvelopeViewSet",
    "AttachmentViewSet",
    "SessionEventViewSet",
    "SecurityJourneyReportViewSet",
    "SecurityJourneyStageViewSet",
    "SecurityScopeCoverageItemViewSet",
    "SecurityVerificationMatrixItemViewSet",
    "SecurityLoggingFieldPolicyViewSet",
    "SecurityThreatModelItemViewSet",
    "SecurityGapItemViewSet",
    "SecurityNextTestItemViewSet",
    "SecurityAnalysisAuditEventViewSet",
    "SecurityAnalysisRunViewSet",
    "SecurityRunView",
    "SecurityDashboardView",
    "SecurityMenuView",
    "SecurityReportSnapshotViewSet",
    "PresenceView",
    "AdminSecurityBootstrapStatusView",
]
