import os
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Conversation, ConversationMember, SecurityAdminAccountState, SecurityJourneyReport


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
        state = SecurityAdminAccountState.objects.get(user=user)
        self.assertTrue(state.must_reset_password)

    def test_bootstrap_skips_if_admin_exists_and_reconcile_disabled(self):
        User.objects.create_superuser(username="existing", email="existing@example.com", password="testpass123")

        env = {
            "BOOTSTRAP_ADMIN_ENABLED": "1",
            "BOOTSTRAP_ADMIN_USERNAME": "newadmin",
            "BOOTSTRAP_ADMIN_EMAIL": "newadmin@example.com",
            "BOOTSTRAP_ADMIN_PASSWORD": "VeryStrongPass123!",
            "BOOTSTRAP_ADMIN_GROUP": "security_admin",
            "BOOTSTRAP_ADMIN_ALLOW_RECONCILE": "0",
        }
        with patch.dict(os.environ, env, clear=False):
            call_command("bootstrap_admin")

        self.assertFalse(User.objects.filter(username="newadmin").exists())


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
        SecurityAdminAccountState.objects.update_or_create(
            user=admin,
            defaults={"must_reset_password": False, "bootstrap_source": "test"},
        )
        token = self._login(admin.username, "testpass123")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.get("/api/admin/security/status/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["admin_security_access"], "ok")

    def test_admin_security_status_denied_if_password_reset_required(self):
        admin = User.objects.create_superuser(username="admin2", email="admin2@example.com", password="testpass123")
        SecurityAdminAccountState.objects.update_or_create(
            user=admin,
            defaults={"must_reset_password": True, "bootstrap_source": "test"},
        )
        token = self._login(admin.username, "testpass123")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.get("/api/admin/security/status/")
        self.assertEqual(response.status_code, 403)


class PasswordResetTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(username="pwadmin", email="pwadmin@example.com", password="testpass123")
        SecurityAdminAccountState.objects.update_or_create(
            user=self.admin,
            defaults={"must_reset_password": True, "bootstrap_source": "docker_bootstrap"},
        )

    def _auth(self):
        token = self.client.post(
            "/api/auth/login/", {"username": "pwadmin", "password": "testpass123"}, format="json"
        ).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_password_reset_clears_must_reset_flag(self):
        self._auth()
        response = self.client.post(
            "/api/auth/password-reset/",
            {"old_password": "testpass123", "new_password": "NewStrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        state = SecurityAdminAccountState.objects.get(user=self.admin)
        self.assertFalse(state.must_reset_password)


class Stage2SecurityJourneyApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(username="secadmin", email="sec@example.com", password="testpass123")
        SecurityAdminAccountState.objects.update_or_create(
            user=self.admin,
            defaults={"must_reset_password": False, "bootstrap_source": "test"},
        )
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

        scope_resp = self.client.post(
            "/api/admin/security/scope-coverage/",
            {
                "report": report_id,
                "area": "TURN/STUN usage",
                "present_in_implementation": True,
                "evidence": "frontend/src/stores/video.ts",
                "notes": "Candidate handling implemented.",
            },
            format="json",
        )
        self.assertEqual(scope_resp.status_code, 201)

        self.assertTrue(SecurityJourneyReport.objects.filter(id=report_id, created_by=self.admin).exists())


class Stage3LoggingAndThreatApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(username="secadmin3", email="sec3@example.com", password="testpass123")
        SecurityAdminAccountState.objects.update_or_create(
            user=self.admin,
            defaults={"must_reset_password": False, "bootstrap_source": "test"},
        )
        self.member = User.objects.create_user(username="member3", password="testpass123")

    def _auth(self, username: str, password: str):
        token = self.client.post(
            "/api/auth/login/", {"username": username, "password": password}, format="json"
        ).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _create_report(self) -> int:
        response = self.client.post(
            "/api/admin/security/reports/",
            {
                "title": "Stage 3 Report",
                "flow_type": "both",
                "status": "draft",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        return response.data["id"]

    def test_non_admin_cannot_access_stage3_endpoints(self):
        self._auth("member3", "testpass123")
        logging_resp = self.client.get("/api/admin/security/logging-policies/")
        threat_resp = self.client.get("/api/admin/security/threat-model/")
        self.assertEqual(logging_resp.status_code, 403)
        self.assertEqual(threat_resp.status_code, 403)

    def test_admin_can_create_logging_policy_and_threat_item(self):
        self._auth("secadmin3", "testpass123")
        report_id = self._create_report()

        logging_resp = self.client.post(
            "/api/admin/security/logging-policies/",
            {
                "report": report_id,
                "field_name": "message_body",
                "classification": "forbidden",
                "rationale": "Never log plaintext message content.",
            },
            format="json",
        )
        self.assertEqual(logging_resp.status_code, 201)

        threat_resp = self.client.post(
            "/api/admin/security/threat-model/",
            {
                "report": report_id,
                "flow_type": "dm",
                "threat": "Passive network attacker",
                "affected_stages": "DM-transport",
                "likely_indicators": "Unexpected cert warnings",
                "controls": "TLS pinning, cert monitoring",
                "residual_risk": "Compromised endpoint still leaks content",
                "severity": "high",
            },
            format="json",
        )
        self.assertEqual(threat_resp.status_code, 201)

        list_resp = self.client.get(f"/api/admin/security/threat-model/?report={report_id}&flow_type=dm")
        self.assertEqual(list_resp.status_code, 200)
        self.assertGreaterEqual(len(list_resp.data), 1)


class Stage4CompiledReportApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(username="secadmin4", email="sec4@example.com", password="testpass123")
        SecurityAdminAccountState.objects.update_or_create(
            user=self.admin,
            defaults={"must_reset_password": False, "bootstrap_source": "test"},
        )
        self.member = User.objects.create_user(username="member4", password="testpass123")

    def _auth(self, username: str, password: str):
        token = self.client.post(
            "/api/auth/login/", {"username": username, "password": password}, format="json"
        ).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_non_admin_cannot_access_compiled_report(self):
        self._auth("member4", "testpass123")

        report_resp = self.client.post(
            "/api/admin/security/reports/",
            {"title": "should fail", "flow_type": "both", "status": "draft"},
            format="json",
        )
        self.assertEqual(report_resp.status_code, 403)

    def test_admin_can_compile_report_with_gaps_and_next_tests(self):
        self._auth("secadmin4", "testpass123")

        report_resp = self.client.post(
            "/api/admin/security/reports/",
            {
                "title": "Stage 4 compilation",
                "flow_type": "both",
                "status": "draft",
                "executive_summary": "Exec summary",
                "reality_check_answers": {"can_server_read_media": "unknown"},
            },
            format="json",
        )
        self.assertEqual(report_resp.status_code, 201)
        report_id = report_resp.data["id"]

        gap_resp = self.client.post(
            "/api/admin/security/gaps/",
            {
                "report": report_id,
                "rank": 1,
                "title": "TURN relay misconfiguration risk",
                "description": "Potential metadata overexposure via relay logs",
                "severity": "high",
                "recommended_remediation": "Harden relay logging and credential TTL",
            },
            format="json",
        )
        self.assertEqual(gap_resp.status_code, 201)

        test_resp = self.client.post(
            "/api/admin/security/next-tests/",
            {
                "report": report_id,
                "priority": "high",
                "name": "TURN forced-path packet capture",
                "scope": "video",
                "method": "Force relay candidates and inspect server-side observability",
                "pass_fail_criteria": "No plaintext media or secrets visible",
            },
            format="json",
        )
        self.assertEqual(test_resp.status_code, 201)

        compiled_resp = self.client.get(f"/api/admin/security/reports/{report_id}/compiled/")
        self.assertEqual(compiled_resp.status_code, 200)
        self.assertIn("executive_summary", compiled_resp.data)
        self.assertIn("dm_stage_by_stage_journey", compiled_resp.data)
        self.assertIn("video_stage_by_stage_journey", compiled_resp.data)
        self.assertIn("verification_matrix", compiled_resp.data)
        self.assertIn("scope_coverage", compiled_resp.data)
        self.assertIn("logging_design", compiled_resp.data)
        self.assertIn("top_10_likely_security_gaps", compiled_resp.data)
        self.assertIn("highest_value_next_tests", compiled_resp.data)
        self.assertIn("threat_model", compiled_resp.data)
        self.assertIn("reality_check_answers", compiled_resp.data)
        self.assertIn("is_system_truly_e2ee_or_transport_only", compiled_resp.data["reality_check_answers"])
        self.assertEqual(
            compiled_resp.data["reality_check_answers"].get("can_server_read_dm_bodies"),
            "unknown/unverified",
        )


class Stage5AuditAndRetentionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(username="secadmin5", email="sec5@example.com", password="testpass123")
        SecurityAdminAccountState.objects.update_or_create(
            user=self.admin,
            defaults={"must_reset_password": False, "bootstrap_source": "test"},
        )
        self.member = User.objects.create_user(username="member5", password="testpass123")

    def _auth(self, username: str, password: str):
        token = self.client.post(
            "/api/auth/login/", {"username": username, "password": password}, format="json"
        ).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_compiled_and_export_emit_audit_events(self):
        self._auth("secadmin5", "testpass123")
        report_resp = self.client.post(
            "/api/admin/security/reports/",
            {"title": "Stage 5", "flow_type": "both", "status": "draft"},
            format="json",
        )
        self.assertEqual(report_resp.status_code, 201)
        report_id = report_resp.data["id"]

        compiled_resp = self.client.get(f"/api/admin/security/reports/{report_id}/compiled/")
        self.assertEqual(compiled_resp.status_code, 200)

        export_resp = self.client.get(f"/api/admin/security/reports/{report_id}/export/")
        self.assertEqual(export_resp.status_code, 200)

        audit_resp = self.client.get(f"/api/admin/security/audit-events/?report={report_id}")
        self.assertEqual(audit_resp.status_code, 200)
        actions = [item["action"] for item in audit_resp.data]
        self.assertIn("compiled_view", actions)
        self.assertIn("export", actions)

    def test_admin_can_trigger_analysis_run_without_content_access(self):
        self._auth("secadmin5", "testpass123")
        report_resp = self.client.post(
            "/api/admin/security/reports/",
            {"title": "Run report", "flow_type": "both", "status": "draft"},
            format="json",
        )
        self.assertEqual(report_resp.status_code, 201)
        report_id = report_resp.data["id"]

        run_resp = self.client.post(
            "/api/admin/security/run/",
            {"report_id": report_id, "requested_checks": ["dm", "video", "logging"]},
            format="json",
        )
        self.assertEqual(run_resp.status_code, 202)
        self.assertTrue(run_resp.data["no_content_read_mode"])

        audit_resp = self.client.get(f"/api/admin/security/audit-events/?report={report_id}&action=run_triggered")
        self.assertEqual(audit_resp.status_code, 200)
        self.assertGreaterEqual(len(audit_resp.data), 1)

    def test_non_admin_cannot_read_audit_events(self):
        self._auth("member5", "testpass123")
        response = self.client.get("/api/admin/security/audit-events/")
        self.assertEqual(response.status_code, 403)

    @patch.dict(os.environ, {"SECURITY_ANALYSIS_RETENTION_DAYS": "0"}, clear=False)
    def test_retention_purge_command_executes(self):
        self._auth("secadmin5", "testpass123")
        report_resp = self.client.post(
            "/api/admin/security/reports/",
            {"title": "Old report", "flow_type": "both", "status": "draft"},
            format="json",
        )
        self.assertEqual(report_resp.status_code, 201)

        call_command("purge_security_analysis_artifacts")


class Stage6SnapshotTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(username="secadmin6", email="sec6@example.com", password="testpass123")
        SecurityAdminAccountState.objects.update_or_create(
            user=self.admin,
            defaults={"must_reset_password": False, "bootstrap_source": "test"},
        )
        self.member = User.objects.create_user(username="member6", password="testpass123")

    def _auth(self, username: str, password: str):
        token = self.client.post(
            "/api/auth/login/", {"username": username, "password": password}, format="json"
        ).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_admin_can_create_and_list_snapshot(self):
        self._auth("secadmin6", "testpass123")
        report_resp = self.client.post(
            "/api/admin/security/reports/",
            {"title": "Stage 6", "flow_type": "both", "status": "draft"},
            format="json",
        )
        self.assertEqual(report_resp.status_code, 201)
        report_id = report_resp.data["id"]

        snapshot_resp = self.client.post(
            f"/api/admin/security/reports/{report_id}/snapshots/",
            {"notes": "baseline snapshot"},
            format="json",
        )
        self.assertEqual(snapshot_resp.status_code, 201)
        self.assertEqual(len(snapshot_resp.data["payload_sha256"]), 64)

        list_resp = self.client.get(f"/api/admin/security/snapshots/?report={report_id}")
        self.assertEqual(list_resp.status_code, 200)
        self.assertGreaterEqual(len(list_resp.data), 1)

        audit_resp = self.client.get(f"/api/admin/security/audit-events/?report={report_id}&action=snapshot_create")
        self.assertEqual(audit_resp.status_code, 200)
        self.assertGreaterEqual(len(audit_resp.data), 1)

        snapshot_id = snapshot_resp.data["id"]
        verify_resp = self.client.get(f"/api/admin/security/snapshots/{snapshot_id}/verify/")
        self.assertEqual(verify_resp.status_code, 200)
        self.assertTrue(verify_resp.data["match"])

    def test_non_admin_cannot_access_snapshot_endpoints(self):
        self._auth("member6", "testpass123")
        list_resp = self.client.get("/api/admin/security/snapshots/")
        self.assertEqual(list_resp.status_code, 403)


class Stage7AdminMenuApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(username="secadmin7", email="sec7@example.com", password="testpass123")
        SecurityAdminAccountState.objects.update_or_create(
            user=self.admin,
            defaults={"must_reset_password": False, "bootstrap_source": "test"},
        )
        self.member = User.objects.create_user(username="member7", password="testpass123")

    def _auth(self, username: str, password: str):
        token = self.client.post(
            "/api/auth/login/", {"username": username, "password": password}, format="json"
        ).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_me_includes_security_admin_flag(self):
        self._auth("secadmin7", "testpass123")
        me_resp = self.client.get("/api/auth/me/")
        self.assertEqual(me_resp.status_code, 200)
        self.assertTrue(me_resp.data["is_security_admin"])

    def test_dashboard_and_run_lifecycle(self):
        self._auth("secadmin7", "testpass123")
        report_resp = self.client.post(
            "/api/admin/security/reports/",
            {"title": "Stage 7", "flow_type": "both", "status": "draft"},
            format="json",
        )
        self.assertEqual(report_resp.status_code, 201)
        report_id = report_resp.data["id"]

        run_resp = self.client.post(
            "/api/admin/security/run/",
            {
                "report_id": report_id,
                "flow_type": "both",
                "requested_checks": ["dm", "video", "logging"],
            },
            format="json",
        )
        self.assertEqual(run_resp.status_code, 202)
        self.assertEqual(run_resp.data["run_status"], "completed")

        runs_resp = self.client.get(f"/api/admin/security/runs/?report={report_id}")
        self.assertEqual(runs_resp.status_code, 200)
        self.assertGreaterEqual(len(runs_resp.data), 1)

        dashboard_resp = self.client.get(f"/api/admin/security/dashboard/?report={report_id}")
        self.assertEqual(dashboard_resp.status_code, 200)
        self.assertIn("latest_run", dashboard_resp.data)
        self.assertIn("recent_runs", dashboard_resp.data)

        menu_resp = self.client.get("/api/admin/security/menu/")
        self.assertEqual(menu_resp.status_code, 200)
        self.assertGreaterEqual(len(menu_resp.data.get("sections", [])), 10)

    def test_non_admin_cannot_access_dashboard_or_runs(self):
        self._auth("member7", "testpass123")
        dashboard_resp = self.client.get("/api/admin/security/dashboard/")
        runs_resp = self.client.get("/api/admin/security/runs/")
        self.assertEqual(dashboard_resp.status_code, 403)
        self.assertEqual(runs_resp.status_code, 403)
