import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import ConversationMember


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.group_name = f"conversation_{self.conversation_id}"

        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return

        is_member = await self._is_member(user.id, self.conversation_id)
        if not is_member:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Clients send messages via REST; socket is used for push fanout.
        if text_data:
            await self.send(text_data=json.dumps({"type": "ack", "status": "ok"}))

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({"type": "message", "payload": event["message"]}))

    @database_sync_to_async
    def _is_member(self, user_id: int, conversation_id: int) -> bool:
        return ConversationMember.objects.filter(conversation_id=conversation_id, user_id=user_id).exists()


class VideoSignalingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.group_name = f"video_conversation_{self.conversation_id}"

        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return

        is_member = await self._is_member(user.id, self.conversation_id)
        if not is_member:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"type": "error", "detail": "invalid_json"}))
            return

        event_type = payload.get("type")
        if event_type not in {"ready", "offer", "answer", "ice", "hangup"}:
            await self.send(text_data=json.dumps({"type": "error", "detail": "invalid_type"}))
            return

        relay_payload = {
            "type": event_type,
            "payload": payload.get("payload", {}),
            "sender_id": self.scope["user"].id,
            "sender_client_id": payload.get("client_id"),
        }
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "video.signal", "message": relay_payload},
        )

    async def video_signal(self, event):
        await self.send(text_data=json.dumps(event["message"]))

    @database_sync_to_async
    def _is_member(self, user_id: int, conversation_id: int) -> bool:
        return ConversationMember.objects.filter(conversation_id=conversation_id, user_id=user_id).exists()
