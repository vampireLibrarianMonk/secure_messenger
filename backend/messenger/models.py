from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Device(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="devices")
    name = models.CharField(max_length=128)
    identity_key = models.TextField()
    signed_prekey = models.TextField(blank=True)
    one_time_prekeys = models.JSONField(default=list, blank=True)
    fingerprint = models.CharField(max_length=128, blank=True)
    is_verified = models.BooleanField(default=False)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.user.username}:{self.name}"


class Workspace(TimeStampedModel):
    name = models.CharField(max_length=255)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="owned_workspaces")

    def __str__(self) -> str:
        return self.name


class WorkspaceMembership(TimeStampedModel):
    ROLE_OWNER = "owner"
    ROLE_ADMIN = "admin"
    ROLE_MEMBER = "member"
    ROLE_CHOICES = (
        (ROLE_OWNER, "Owner"),
        (ROLE_ADMIN, "Admin"),
        (ROLE_MEMBER, "Member"),
    )

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workspace_memberships")
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default=ROLE_MEMBER)

    class Meta:
        unique_together = ("workspace", "user")


class Channel(TimeStampedModel):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="channels")
    name = models.CharField(max_length=120)
    topic = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="created_channels")

    class Meta:
        unique_together = ("workspace", "name")

    def __str__(self) -> str:
        return f"{self.workspace.name}#{self.name}"


class Conversation(TimeStampedModel):
    TYPE_DM = "dm"
    TYPE_GROUP = "group"
    TYPE_CHANNEL = "channel"
    TYPE_CHOICES = (
        (TYPE_DM, "Direct Message"),
        (TYPE_GROUP, "Group"),
        (TYPE_CHANNEL, "Channel"),
    )

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="conversations", null=True, blank=True)
    channel = models.OneToOneField(Channel, on_delete=models.SET_NULL, related_name="conversation", null=True, blank=True)
    kind = models.CharField(max_length=16, choices=TYPE_CHOICES)
    title = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="created_conversations")


class ConversationMember(TimeStampedModel):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversation_memberships")

    class Meta:
        unique_together = ("conversation", "user")


class MessageEnvelope(TimeStampedModel):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages")
    sender_device = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True, blank=True, related_name="messages")
    ciphertext = models.TextField()
    nonce = models.CharField(max_length=128)
    aad = models.TextField(blank=True)
    message_index = models.PositiveIntegerField(default=0)


class Attachment(TimeStampedModel):
    message = models.ForeignKey(MessageEnvelope, on_delete=models.CASCADE, related_name="attachments")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attachments")
    blob = models.FileField(upload_to="attachments/")
    mime_type = models.CharField(max_length=128)
    size = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=128)
    wrapped_file_key = models.TextField()
    file_nonce = models.CharField(max_length=128)


class SessionEvent(TimeStampedModel):
    EVENT_LOCK = "lock"
    EVENT_LOGOUT = "logout"
    EVENT_PANIC = "panic"
    EVENT_REVOKE = "revoke"
    EVENT_CHOICES = (
        (EVENT_LOCK, "Lock"),
        (EVENT_LOGOUT, "Logout"),
        (EVENT_PANIC, "Panic"),
        (EVENT_REVOKE, "Revoke"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="session_events")
    device = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True, blank=True, related_name="session_events")
    event_type = models.CharField(max_length=16, choices=EVENT_CHOICES)
    metadata = models.JSONField(default=dict, blank=True)


class UserNotificationPreference(TimeStampedModel):
    SOUND_CHIME = "chime"
    SOUND_PULSE = "pulse"
    SOUND_ALERT = "alert"
    SOUND_SOFT = "soft"
    SOUND_CHOICES = (
        (SOUND_CHIME, "Chime"),
        (SOUND_PULSE, "Pulse"),
        (SOUND_ALERT, "Alert"),
        (SOUND_SOFT, "Soft"),
    )

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_preferences")
    dm_sound = models.CharField(max_length=32, choices=SOUND_CHOICES, default=SOUND_CHIME)
    dm_document_sound = models.CharField(max_length=32, choices=SOUND_CHOICES, default=SOUND_PULSE)
    video_ring_sound = models.CharField(max_length=32, choices=SOUND_CHOICES, default=SOUND_ALERT)
    chat_leave_sound = models.CharField(max_length=32, choices=SOUND_CHOICES, default=SOUND_SOFT)
