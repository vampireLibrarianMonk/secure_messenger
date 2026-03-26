from django.contrib.auth.models import User
from rest_framework import serializers

from .models import (
    Attachment,
    Channel,
    Conversation,
    ConversationMember,
    Device,
    MessageEnvelope,
    SecurityJourneyReport,
    SecurityJourneyStage,
    SecurityVerificationMatrixItem,
    SessionEvent,
    Workspace,
    WorkspaceMembership,
)


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ("id", "username", "email", "password")

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = (
            "id",
            "user",
            "name",
            "identity_key",
            "signed_prekey",
            "one_time_prekeys",
            "fingerprint",
            "is_verified",
            "last_seen_at",
            "created_at",
        )
        read_only_fields = ("user", "is_verified", "last_seen_at", "created_at")


class WorkspaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workspace
        fields = ("id", "name", "created_by", "created_at")
        read_only_fields = ("created_by", "created_at")


class WorkspaceMembershipSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = WorkspaceMembership
        fields = ("id", "workspace", "user", "username", "role", "created_at")
        read_only_fields = ("created_at",)


class ChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Channel
        fields = ("id", "workspace", "name", "topic", "created_by", "created_at")
        read_only_fields = ("created_by", "created_at")


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = ("id", "workspace", "channel", "kind", "title", "created_by", "created_at")
        read_only_fields = ("created_by", "created_at")


class ConversationMemberSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = ConversationMember
        fields = ("id", "conversation", "user", "username", "created_at")
        read_only_fields = ("created_at",)


class AttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = (
            "id",
            "message",
            "uploaded_by",
            "blob",
            "mime_type",
            "size",
            "sha256",
            "wrapped_file_key",
            "file_nonce",
            "created_at",
        )
        read_only_fields = ("uploaded_by", "size", "created_at")


class MessageEnvelopeSerializer(serializers.ModelSerializer):
    attachments = AttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = MessageEnvelope
        fields = (
            "id",
            "conversation",
            "sender",
            "sender_device",
            "ciphertext",
            "nonce",
            "aad",
            "message_index",
            "attachments",
            "created_at",
        )
        read_only_fields = ("sender", "created_at")


class SessionEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionEvent
        fields = ("id", "user", "device", "event_type", "metadata", "created_at")
        read_only_fields = ("user", "created_at")


class SecurityJourneyReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecurityJourneyReport
        fields = (
            "id",
            "title",
            "flow_type",
            "status",
            "executive_summary",
            "reality_check_answers",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_by", "created_at", "updated_at")


class SecurityJourneyStageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecurityJourneyStage
        fields = (
            "id",
            "report",
            "flow_type",
            "stage_number",
            "stage_name",
            "component",
            "protocol",
            "security_assumptions",
            "assets_exposed",
            "trust_boundary",
            "attack_surface",
            "plaintext_data",
            "encrypted_data",
            "theoretically_readable_by",
            "logs_should_exist",
            "logs_must_not_contain",
            "validation_method",
            "likely_failure_modes",
            "code_config_infra_checks",
            "severity_if_compromised",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")


class SecurityVerificationMatrixItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecurityVerificationMatrixItem
        fields = (
            "id",
            "report",
            "stage",
            "stage_label",
            "expected_security_property",
            "evidence_source",
            "how_to_test",
            "pass_fail_criteria",
            "common_misconfiguration",
            "recommended_remediation",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")
