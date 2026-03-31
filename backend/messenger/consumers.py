import json
import uuid

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import Conversation, ConversationMember, SessionEvent


def _validate_video_signal_message(
    payload: dict,
    *,
    required_session_id: str,
    last_control_nonce: int | None,
    last_sequence: int | None,
) -> tuple[bool, str | None]:
    event_type = payload.get("type")
    if event_type not in {"ready", "offer", "answer", "ice", "hangup", "rekey_update"}:
        return False, "invalid_type"

    sender_client_id = payload.get("client_id")
    if not isinstance(sender_client_id, str) or not sender_client_id.strip():
        return False, "missing_client_id"

    signaling_session_id = payload.get("signaling_session_id")
    if not isinstance(signaling_session_id, str) or signaling_session_id != required_session_id:
        return False, "invalid_signaling_session"

    sequence = payload.get("sequence")
    if not isinstance(sequence, int) or sequence < 1:
        return False, "invalid_sequence"
    if last_sequence is not None and sequence <= last_sequence:
        return False, "replayed_sequence"

    if event_type != "rekey_update":
        return True, None

    event_payload = payload.get("payload")
    if not isinstance(event_payload, dict):
        return False, "invalid_rekey_payload"

    epoch = event_payload.get("epoch")
    if not isinstance(epoch, int) or epoch < 1:
        return False, "invalid_rekey_epoch"

    control_nonce = event_payload.get("control_nonce")
    if not isinstance(control_nonce, int) or control_nonce < 1:
        return False, "invalid_control_nonce"

    if last_control_nonce is not None and control_nonce <= last_control_nonce:
        return False, "replayed_control_nonce"

    return True, None


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

    async def chat_member_left(self, event):
        await self.send(text_data=json.dumps({
            "type": "member_left",
            "payload": {
                "user_id": event["user_id"],
                "messages_deleted": event["messages_deleted"],
                "attachments_deleted": event["attachments_deleted"],
            }
        }))

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
        self._signaling_session_id = str(uuid.uuid4())
        self._latest_control_nonce_by_client: dict[str, int] = {}
        self._latest_sequence_by_client: dict[str, int] = {}
        await self.send(
            text_data=json.dumps(
                {
                    "type": "session",
                    "payload": {"signaling_session_id": self._signaling_session_id},
                }
            )
        )

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

        sender_client_id = payload.get("client_id")
        last_nonce = None
        last_sequence = None
        if isinstance(sender_client_id, str) and sender_client_id:
            last_nonce = self._latest_control_nonce_by_client.get(sender_client_id)
            last_sequence = self._latest_sequence_by_client.get(sender_client_id)

        is_valid, error_code = _validate_video_signal_message(
            payload,
            required_session_id=self._signaling_session_id,
            last_control_nonce=last_nonce,
            last_sequence=last_sequence,
        )
        if not is_valid:
            await self.send(text_data=json.dumps({"type": "error", "detail": error_code or "invalid_type"}))
            return

        sender_client_id = payload.get("client_id")
        sequence = int(payload.get("sequence"))
        self._latest_sequence_by_client[str(sender_client_id)] = sequence

        event_type = payload.get("type")

        if event_type == "rekey_update":
            is_group = await self._is_group_conversation(self.conversation_id)
            if not is_group:
                await self.send(text_data=json.dumps({"type": "error", "detail": "rekey_update_not_supported_for_non_group"}))
                return

            if not isinstance(sender_client_id, str) or not sender_client_id:
                await self.send(text_data=json.dumps({"type": "error", "detail": "missing_client_id"}))
                return

            epoch = int(payload["payload"]["epoch"])
            current_epoch = await self._current_group_epoch(self.conversation_id)
            if epoch < current_epoch:
                await self.send(text_data=json.dumps({"type": "error", "detail": "stale_rekey_epoch"}))
                return

            control_nonce = int(payload["payload"]["control_nonce"])
            self._latest_control_nonce_by_client[sender_client_id] = control_nonce

            if epoch > current_epoch:
                await self._record_group_epoch(self.scope["user"].id, self.conversation_id, epoch)

        relay_payload = {
            "type": event_type,
            "payload": payload.get("payload", {}),
            "sender_id": self.scope["user"].id,
            "sender_client_id": sender_client_id,
            "signaling_session_id": self._signaling_session_id,
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

    @database_sync_to_async
    def _is_group_conversation(self, conversation_id: int) -> bool:
        return Conversation.objects.filter(id=conversation_id, kind=Conversation.TYPE_GROUP).exists()

    @database_sync_to_async
    def _current_group_epoch(self, conversation_id: int) -> int:
        conversation = Conversation.objects.filter(id=conversation_id).first()
        if not conversation or conversation.kind != Conversation.TYPE_GROUP:
            return 0

        event = (
            SessionEvent.objects.filter(
                event_type=SessionEvent.EVENT_REVOKE,
                metadata__category="group_key_epoch",
                metadata__conversation_id=conversation_id,
            )
            .order_by("-created_at")
            .first()
        )
        if not event:
            return 1

        epoch = (event.metadata or {}).get("epoch", 1)
        return int(epoch) if isinstance(epoch, int) and epoch >= 1 else 1

    @database_sync_to_async
    def _record_group_epoch(self, user_id: int, conversation_id: int, epoch: int) -> None:
        SessionEvent.objects.create(
            user_id=user_id,
            event_type=SessionEvent.EVENT_REVOKE,
            metadata={
                "category": "group_key_epoch",
                "conversation_id": conversation_id,
                "epoch": epoch,
                "reason": "video_rekey_update",
            },
        )
