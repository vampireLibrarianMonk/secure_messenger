import os
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Conversation, ConversationMember, SecurityJourneyReport


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
                "nonce": "bm9uY2U=",
                "aad": "",
                "message_index": 1,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["ciphertext"], "ZmFrZQ==")


class AdminBootstrapTests(TestCase):
    def test_bootstrap_admin_creates_and_is_idempotent(self):
        env = {
            "BOOTSTRAP_ADMIN_ENABLED": "1",
            "BOOTSTRAP_ADMIN_USERNAME": "secadmin",
            "BOOTSTRAP_ADMIN_EMAIL": "secadmin@example.com",
            "BOOTSTRAP_ADMIN_PASSWORD": "VeryStrongPass123!",
            "BOOTSTRAP_ADMIN_GROUP": "security_admin",
        }
        with patch.dict(os.environ, env, clear=False):
            call_command("bootstrap_admin")
            call_command("bootstrap_admin")

        users = User.objects.filter(username="secadmin")
        self.assertEqual(users.count(), 1)
        user = users.first()
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.groups.filter(name="security_admin").exists())


class AdminSecurityEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _login(self, username: str, password: str) -> str:
        return self.client.post(
            "/api/auth/login/", {"username": username, "password": password}, format="json"
        ).data["access"]

    def test_admin_security_status_requires_security_admin(self):
        user = User.objects.create_user(username="alice", password="testpass123")
        token = self._login(user.username, "testpass123")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.get("/api/admin/security/status/")
        self.assertEqual(response.status_code, 403)

    def test_admin_security_status_allows_superuser(self):
        admin = User.objects.create_superuser(username="admin", email="admin@example.com", password="testpass123")
        token = self._login(admin.username, "testpass123")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.get("/api/admin/security/status/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["admin_security_access"], "ok")


class Stage2SecurityJourneyApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(username="secadmin", email="sec@example.com", password="testpass123")
        self.member = User.objects.create_user(username="member", password="testpass123")

    def _auth(self, username: str, password: str):
        token = self.client.post(
            "/api/auth/login/", {"username": username, "password": password}, format="json"
        ).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_non_admin_cannot_access_security_journey_reports(self):
        self._auth("member", "testpass123")
        response = self.client.get("/api/admin/security/reports/")
        self.assertEqual(response.status_code, 403)

    def test_admin_can_create_report_stage_and_matrix_item(self):
        self._auth("secadmin", "testpass123")

        report_resp = self.client.post(
            "/api/admin/security/reports/",
            {
                "title": "DM + Video exploratory review",
                "flow_type": "both",
                "status": "draft",
                "executive_summary": "Initial draft.",
                "reality_check_answers": {"is_e2ee": "unknown"},
            },
            format="json",
        )
        self.assertEqual(report_resp.status_code, 201)
        report_id = report_resp.data["id"]

        stage_resp = self.client.post(
            "/api/admin/security/stages/",
            {
                "report": report_id,
                "flow_type": "dm",
                "stage_number": 1,
                "stage_name": "User authenticated",
                "component": "Auth API",
                "protocol": "HTTPS",
                "security_assumptions": "JWT validation and TLS are correctly configured.",
                "severity_if_compromised": "high",
            },
            format="json",
        )
        self.assertEqual(stage_resp.status_code, 201)
        stage_id = stage_resp.data["id"]

        matrix_resp = self.client.post(
            "/api/admin/security/verification-matrix/",
            {
                "report": report_id,
                "stage": stage_id,
                "stage_label": "DM-1",
                "expected_security_property": "Only authenticated users can submit messages.",
                "evidence_source": "Auth middleware logs",
                "how_to_test": "Attempt unauthenticated POST /api/messages/",
                "pass_fail_criteria": "Must return 401/403",
                "common_misconfiguration": "AllowAny accidentally applied",
                "recommended_remediation": "Restore IsAuthenticated and add regression tests",
            },
            format="json",
        )
        self.assertEqual(matrix_resp.status_code, 201)

        self.assertTrue(SecurityJourneyReport.objects.filter(id=report_id, created_by=self.admin).exists())
