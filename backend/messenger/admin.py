from django.contrib import admin

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
    SecurityReportSnapshot,
    SecurityJourneyReport,
    SecurityJourneyStage,
    SecurityScopeCoverageItem,
    SecurityAnalysisRun,
    SecurityThreatModelItem,
    SecurityVerificationMatrixItem,
    SessionEvent,
    Workspace,
    WorkspaceMembership,
)


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "name", "is_verified", "last_seen_at", "created_at")
    search_fields = ("user__username", "name", "fingerprint")


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_by", "created_at")
    search_fields = ("name", "created_by__username")


@admin.register(WorkspaceMembership)
class WorkspaceMembershipAdmin(admin.ModelAdmin):
    list_display = ("id", "workspace", "user", "role", "created_at")
    list_filter = ("role",)


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ("id", "workspace", "name", "created_by", "created_at")
    search_fields = ("name", "workspace__name")


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "title", "workspace", "channel", "created_by", "created_at")
    list_filter = ("kind",)


@admin.register(ConversationMember)
class ConversationMemberAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "user", "created_at")


@admin.register(MessageEnvelope)
class MessageEnvelopeAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender", "sender_device", "message_index", "created_at")


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("id", "message", "uploaded_by", "mime_type", "size", "created_at")


@admin.register(SessionEvent)
class SessionEventAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "device", "event_type", "created_at")
    list_filter = ("event_type",)


@admin.register(SecurityJourneyReport)
class SecurityJourneyReportAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "flow_type", "status", "created_by", "created_at")
    list_filter = ("flow_type", "status")
    search_fields = ("title", "created_by__username")


@admin.register(SecurityJourneyStage)
class SecurityJourneyStageAdmin(admin.ModelAdmin):
    list_display = ("id", "report", "flow_type", "stage_number", "stage_name", "severity_if_compromised", "created_at")
    list_filter = ("flow_type", "severity_if_compromised")
    search_fields = ("stage_name", "component", "protocol")


@admin.register(SecurityScopeCoverageItem)
class SecurityScopeCoverageItemAdmin(admin.ModelAdmin):
    list_display = ("id", "report", "area", "present_in_implementation", "created_at")
    list_filter = ("present_in_implementation",)
    search_fields = ("area",)


@admin.register(SecurityVerificationMatrixItem)
class SecurityVerificationMatrixItemAdmin(admin.ModelAdmin):
    list_display = ("id", "report", "stage", "stage_label", "created_at")
    search_fields = ("stage_label", "expected_security_property")


@admin.register(SecurityLoggingFieldPolicy)
class SecurityLoggingFieldPolicyAdmin(admin.ModelAdmin):
    list_display = ("id", "report", "field_name", "classification", "created_at")
    list_filter = ("classification",)
    search_fields = ("field_name",)


@admin.register(SecurityThreatModelItem)
class SecurityThreatModelItemAdmin(admin.ModelAdmin):
    list_display = ("id", "report", "flow_type", "threat", "severity", "created_at")
    list_filter = ("flow_type", "severity")
    search_fields = ("threat",)


@admin.register(SecurityGapItem)
class SecurityGapItemAdmin(admin.ModelAdmin):
    list_display = ("id", "report", "rank", "title", "severity", "created_at")
    list_filter = ("severity",)
    search_fields = ("title",)


@admin.register(SecurityNextTestItem)
class SecurityNextTestItemAdmin(admin.ModelAdmin):
    list_display = ("id", "report", "priority", "name", "created_at")
    list_filter = ("priority",)
    search_fields = ("name",)


@admin.register(SecurityAnalysisAuditEvent)
class SecurityAnalysisAuditEventAdmin(admin.ModelAdmin):
    list_display = ("id", "actor", "report", "action", "created_at")
    list_filter = ("action",)
    search_fields = ("actor__username",)


@admin.register(SecurityReportSnapshot)
class SecurityReportSnapshotAdmin(admin.ModelAdmin):
    list_display = ("id", "report", "generated_by", "snapshot_format", "payload_sha256", "created_at")
    list_filter = ("snapshot_format",)
    search_fields = ("payload_sha256",)


@admin.register(SecurityAdminAccountState)
class SecurityAdminAccountStateAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "must_reset_password", "bootstrap_source", "last_bootstrap_at", "created_at")
    list_filter = ("must_reset_password", "bootstrap_source")
    search_fields = ("user__username",)


@admin.register(SecurityAnalysisRun)
class SecurityAnalysisRunAdmin(admin.ModelAdmin):
    list_display = ("id", "report", "triggered_by", "flow_type", "status", "created_at")
    list_filter = ("flow_type", "status")
    search_fields = ("report__title", "triggered_by__username")
