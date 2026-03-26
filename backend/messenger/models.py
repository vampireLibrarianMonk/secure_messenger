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


class SecurityJourneyReport(TimeStampedModel):
    FLOW_DM = "dm"
    FLOW_VIDEO = "video"
    FLOW_BOTH = "both"
    FLOW_CHOICES = (
        (FLOW_DM, "Direct Message"),
        (FLOW_VIDEO, "Video"),
        (FLOW_BOTH, "Both"),
    )

    STATUS_DRAFT = "draft"
    STATUS_REVIEW = "review"
    STATUS_FINAL = "final"
    STATUS_CHOICES = (
        (STATUS_DRAFT, "Draft"),
        (STATUS_REVIEW, "In Review"),
        (STATUS_FINAL, "Final"),
    )

    title = models.CharField(max_length=255)
    flow_type = models.CharField(max_length=16, choices=FLOW_CHOICES, default=FLOW_BOTH)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    executive_summary = models.TextField(blank=True)
    reality_check_answers = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="security_journey_reports",
    )


class SecurityJourneyStage(TimeStampedModel):
    FLOW_DM = "dm"
    FLOW_VIDEO = "video"
    FLOW_CHOICES = (
        (FLOW_DM, "Direct Message"),
        (FLOW_VIDEO, "Video"),
    )

    report = models.ForeignKey(SecurityJourneyReport, on_delete=models.CASCADE, related_name="stages")
    flow_type = models.CharField(max_length=16, choices=FLOW_CHOICES)
    stage_number = models.PositiveIntegerField()
    stage_name = models.CharField(max_length=255)
    component = models.CharField(max_length=255, blank=True)
    protocol = models.CharField(max_length=128, blank=True)

    security_assumptions = models.TextField(blank=True)
    assets_exposed = models.TextField(blank=True)
    trust_boundary = models.TextField(blank=True)
    attack_surface = models.TextField(blank=True)

    plaintext_data = models.TextField(blank=True)
    encrypted_data = models.TextField(blank=True)
    theoretically_readable_by = models.TextField(blank=True)

    logs_should_exist = models.TextField(blank=True)
    logs_must_not_contain = models.TextField(blank=True)
    validation_method = models.TextField(blank=True)
    likely_failure_modes = models.TextField(blank=True)
    code_config_infra_checks = models.TextField(blank=True)

    severity_if_compromised = models.CharField(max_length=32, blank=True)

    class Meta:
        unique_together = ("report", "flow_type", "stage_number", "stage_name")
        ordering = ("flow_type", "stage_number", "id")


class SecurityVerificationMatrixItem(TimeStampedModel):
    report = models.ForeignKey(SecurityJourneyReport, on_delete=models.CASCADE, related_name="verification_items")
    stage = models.ForeignKey(
        SecurityJourneyStage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verification_items",
    )
    stage_label = models.CharField(max_length=255, blank=True)
    expected_security_property = models.TextField()
    evidence_source = models.TextField(blank=True)
    how_to_test = models.TextField(blank=True)
    pass_fail_criteria = models.TextField(blank=True)
    common_misconfiguration = models.TextField(blank=True)
    recommended_remediation = models.TextField(blank=True)
