from django.contrib.auth.models import User
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
