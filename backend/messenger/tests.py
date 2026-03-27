import base64

from django.contrib.auth.models import User
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from .models import Attachment, Conversation, ConversationMember, MessageEnvelope, SessionEvent
from .consumers import _validate_video_signal_message


def b64_bytes(size: int, fill: bytes = b"a") -> str:
    return base64.b64encode(fill * size).decode("ascii")


class AuthFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register_and_login(self):
        register = self.client.post(
            "/api/auth/register/",
            {"username": "alice", "email": "alice@example.com", "password": "testpass123"},
            format="json",
        )
        self.assertEqual(register.status_code, 201)
        self.assertIn("access", register.data)

        login = self.client.post(
            "/api/auth/login/",
            {"username": "alice", "password": "testpass123"},
            format="json",
        )
        self.assertEqual(login.status_code, 200)
        self.assertIn("access", login.data)


class MessagingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="alice", password="testpass123")
        self.other = User.objects.create_user(username="bob", password="testpass123")

        token = self.client.post(
            "/api/auth/login/", {"username": "alice", "password": "testpass123"}, format="json"
        ).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_send_ciphertext_message(self):
        conversation = Conversation.objects.create(kind=Conversation.TYPE_DM, title="dm", created_by=self.user)
        ConversationMember.objects.create(conversation=conversation, user=self.user)
        ConversationMember.objects.create(conversation=conversation, user=self.other)

        response = self.client.post(
            "/api/messages/",
            {
                "conversation": conversation.id,
                "ciphertext": "ZmFrZQ==",
                "nonce": b64_bytes(12),
                "aad": "",
                "message_index": 1,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["ciphertext"], "ZmFrZQ==")

    def test_send_ciphertext_message_rejects_invalid_nonce_size(self):
        conversation = Conversation.objects.create(kind=Conversation.TYPE_DM, title="dm", created_by=self.user)
        ConversationMember.objects.create(conversation=conversation, user=self.user)
        ConversationMember.objects.create(conversation=conversation, user=self.other)

        response = self.client.post(
            "/api/messages/",
            {
                "conversation": conversation.id,
                "ciphertext": "ZmFrZQ==",
                "nonce": "bm9uY2U=",  # 5 bytes decoded
                "aad": "",
                "message_index": 2,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("nonce", response.data)

    def test_send_ciphertext_message_rejects_non_json_aad(self):
        conversation = Conversation.objects.create(kind=Conversation.TYPE_DM, title="dm", created_by=self.user)
        ConversationMember.objects.create(conversation=conversation, user=self.user)
        ConversationMember.objects.create(conversation=conversation, user=self.other)

        response = self.client.post(
            "/api/messages/",
            {
                "conversation": conversation.id,
                "ciphertext": "ZmFrZQ==",
                "nonce": b64_bytes(12),
                "aad": "not-json",
                "message_index": 3,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("aad", response.data)


class AttachmentSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.alice = User.objects.create_user(username="alice", password="testpass123")
        self.bob = User.objects.create_user(username="bob", password="testpass123")
        self.charlie = User.objects.create_user(username="charlie", password="testpass123")

        token = self.client.post(
            "/api/auth/login/", {"username": "alice", "password": "testpass123"}, format="json"
        ).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        self.conversation = Conversation.objects.create(kind=Conversation.TYPE_DM, title="dm", created_by=self.alice)
        ConversationMember.objects.create(conversation=self.conversation, user=self.alice)
        ConversationMember.objects.create(conversation=self.conversation, user=self.bob)

        self.message = MessageEnvelope.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            ciphertext="ZmFrZQ==",
            nonce=b64_bytes(12),
            aad="",
            message_index=1,
        )

    def _post_attachment(self, **overrides):
        payload = {
            "message": str(self.message.id),
            "mime_type": "application/pdf",
            "sha256": b64_bytes(32, b"b"),
            "wrapped_file_key": b64_bytes(32, b"k"),
            "file_nonce": b64_bytes(12, b"n"),
            "blob": SimpleUploadedFile("file.enc", b"encrypted", content_type="application/octet-stream"),
        }
        payload.update(overrides)
        return self.client.post("/api/attachments/", payload, format="multipart")

    def test_attachment_upload_success_with_valid_metadata(self):
        response = self._post_attachment()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Attachment.objects.count(), 1)

    def test_attachment_upload_rejects_invalid_nonce(self):
        response = self._post_attachment(file_nonce="bm9uY2U=")
        self.assertEqual(response.status_code, 400)
        self.assertIn("file_nonce", response.data)

    def test_attachment_upload_rejects_invalid_sha256(self):
        response = self._post_attachment(sha256=b64_bytes(16, b"s"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("sha256", response.data)

    def test_attachment_upload_rejects_invalid_wrapped_file_key_size(self):
        response = self._post_attachment(wrapped_file_key=b64_bytes(15, b"k"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("wrapped_file_key", response.data)

    def test_attachment_upload_rejects_non_member_message_target(self):
        other_conversation = Conversation.objects.create(kind=Conversation.TYPE_DM, title="private", created_by=self.charlie)
        ConversationMember.objects.create(conversation=other_conversation, user=self.charlie)
        isolated_message = MessageEnvelope.objects.create(
            conversation=other_conversation,
            sender=self.charlie,
            ciphertext="ZmFrZQ==",
            nonce=b64_bytes(12),
            aad="",
            message_index=2,
        )

        response = self._post_attachment(message=str(isolated_message.id))
        self.assertEqual(response.status_code, 403)


class TestLabArtifactSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.test_user = User.objects.create_user(username="test_user_alpha", password="testpass123")
        token = self.client.post(
            "/api/auth/login/", {"username": "test_user_alpha", "password": "testpass123"}, format="json"
        ).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _valid_run_payload(self):
        return {
            "run": {
                "run_id": "sim_run_1234",
                "scenario": "dm-basic",
                "scenario_label": "DM basic encrypted exchange",
                "category": "dm",
                "environment": "local sandbox",
                "intensity": "standard",
                "state": "completed",
                "result": "PASS — E2EE VERIFIED",
                "duration_ms": 1000,
                "warnings": 0,
                "participants": ["test-user-a@faux_node_alpha", "test-user-b@faux_node_bravo"],
                "events": [
                    {
                        "id": "session-1",
                        "timestamp": "2026-01-01T00:00:00.000Z",
                        "label": "STEP 1: session",
                        "status": "completed",
                    }
                ],
                "logs": [
                    {
                        "timestamp": "2026-01-01T00:00:00.000Z",
                        "level": "INFO",
                        "text": "session completed",
                    }
                ],
                "evidence": ["DM client-side encryption: confirmed"],
                "diagnostics": {"dm": {"ok": True}},
                "metadata_observability": {
                    "correlation_id": "corr-1",
                    "session_id": "sess-1",
                    "room_id": "room-1",
                    "transport_path": "direct",
                    "auth_state": "validated",
                },
            }
        }

    def test_store_run_artifact_success_for_test_user(self):
        response = self.client.post("/api/test-lab/runs/", self._valid_run_payload(), format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(SessionEvent.objects.filter(event_type=SessionEvent.EVENT_REVOKE).count(), 1)

    def test_store_run_artifact_rejects_invalid_schema(self):
        payload = self._valid_run_payload()
        del payload["run"]["metadata_observability"]

        response = self.client.post("/api/test-lab/runs/", payload, format="json")
        self.assertEqual(response.status_code, 400)

    def test_store_run_artifact_rejects_prohibited_plaintext_markers(self):
        payload = self._valid_run_payload()
        payload["run"]["diagnostics"] = {"plaintext": "should-not-exist"}

        response = self.client.post("/api/test-lab/runs/", payload, format="json")
        self.assertEqual(response.status_code, 400)

    def test_video_e2ee_verified_artifact_requires_runtime_verified_evidence_source(self):
        payload = self._valid_run_payload()
        payload["run"]["category"] = "video"
        payload["run"]["result"] = "PASS — E2EE VERIFIED"
        payload["run"]["diagnostics"] = {
            "video": {
                "transport_vs_app_layer": "app_layer_verified_or_unknown",
                "app_layer_evidence_source": "runtime_experimental_obfuscation",
            }
        }

        response = self.client.post("/api/test-lab/runs/", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("runtime_verified", str(response.data))

    def test_video_e2ee_verified_artifact_rejects_transport_only_marker(self):
        payload = self._valid_run_payload()
        payload["run"]["category"] = "video"
        payload["run"]["result"] = "PASS — E2EE VERIFIED"
        payload["run"]["diagnostics"] = {
            "video": {
                "transport_vs_app_layer": "transport_only",
                "app_layer_evidence_source": "runtime_verified",
            }
        }

        response = self.client.post("/api/test-lab/runs/", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("transport_only", str(response.data))

    def test_video_e2ee_verified_artifact_accepts_runtime_verified_evidence_source(self):
        payload = self._valid_run_payload()
        payload["run"]["category"] = "video"
        payload["run"]["result"] = "PASS — E2EE VERIFIED"
        payload["run"]["diagnostics"] = {
            "video": {
                "transport_vs_app_layer": "app_layer_verified_or_unknown",
                "app_layer_evidence_source": "runtime_verified",
            }
        }

        response = self.client.post("/api/test-lab/runs/", payload, format="json")
        self.assertEqual(response.status_code, 201)


class GroupEpochSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.alice = User.objects.create_user(username="alice", password="testpass123")
        self.bob = User.objects.create_user(username="bob", password="testpass123")
        self.charlie = User.objects.create_user(username="charlie", password="testpass123")

        token = self.client.post(
            "/api/auth/login/", {"username": "alice", "password": "testpass123"}, format="json"
        ).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _create_group(self) -> int:
        response = self.client.post(
            "/api/conversations/",
            {
                "kind": "group",
                "title": "secure-group",
                "member_usernames": ["bob"],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        return int(response.data["id"])

    def test_group_create_emits_initial_epoch_event(self):
        conversation_id = self._create_group()
        event = SessionEvent.objects.filter(
            event_type=SessionEvent.EVENT_REVOKE,
            metadata__category="group_key_epoch",
            metadata__conversation_id=conversation_id,
        ).order_by("-created_at").first()
        self.assertIsNotNone(event)
        self.assertEqual(event.metadata["epoch"], 1)
        self.assertEqual(event.metadata["reason"], "group_created")

    def test_group_membership_change_increments_epoch(self):
        conversation_id = self._create_group()

        response = self.client.post(
            f"/api/conversations/{conversation_id}/members/",
            {"user": self.charlie.id},
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        latest_event = SessionEvent.objects.filter(
            event_type=SessionEvent.EVENT_REVOKE,
            metadata__category="group_key_epoch",
            metadata__conversation_id=conversation_id,
        ).order_by("-created_at").first()
        self.assertIsNotNone(latest_event)
        self.assertEqual(latest_event.metadata["epoch"], 2)
        self.assertEqual(latest_event.metadata["reason"], "member_added")

    def test_group_key_epoch_endpoint_returns_current_epoch(self):
        conversation_id = self._create_group()

        # Add member to advance epoch from 1 -> 2
        response = self.client.post(
            f"/api/conversations/{conversation_id}/members/",
            {"user": self.charlie.id},
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        epoch_response = self.client.get(f"/api/conversations/{conversation_id}/key-epoch/")
        self.assertEqual(epoch_response.status_code, 200)
        self.assertEqual(epoch_response.data["conversation_id"], conversation_id)
        self.assertEqual(epoch_response.data["group_epoch"], 2)

    def test_group_message_requires_current_epoch(self):
        conversation_id = self._create_group()

        ok = self.client.post(
            "/api/messages/",
            {
                "conversation": conversation_id,
                "ciphertext": "ZmFrZQ==",
                "nonce": b64_bytes(12),
                "aad": '{"group_epoch": 1}',
                "message_index": 10,
            },
            format="json",
        )
        self.assertEqual(ok.status_code, 201)

        stale = self.client.post(
            "/api/messages/",
            {
                "conversation": conversation_id,
                "ciphertext": "ZmFrZQ==",
                "nonce": b64_bytes(12),
                "aad": '{"group_epoch": 0}',
                "message_index": 11,
            },
            format="json",
        )
        self.assertEqual(stale.status_code, 409)
        self.assertIn("expected_group_epoch", stale.data)
        self.assertIn("expected_group_epoch=1", stale.data["detail"])

    def test_group_message_rejects_missing_group_epoch(self):
        conversation_id = self._create_group()
        response = self.client.post(
            "/api/messages/",
            {
                "conversation": conversation_id,
                "ciphertext": "ZmFrZQ==",
                "nonce": b64_bytes(12),
                "aad": '{"kind":"text"}',
                "message_index": 12,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("aad", response.data)


class VideoSignalValidationTests(TestCase):
    def test_validate_non_rekey_allowed(self):
        ok, error = _validate_video_signal_message(
            {"type": "offer", "payload": {}, "client_id": "c1", "sequence": 1},
            required_session_id="sess-1",
            last_control_nonce=None,
            last_sequence=None,
        )
        self.assertFalse(ok)
        self.assertEqual(error, "invalid_signaling_session")

        ok, error = _validate_video_signal_message(
            {
                "type": "offer",
                "payload": {},
                "client_id": "c1",
                "sequence": 1,
                "signaling_session_id": "sess-1",
            },
            required_session_id="sess-1",
            last_control_nonce=None,
            last_sequence=None,
        )
        self.assertTrue(ok)
        self.assertIsNone(error)

    def test_validate_rekey_requires_monotonic_nonce(self):
        ok, error = _validate_video_signal_message(
            {
                "type": "rekey_update",
                "payload": {"epoch": 2, "control_nonce": 7},
                "client_id": "c1",
                "sequence": 2,
                "signaling_session_id": "sess-1",
            },
            required_session_id="sess-1",
            last_control_nonce=7,
            last_sequence=1,
        )
        self.assertFalse(ok)
        self.assertEqual(error, "replayed_control_nonce")

    def test_validate_rekey_epoch_and_nonce_types(self):
        ok, error = _validate_video_signal_message(
            {
                "type": "rekey_update",
                "payload": {"epoch": "x", "control_nonce": "y"},
                "client_id": "c1",
                "sequence": 2,
                "signaling_session_id": "sess-1",
            },
            required_session_id="sess-1",
            last_control_nonce=None,
            last_sequence=1,
        )
        self.assertFalse(ok)
        self.assertEqual(error, "invalid_rekey_epoch")

    def test_validate_rekey_missing_payload(self):
        ok, error = _validate_video_signal_message(
            {
                "type": "rekey_update",
                "payload": None,
                "client_id": "c1",
                "sequence": 2,
                "signaling_session_id": "sess-1",
            },
            required_session_id="sess-1",
            last_control_nonce=None,
            last_sequence=1,
        )
        self.assertFalse(ok)
        self.assertEqual(error, "invalid_rekey_payload")

    def test_validate_requires_monotonic_sequence(self):
        ok, error = _validate_video_signal_message(
            {
                "type": "offer",
                "payload": {},
                "client_id": "c1",
                "sequence": 3,
                "signaling_session_id": "sess-1",
            },
            required_session_id="sess-1",
            last_control_nonce=None,
            last_sequence=3,
        )
        self.assertFalse(ok)
        self.assertEqual(error, "replayed_sequence")

    def test_validate_requires_client_id_and_sequence(self):
        ok, error = _validate_video_signal_message(
            {"type": "offer", "payload": {}},
            required_session_id="sess-1",
            last_control_nonce=None,
            last_sequence=None,
        )
        self.assertFalse(ok)
        self.assertEqual(error, "missing_client_id")
