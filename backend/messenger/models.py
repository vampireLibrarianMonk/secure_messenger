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


class SecurityAdminAccountState(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="security_admin_state")
    must_reset_password = models.BooleanField(default=False)
    bootstrap_source = models.CharField(max_length=64, default="docker_bootstrap")
    last_bootstrap_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Security Admin Account State"
        verbose_name_plural = "Security Admin Account States"


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


class SecurityScopeCoverageItem(TimeStampedModel):
    report = models.ForeignKey(SecurityJourneyReport, on_delete=models.CASCADE, related_name="scope_coverage_items")
    area = models.CharField(max_length=128)
    present_in_implementation = models.BooleanField(default=False)
    evidence = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ("report", "area")
        ordering = ("area", "id")


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


class SecurityLoggingFieldPolicy(TimeStampedModel):
    CLASS_ALLOWED = "allowed"
    CLASS_HASHED = "hashed"
    CLASS_REDACTED = "redacted"
    CLASS_FORBIDDEN = "forbidden"
    CLASSIFICATION_CHOICES = (
        (CLASS_ALLOWED, "Allowed"),
        (CLASS_HASHED, "Hashed/Tokenized"),
        (CLASS_REDACTED, "Redacted"),
        (CLASS_FORBIDDEN, "Forbidden"),
    )

    report = models.ForeignKey(SecurityJourneyReport, on_delete=models.CASCADE, related_name="logging_field_policies")
    field_name = models.CharField(max_length=128)
    classification = models.CharField(max_length=16, choices=CLASSIFICATION_CHOICES)
    rationale = models.TextField(blank=True)

    class Meta:
        unique_together = ("report", "field_name")
        ordering = ("field_name",)


class SecurityThreatModelItem(TimeStampedModel):
    FLOW_DM = "dm"
    FLOW_VIDEO = "video"
    FLOW_BOTH = "both"
    FLOW_CHOICES = (
        (FLOW_DM, "Direct Message"),
        (FLOW_VIDEO, "Video"),
        (FLOW_BOTH, "Both"),
    )

    report = models.ForeignKey(SecurityJourneyReport, on_delete=models.CASCADE, related_name="threat_items")
    flow_type = models.CharField(max_length=16, choices=FLOW_CHOICES, default=FLOW_BOTH)
    threat = models.CharField(max_length=255)
    affected_stages = models.TextField(blank=True)
    likely_indicators = models.TextField(blank=True)
    controls = models.TextField(blank=True)
    residual_risk = models.TextField(blank=True)
    severity = models.CharField(max_length=32, blank=True)

    class Meta:
        ordering = ("flow_type", "threat", "id")


class SecurityGapItem(TimeStampedModel):
    report = models.ForeignKey(SecurityJourneyReport, on_delete=models.CASCADE, related_name="gap_items")
    rank = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    evidence = models.TextField(blank=True)
    severity = models.CharField(max_length=32, blank=True)
    recommended_remediation = models.TextField(blank=True)

    class Meta:
        ordering = ("rank", "id")


class SecurityNextTestItem(TimeStampedModel):
    PRIORITY_HIGH = "high"
    PRIORITY_MEDIUM = "medium"
    PRIORITY_LOW = "low"
    PRIORITY_CHOICES = (
        (PRIORITY_HIGH, "High"),
        (PRIORITY_MEDIUM, "Medium"),
        (PRIORITY_LOW, "Low"),
    )

    report = models.ForeignKey(SecurityJourneyReport, on_delete=models.CASCADE, related_name="next_test_items")
    priority = models.CharField(max_length=16, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)
    name = models.CharField(max_length=255)
    scope = models.CharField(max_length=255, blank=True)
    method = models.TextField(blank=True)
    pass_fail_criteria = models.TextField(blank=True)

    class Meta:
        ordering = ("priority", "id")


class SecurityAnalysisAuditEvent(TimeStampedModel):
    ACTION_RUN_TRIGGERED = "run_triggered"
    ACTION_COMPILED_VIEW = "compiled_view"
    ACTION_EXPORT = "export"
    ACTION_SNAPSHOT_CREATE = "snapshot_create"
    ACTION_RETENTION_PURGE = "retention_purge"
    ACTION_CHOICES = (
        (ACTION_RUN_TRIGGERED, "Analysis Run Triggered"),
        (ACTION_COMPILED_VIEW, "Compiled Report Viewed"),
        (ACTION_EXPORT, "Exported"),
        (ACTION_SNAPSHOT_CREATE, "Snapshot Created"),
        (ACTION_RETENTION_PURGE, "Retention Purge"),
    )

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="security_analysis_events")
    report = models.ForeignKey(
        SecurityJourneyReport,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    action = models.CharField(max_length=32, choices=ACTION_CHOICES)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at", "id")


class SecurityReportSnapshot(TimeStampedModel):
    FORMAT_JSON = "json"
    FORMAT_CHOICES = (
        (FORMAT_JSON, "JSON"),
    )

    report = models.ForeignKey(SecurityJourneyReport, on_delete=models.CASCADE, related_name="snapshots")
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="security_report_snapshots",
    )
    snapshot_format = models.CharField(max_length=16, choices=FORMAT_CHOICES, default=FORMAT_JSON)
    payload = models.JSONField(default=dict)
    payload_sha256 = models.CharField(max_length=64)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at", "id")


class SecurityAnalysisRun(TimeStampedModel):
    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_QUEUED, "Queued"),
        (STATUS_RUNNING, "Running"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    )

    FLOW_DM = "dm"
    FLOW_VIDEO = "video"
    FLOW_BOTH = "both"
    FLOW_CHOICES = (
        (FLOW_DM, "Direct Message"),
        (FLOW_VIDEO, "Video"),
        (FLOW_BOTH, "Both"),
    )

    report = models.ForeignKey(SecurityJourneyReport, on_delete=models.CASCADE, related_name="analysis_runs")
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="security_analysis_runs",
    )
    flow_type = models.CharField(max_length=16, choices=FLOW_CHOICES, default=FLOW_BOTH)
    requested_checks = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    run_summary = models.JSONField(default=dict, blank=True)
    failure_reason = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at", "id")
