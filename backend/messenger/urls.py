from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    AttachmentViewSet,
    ChannelViewSet,
    ConversationViewSet,
    DeviceViewSet,
    LogoutView,
    MeView,
    MessageEnvelopeViewSet,
    NotificationPreferenceView,
    PasswordChangeView,
    PresenceView,
    RegisterView,
    SessionEventViewSet,
    TestLabBootstrapView,
    TestLabRunArtifactView,
    TestLabTestUserManagementView,
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


urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", TokenObtainPairView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("auth/change-password/", PasswordChangeView.as_view(), name="change-password"),
    path("auth/notification-preferences/", NotificationPreferenceView.as_view(), name="notification-preferences"),
    path("test-lab/bootstrap/", TestLabBootstrapView.as_view(), name="test-lab-bootstrap"),
    path("test-lab/runs/", TestLabRunArtifactView.as_view(), name="test-lab-runs"),
    path("test-lab/test-users/", TestLabTestUserManagementView.as_view(), name="test-lab-test-users"),
    path("presence/", PresenceView.as_view(), name="presence"),
    path("", include(router.urls)),
]
