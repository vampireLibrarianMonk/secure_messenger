import base64
import binascii
import json

from django.contrib.auth.models import User
from rest_framework import serializers

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
    @staticmethod
    def _validate_base64(value: str, field_name: str) -> str:
        try:
            base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError):
            raise serializers.ValidationError(f"{field_name} must be valid base64.")
        return value

    def validate_sha256(self, value: str) -> str:
        self._validate_base64(value, "sha256")
        digest = base64.b64decode(value)
        if len(digest) != 32:
            raise serializers.ValidationError("sha256 must decode to 32 bytes.")
        return value

    def validate_file_nonce(self, value: str) -> str:
        self._validate_base64(value, "file_nonce")
        nonce = base64.b64decode(value)
        if len(nonce) != 12:
            raise serializers.ValidationError("file_nonce must decode to 12 bytes for AES-GCM.")
        return value

    def validate_wrapped_file_key(self, value: str) -> str:
        self._validate_base64(value, "wrapped_file_key")
        key_raw = base64.b64decode(value)
        if len(key_raw) not in {16, 24, 32}:
            raise serializers.ValidationError(
                "wrapped_file_key must decode to a supported AES key length (16/24/32 bytes)."
            )
        return value

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

    @staticmethod
    def _validate_base64(value: str, field_name: str) -> str:
        try:
            base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError):
            raise serializers.ValidationError(f"{field_name} must be valid base64.")
        return value

    def validate_ciphertext(self, value: str) -> str:
        if not value or not isinstance(value, str):
            raise serializers.ValidationError("ciphertext is required.")
        if len(value) > 65535:
            raise serializers.ValidationError("ciphertext exceeds maximum allowed length.")
        return self._validate_base64(value, "ciphertext")

    def validate_nonce(self, value: str) -> str:
        if not value or not isinstance(value, str):
            raise serializers.ValidationError("nonce is required.")
        self._validate_base64(value, "nonce")
        nonce_raw = base64.b64decode(value)
        if len(nonce_raw) != 12:
            raise serializers.ValidationError("nonce must decode to 12 bytes for AES-GCM.")
        return value

    def validate_aad(self, value: str) -> str:
        if value in (None, ""):
            return ""
        if not isinstance(value, str):
            raise serializers.ValidationError("aad must be a JSON string.")
        if len(value) > 4096:
            raise serializers.ValidationError("aad exceeds maximum allowed length.")
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise serializers.ValidationError("aad must be valid JSON.") from exc
        if not isinstance(parsed, dict):
            raise serializers.ValidationError("aad JSON must be an object.")
        return value

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
