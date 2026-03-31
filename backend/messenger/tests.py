import base64

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import User
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from config.asgi import application
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

    def test_change_password_success_requires_current_password(self):
        User.objects.create_user(username="alice", email="alice@example.com", password="testpass123")
        login = self.client.post(
            "/api/auth/login/",
            {"username": "alice", "password": "testpass123"},
            format="json",
        )
        token = login.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.post(
            "/api/auth/change-password/",
            {
                "current_password": "testpass123",
                "new_password": "NewStrongPass123_",
                "confirm_new_password": "NewStrongPass123_",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        self.client.credentials()
        old_login = self.client.post(
            "/api/auth/login/",
            {"username": "alice", "password": "testpass123"},
            format="json",
        )
        self.assertEqual(old_login.status_code, 401)

        new_login = self.client.post(
            "/api/auth/login/",
            {"username": "alice", "password": "NewStrongPass123_"},
            format="json",
        )
        self.assertEqual(new_login.status_code, 200)

    def test_change_password_rejects_wrong_current_password(self):
        User.objects.create_user(username="alice", password="testpass123")
        login = self.client.post(
            "/api/auth/login/",
            {"username": "alice", "password": "testpass123"},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        response = self.client.post(
            "/api/auth/change-password/",
            {
                "current_password": "wrongpass",
                "new_password": "NewStrongPass123_",
                "confirm_new_password": "NewStrongPass123_",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("current_password", response.data)

    def test_change_password_rejects_mismatch(self):
        User.objects.create_user(username="alice", password="testpass123")
        login = self.client.post(
            "/api/auth/login/",
            {"username": "alice", "password": "testpass123"},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        response = self.client.post(
            "/api/auth/change-password/",
            {
                "current_password": "testpass123",
                "new_password": "NewStrongPass123_",
                "confirm_new_password": "MismatchPass123_",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("confirm_new_password", response.data)

    def test_notification_preferences_default_and_update(self):
        User.objects.create_user(username="alice", password="testpass123")
        login = self.client.post(
            "/api/auth/login/",
            {"username": "alice", "password": "testpass123"},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        default_response = self.client.get("/api/auth/notification-preferences/")
        self.assertEqual(default_response.status_code, 200)
        self.assertEqual(default_response.data["dm_sound"], "chime")
        self.assertEqual(default_response.data["dm_document_sound"], "pulse")
        self.assertEqual(default_response.data["video_ring_sound"], "alert")
        self.assertEqual(default_response.data["chat_leave_sound"], "soft")

        update_response = self.client.put(
            "/api/auth/notification-preferences/",
            {
                "dm_sound": "soft",
                "dm_document_sound": "alert",
                "video_ring_sound": "pulse",
                "chat_leave_sound": "chime",
            },
            format="json",
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.data["dm_sound"], "soft")
        self.assertEqual(update_response.data["dm_document_sound"], "alert")
        self.assertEqual(update_response.data["video_ring_sound"], "pulse")
        self.assertEqual(update_response.data["chat_leave_sound"], "chime")


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

    def test_send_ciphertext_message_preserves_shared_key_aad_for_receiver(self):
        conversation = Conversation.objects.create(kind=Conversation.TYPE_DM, title="dm", created_by=self.user)
        ConversationMember.objects.create(conversation=conversation, user=self.user)
        ConversationMember.objects.create(conversation=conversation, user=self.other)

        shared_key = b64_bytes(32, b"k")
        response = self.client.post(
            "/api/messages/",
            {
                "conversation": conversation.id,
                "ciphertext": "ZmFrZQ==",
                "nonce": b64_bytes(12),
                "aad": f'{{"kind":"text","shared_key":"{shared_key}"}}',
                "message_index": 4,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertIn(shared_key, response.data["aad"])

    def test_two_temporary_users_can_fetch_distinct_shared_keys_for_multiple_messages(self):
        conversation = Conversation.objects.create(kind=Conversation.TYPE_DM, title="dm", created_by=self.user)
        ConversationMember.objects.create(conversation=conversation, user=self.user)
        ConversationMember.objects.create(conversation=conversation, user=self.other)

        first_key = b64_bytes(32, b"k")
        second_key = b64_bytes(32, b"z")

        first = self.client.post(
            "/api/messages/",
            {
                "conversation": conversation.id,
                "ciphertext": "ZmFrZTE=",
                "nonce": b64_bytes(12, b"n"),
                "aad": f'{{"kind":"text","shared_key":"{first_key}"}}',
                "message_index": 5,
            },
            format="json",
        )
        self.assertEqual(first.status_code, 201)

        second = self.client.post(
            "/api/messages/",
            {
                "conversation": conversation.id,
                "ciphertext": "ZmFrZTI=",
                "nonce": b64_bytes(12, b"m"),
                "aad": f'{{"kind":"text","shared_key":"{second_key}"}}',
                "message_index": 6,
            },
            format="json",
        )
        self.assertEqual(second.status_code, 201)

        receiver_client = APIClient()
        receiver_token = receiver_client.post(
            "/api/auth/login/", {"username": "bob", "password": "testpass123"}, format="json"
        ).data["access"]
        receiver_client.credentials(HTTP_AUTHORIZATION=f"Bearer {receiver_token}")

        fetched = receiver_client.get(f"/api/messages/?conversation={conversation.id}")
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(len(fetched.data), 2)
        self.assertIn(first_key, fetched.data[0]["aad"])
        self.assertIn(second_key, fetched.data[1]["aad"])

    def test_conversation_list_includes_last_message_fields(self):
        conversation = Conversation.objects.create(kind=Conversation.TYPE_DM, title="dm", created_by=self.user)
        ConversationMember.objects.create(conversation=conversation, user=self.user)
        ConversationMember.objects.create(conversation=conversation, user=self.other)

        # No messages yet
        response = self.client.get("/api/conversations/")
        self.assertEqual(response.status_code, 200)
        conv_data = next(c for c in response.data if c["id"] == conversation.id)
        self.assertIsNone(conv_data["last_message_id"])
        self.assertIsNone(conv_data["last_message_sender"])

        # Alice sends a message
        msg = MessageEnvelope.objects.create(
            conversation=conversation, sender=self.user,
            ciphertext="ZmFrZQ==", nonce=b64_bytes(12), aad="", message_index=1,
        )

        response = self.client.get("/api/conversations/")
        conv_data = next(c for c in response.data if c["id"] == conversation.id)
        self.assertEqual(conv_data["last_message_id"], msg.id)
        self.assertEqual(conv_data["last_message_sender"], self.user.id)

        # Bob sends a newer message — last_message should update
        msg2 = MessageEnvelope.objects.create(
            conversation=conversation, sender=self.other,
            ciphertext="ZmFrZQ==", nonce=b64_bytes(12), aad="", message_index=2,
        )

        response = self.client.get("/api/conversations/")
        conv_data = next(c for c in response.data if c["id"] == conversation.id)
        self.assertEqual(conv_data["last_message_id"], msg2.id)
        self.assertEqual(conv_data["last_message_sender"], self.other.id)


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

    def test_attachment_download_requires_conversation_membership(self):
        created = self._post_attachment()
        self.assertEqual(created.status_code, 201)
        attachment_id = created.data["id"]

        outsider_client = APIClient()
        outsider_token = outsider_client.post(
            "/api/auth/login/", {"username": "charlie", "password": "testpass123"}, format="json"
        ).data["access"]
        outsider_client.credentials(HTTP_AUTHORIZATION=f"Bearer {outsider_token}")

        response = outsider_client.get(f"/api/attachments/{attachment_id}/download/")
        self.assertEqual(response.status_code, 404)

    def test_attachment_download_returns_encrypted_blob_for_member(self):
        created = self._post_attachment()
        self.assertEqual(created.status_code, 201)
        attachment_id = created.data["id"]

        response = self.client.get(f"/api/attachments/{attachment_id}/download/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/octet-stream")
        self.assertGreater(int(response["Content-Length"]), 0)


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


class VideoSignalingHandshakeTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="testpass123")
        self.bob = User.objects.create_user(username="bob", password="testpass123")
        self.client = APIClient()

        self.alice_token = self.client.post(
            "/api/auth/login/", {"username": "alice", "password": "testpass123"}, format="json"
        ).data["access"]
        self.bob_token = self.client.post(
            "/api/auth/login/", {"username": "bob", "password": "testpass123"}, format="json"
        ).data["access"]

        self.conversation = Conversation.objects.create(
            kind=Conversation.TYPE_DM,
            title="dm",
            created_by=self.alice,
        )
        ConversationMember.objects.create(conversation=self.conversation, user=self.alice)
        ConversationMember.objects.create(conversation=self.conversation, user=self.bob)

    def test_two_user_start_join_signal_workflow(self):
        async def scenario():
            async def receive_until_type(communicator, expected_type: str):
                while True:
                    message = await communicator.receive_json_from()
                    if message["type"] == expected_type:
                        return message

            alice = WebsocketCommunicator(
                application,
                f"/ws/video/conversations/{self.conversation.id}/?token={self.alice_token}",
            )
            bob = WebsocketCommunicator(
                application,
                f"/ws/video/conversations/{self.conversation.id}/?token={self.bob_token}",
            )

            connected_alice, _ = await alice.connect()
            connected_bob, _ = await bob.connect()
            self.assertTrue(connected_alice)
            self.assertTrue(connected_bob)

            alice_session = await alice.receive_json_from()
            bob_session = await bob.receive_json_from()
            self.assertEqual(alice_session["type"], "session")
            self.assertEqual(bob_session["type"], "session")

            alice_session_id = alice_session["payload"]["signaling_session_id"]
            bob_session_id = bob_session["payload"]["signaling_session_id"]
            self.assertTrue(alice_session_id)
            self.assertTrue(bob_session_id)
            self.assertNotEqual(alice_session_id, bob_session_id)

            await alice.send_json_to(
                {
                    "type": "offer",
                    "payload": {"type": "offer", "sdp": "fake-offer-sdp"},
                    "client_id": "alice-client",
                    "sequence": 1,
                    "signaling_session_id": alice_session_id,
                }
            )

            bob_offer = await bob.receive_json_from()
            self.assertEqual(bob_offer["type"], "offer")
            self.assertEqual(bob_offer["sender_client_id"], "alice-client")
            self.assertEqual(bob_offer["payload"]["type"], "offer")

            await bob.send_json_to(
                {
                    "type": "ready",
                    "payload": {"ok": True},
                    "client_id": "bob-client",
                    "sequence": 1,
                    "signaling_session_id": bob_session_id,
                }
            )

            alice_ready = await receive_until_type(alice, "ready")
            self.assertEqual(alice_ready["type"], "ready")
            self.assertEqual(alice_ready["sender_client_id"], "bob-client")

            await bob.send_json_to(
                {
                    "type": "answer",
                    "payload": {"type": "answer", "sdp": "fake-answer-sdp"},
                    "client_id": "bob-client",
                    "sequence": 2,
                    "signaling_session_id": bob_session_id,
                }
            )

            alice_answer = await receive_until_type(alice, "answer")
            self.assertEqual(alice_answer["type"], "answer")
            self.assertEqual(alice_answer["payload"]["type"], "answer")

            await alice.send_json_to(
                {
                    "type": "ice",
                    "payload": {"candidate": "candidate:1 1 UDP 1 0.0.0.0 9 typ host", "sdpMid": "0", "sdpMLineIndex": 0},
                    "client_id": "alice-client",
                    "sequence": 2,
                    "signaling_session_id": alice_session_id,
                }
            )

            bob_ice = await receive_until_type(bob, "ice")
            self.assertEqual(bob_ice["type"], "ice")
            self.assertEqual(bob_ice["sender_client_id"], "alice-client")

            await alice.disconnect()
            await bob.disconnect()

        async_to_sync(scenario)()

    def test_sender_offer_is_echoed_and_peer_also_receives_offer(self):
        async def scenario():
            alice = WebsocketCommunicator(
                application,
                f"/ws/video/conversations/{self.conversation.id}/?token={self.alice_token}",
            )
            bob = WebsocketCommunicator(
                application,
                f"/ws/video/conversations/{self.conversation.id}/?token={self.bob_token}",
            )

            connected_alice, _ = await alice.connect()
            connected_bob, _ = await bob.connect()
            self.assertTrue(connected_alice)
            self.assertTrue(connected_bob)

            alice_session = await alice.receive_json_from()
            bob_session = await bob.receive_json_from()
            alice_session_id = alice_session["payload"]["signaling_session_id"]

            await alice.send_json_to(
                {
                    "type": "offer",
                    "payload": {"type": "offer", "sdp": "fake-offer-sdp"},
                    "client_id": "alice-client",
                    "sequence": 1,
                    "signaling_session_id": alice_session_id,
                }
            )

            alice_echo = await alice.receive_json_from()
            bob_offer = await bob.receive_json_from()

            self.assertEqual(alice_echo["type"], "offer")
            self.assertEqual(alice_echo["sender_client_id"], "alice-client")
            self.assertEqual(alice_echo["payload"]["type"], "offer")

            self.assertEqual(bob_offer["type"], "offer")
            self.assertEqual(bob_offer["sender_client_id"], "alice-client")
            self.assertEqual(bob_offer["payload"]["type"], "offer")

            await alice.disconnect()
            await bob.disconnect()

        async_to_sync(scenario)()

    def test_offer_before_join_can_be_resent_after_ready(self):
        async def scenario():
            async def receive_until_type(communicator, expected_type: str):
                while True:
                    message = await communicator.receive_json_from()
                    if message["type"] == expected_type:
                        return message

            alice = WebsocketCommunicator(
                application,
                f"/ws/video/conversations/{self.conversation.id}/?token={self.alice_token}",
            )
            bob = WebsocketCommunicator(
                application,
                f"/ws/video/conversations/{self.conversation.id}/?token={self.bob_token}",
            )

            connected_alice, _ = await alice.connect()
            connected_bob, _ = await bob.connect()
            self.assertTrue(connected_alice)
            self.assertTrue(connected_bob)

            alice_session = await alice.receive_json_from()
            bob_session = await bob.receive_json_from()
            alice_session_id = alice_session["payload"]["signaling_session_id"]
            bob_session_id = bob_session["payload"]["signaling_session_id"]

            await alice.send_json_to(
                {
                    "type": "offer",
                    "payload": {"type": "offer", "sdp": "first-offer-sdp"},
                    "client_id": "alice-client",
                    "sequence": 1,
                    "signaling_session_id": alice_session_id,
                }
            )

            alice_echo = await alice.receive_json_from()
            bob_first_offer = await bob.receive_json_from()
            self.assertEqual(alice_echo["type"], "offer")
            self.assertEqual(bob_first_offer["type"], "offer")
            self.assertEqual(bob_first_offer["payload"]["sdp"], "first-offer-sdp")

            await bob.send_json_to(
                {
                    "type": "ready",
                    "payload": {"ok": True},
                    "client_id": "bob-client",
                    "sequence": 1,
                    "signaling_session_id": bob_session_id,
                }
            )

            alice_ready = await receive_until_type(alice, "ready")
            self.assertEqual(alice_ready["sender_client_id"], "bob-client")

            await alice.send_json_to(
                {
                    "type": "offer",
                    "payload": {"type": "offer", "sdp": "resent-offer-sdp"},
                    "client_id": "alice-client",
                    "sequence": 2,
                    "signaling_session_id": alice_session_id,
                }
            )

            alice_echo_resent = await alice.receive_json_from()
            bob_resent_offer = await receive_until_type(bob, "offer")
            self.assertEqual(alice_echo_resent["type"], "offer")
            self.assertEqual(bob_resent_offer["type"], "offer")
            self.assertEqual(bob_resent_offer["payload"]["sdp"], "resent-offer-sdp")

            await alice.disconnect()
            await bob.disconnect()

        async_to_sync(scenario)()


class ConversationLeaveTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.alice = User.objects.create_user(username="alice", password="testpass123")
        self.bob = User.objects.create_user(username="bob", password="testpass123")
        self.charlie = User.objects.create_user(username="charlie", password="testpass123")

        # Authenticate as Alice by default
        token = self.client.post(
            "/api/auth/login/", {"username": "alice", "password": "testpass123"}, format="json"
        ).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_leave_conversation_success_for_member(self):
        conversation = Conversation.objects.create(kind=Conversation.TYPE_DM, title="dm", created_by=self.alice)
        ConversationMember.objects.create(conversation=conversation, user=self.alice)
        ConversationMember.objects.create(conversation=conversation, user=self.bob)

        response = self.client.post(f"/api/conversations/{conversation.id}/leave/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Left conversation successfully", response.data["detail"])
        
        # Verify Alice is no longer a member
        self.assertFalse(ConversationMember.objects.filter(conversation=conversation, user=self.alice).exists())
        
        # Verify Bob is still a member  
        self.assertTrue(ConversationMember.objects.filter(conversation=conversation, user=self.bob).exists())

    def test_leave_conversation_deletes_user_messages(self):
        conversation = Conversation.objects.create(kind=Conversation.TYPE_DM, title="dm", created_by=self.alice)
        ConversationMember.objects.create(conversation=conversation, user=self.alice)
        ConversationMember.objects.create(conversation=conversation, user=self.bob)

        # Alice sends messages
        alice_msg1 = MessageEnvelope.objects.create(
            conversation=conversation, sender=self.alice, ciphertext="alice1", nonce=b64_bytes(12), aad="", message_index=1
        )
        alice_msg2 = MessageEnvelope.objects.create(
            conversation=conversation, sender=self.alice, ciphertext="alice2", nonce=b64_bytes(12), aad="", message_index=2
        )
        
        # Bob sends a message
        bob_msg = MessageEnvelope.objects.create(
            conversation=conversation, sender=self.bob, ciphertext="bob1", nonce=b64_bytes(12), aad="", message_index=3
        )

        response = self.client.post(f"/api/conversations/{conversation.id}/leave/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["messages_deleted"], 2)

        # Verify Alice's messages are deleted
        self.assertFalse(MessageEnvelope.objects.filter(id=alice_msg1.id).exists())
        self.assertFalse(MessageEnvelope.objects.filter(id=alice_msg2.id).exists())
        
        # Verify Bob's message remains
        self.assertTrue(MessageEnvelope.objects.filter(id=bob_msg.id).exists())

    def test_leave_conversation_auto_deletes_when_no_members_remain(self):
        conversation = Conversation.objects.create(kind=Conversation.TYPE_DM, title="dm", created_by=self.alice)
        ConversationMember.objects.create(conversation=conversation, user=self.alice)

        response = self.client.post(f"/api/conversations/{conversation.id}/leave/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["conversation_deleted"])

        # Verify conversation is deleted
        self.assertFalse(Conversation.objects.filter(id=conversation.id).exists())


