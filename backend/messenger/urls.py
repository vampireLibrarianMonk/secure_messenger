from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    AdminSecurityBootstrapStatusView,
    AttachmentViewSet,
    ChannelViewSet,
    ConversationViewSet,
    DeviceViewSet,
    LogoutView,
    MeView,
    MessageEnvelopeViewSet,
    PasswordResetView,
    PresenceView,
    RegisterView,
    SecurityAnalysisAuditEventViewSet,
    SecurityGapItemViewSet,
    SecurityLoggingFieldPolicyViewSet,
    SecurityNextTestItemViewSet,
    SecurityRunView,
    SecurityJourneyReportViewSet,
    SecurityJourneyStageViewSet,
    SecurityAnalysisRunViewSet,
    SecurityDashboardView,
    SecurityMenuView,
    SecurityScopeCoverageItemViewSet,
    SecurityReportSnapshotViewSet,
    SecurityThreatModelItemViewSet,
    SecurityVerificationMatrixItemViewSet,
    SessionEventViewSet,
    WorkspaceViewSet,
)


router = DefaultRouter()
router.register(r"devices", DeviceViewSet, basename="device")
router.register(r"workspaces", WorkspaceViewSet, basename="workspace")
router.register(r"channels", ChannelViewSet, basename="channel")
router.register(r"conversations", ConversationViewSet, basename="conversation")
router.register(r"messages", MessageEnvelopeViewSet, basename="message")
router.register(r"attachments", AttachmentViewSet, basename="attachment")
router.register(r"session-events", SessionEventViewSet, basename="session-event")
router.register(r"admin/security/reports", SecurityJourneyReportViewSet, basename="security-journey-report")
router.register(r"admin/security/stages", SecurityJourneyStageViewSet, basename="security-journey-stage")
router.register(r"admin/security/scope-coverage", SecurityScopeCoverageItemViewSet, basename="security-scope-coverage-item")
router.register(r"admin/security/verification-matrix", SecurityVerificationMatrixItemViewSet, basename="security-verification-matrix")
router.register(r"admin/security/logging-policies", SecurityLoggingFieldPolicyViewSet, basename="security-logging-field-policy")
router.register(r"admin/security/threat-model", SecurityThreatModelItemViewSet, basename="security-threat-model-item")
router.register(r"admin/security/gaps", SecurityGapItemViewSet, basename="security-gap-item")
router.register(r"admin/security/next-tests", SecurityNextTestItemViewSet, basename="security-next-test-item")
router.register(r"admin/security/audit-events", SecurityAnalysisAuditEventViewSet, basename="security-analysis-audit-event")
router.register(r"admin/security/snapshots", SecurityReportSnapshotViewSet, basename="security-report-snapshot")
router.register(r"admin/security/runs", SecurityAnalysisRunViewSet, basename="security-analysis-run")


urlpatterns = [
    path("admin/security/status/", AdminSecurityBootstrapStatusView.as_view(), name="admin-security-status"),
    path("admin/security/menu/", SecurityMenuView.as_view(), name="admin-security-menu"),
    path("admin/security/dashboard/", SecurityDashboardView.as_view(), name="admin-security-dashboard"),
    path("admin/security/run/", SecurityRunView.as_view(), name="admin-security-run"),
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", TokenObtainPairView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("auth/password-reset/", PasswordResetView.as_view(), name="password_reset"),
    path("presence/", PresenceView.as_view(), name="presence"),
    path("", include(router.urls)),
]
