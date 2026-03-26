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
    PresenceView,
    RegisterView,
    SecurityJourneyReportViewSet,
    SecurityJourneyStageViewSet,
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
router.register(r"admin/security/verification-matrix", SecurityVerificationMatrixItemViewSet, basename="security-verification-matrix")


urlpatterns = [
    path("admin/security/status/", AdminSecurityBootstrapStatusView.as_view(), name="admin-security-status"),
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", TokenObtainPairView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("presence/", PresenceView.as_view(), name="presence"),
    path("", include(router.urls)),
]
