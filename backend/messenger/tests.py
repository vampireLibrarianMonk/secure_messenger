import os
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Conversation, ConversationMember


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
