import { defineStore } from "pinia";
import { apiRequest, websocketUrl } from "../lib/api";
import { decryptText } from "../lib/crypto";
import { useAuthStore } from "./auth";
import { useSecurityStore } from "./security";
import type { Conversation, MessageEnvelope } from "../types";

interface DecryptedMessage extends MessageEnvelope {
  plaintext: string;
}

interface ChatState {
  conversations: Conversation[];
  messagesByConversation: Record<number, DecryptedMessage[]>;
  activeConversationId: number | null;
  ws: WebSocket | null;
}

export const useChatStore = defineStore("chat", {
  state: (): ChatState => ({
    conversations: [],
    messagesByConversation: {},
    activeConversationId: null,
    ws: null,
  }),
  getters: {
    activeMessages(state): DecryptedMessage[] {
      if (!state.activeConversationId) return [];
      return state.messagesByConversation[state.activeConversationId] ?? [];
    },
  },
  actions: {
    async fetchMessages(conversationId: number): Promise<DecryptedMessage[]> {
      const auth = useAuthStore();
      const messages = await apiRequest<MessageEnvelope[]>(`/messages/?conversation=${conversationId}`, {
        token: auth.accessToken,
      });
      return Promise.all(messages.map((m) => this.decryptEnvelope(m)));
    },

    async loadConversations() {
      const auth = useAuthStore();
      this.conversations = await apiRequest<Conversation[]>("/conversations/", { token: auth.accessToken });
      if (this.activeConversationId && !this.conversations.some((c) => c.id === this.activeConversationId)) {
        this.activeConversationId = this.conversations[0]?.id ?? null;
      }
      if (!this.activeConversationId && this.conversations.length) {
        this.activeConversationId = this.conversations[0].id;
      }
    },
    async createConversation(payload: { kind: "dm" | "group"; title: string; memberUsernames: string[] }) {
      const auth = useAuthStore();
      const convo = await apiRequest<Conversation>("/conversations/", {
        method: "POST",
        token: auth.accessToken,
        body: {
          kind: payload.kind,
          title: payload.title,
          member_usernames: payload.memberUsernames,
        },
      });
      this.conversations.unshift(convo);
      this.activeConversationId = convo.id;
      await this.loadMessages(convo.id);
    },

    async deleteConversation(conversationId: number) {
      const auth = useAuthStore();
      await apiRequest(`/conversations/${conversationId}/`, {
        method: "DELETE",
        token: auth.accessToken,
      });

      this.conversations = this.conversations.filter((c) => c.id !== conversationId);
      delete this.messagesByConversation[conversationId];

      if (this.activeConversationId === conversationId) {
        this.activeConversationId = this.conversations[0]?.id ?? null;
        if (this.activeConversationId) {
          await this.loadMessages(this.activeConversationId);
        } else {
          this.disconnectSocket();
        }
      }
    },

    async nukeConversation(conversationId: number) {
      const auth = useAuthStore();
      await apiRequest(`/conversations/${conversationId}/nuke/`, {
        method: "POST",
        token: auth.accessToken,
      });

      this.conversations = this.conversations.filter((c) => c.id !== conversationId);
      delete this.messagesByConversation[conversationId];

      if (this.activeConversationId === conversationId) {
        this.activeConversationId = this.conversations[0]?.id ?? null;
        if (this.activeConversationId) {
          await this.loadMessages(this.activeConversationId);
        } else {
          this.disconnectSocket();
        }
      }
    },
    async loadMessages(conversationId: number) {
      const decrypted = await this.fetchMessages(conversationId);
      this.messagesByConversation[conversationId] = decrypted;
      this.activeConversationId = conversationId;
      this.connectSocket(conversationId);
    },

    async refreshMessages(conversationId: number) {
      const next = await this.fetchMessages(conversationId);
      this.messagesByConversation[conversationId] = [...next].sort(
        (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
      );
    },
    async decryptEnvelope(message: MessageEnvelope): Promise<DecryptedMessage> {
      const security = useSecurityStore();
      let keyFromAad: string | undefined;

      if (message.aad) {
        try {
          const aad = JSON.parse(message.aad) as { shared_key?: string };
          if (aad.shared_key) {
            keyFromAad = aad.shared_key;
            security.setConversationKey(message.conversation, aad.shared_key);
          }
        } catch {
          // ignore malformed AAD payload
        }
      }

      let key = keyFromAad ?? security.getConversationKey(message.conversation);

      if (!key) {
        return { ...message, plaintext: "🔒 Encrypted message (missing key)" };
      }
      try {
        const plaintext = await decryptText(message.ciphertext, message.nonce, key);
        return { ...message, plaintext };
      } catch {
        return { ...message, plaintext: "⚠ Unable to decrypt message" };
      }
    },
    connectSocket(conversationId: number) {
      const auth = useAuthStore();
      if (!auth.accessToken) return;
      this.ws?.close();
      const ws = new WebSocket(websocketUrl(conversationId, auth.accessToken));
      ws.onmessage = async (event) => {
        const parsed = JSON.parse(event.data);
        if (parsed.type !== "message") return;
        const envelope = parsed.payload as MessageEnvelope;
        const decrypted = await this.decryptEnvelope(envelope);
        const current = this.messagesByConversation[conversationId] ?? [];
        if (!current.some((m) => m.id === decrypted.id)) {
          this.messagesByConversation[conversationId] = [...current, decrypted];
        }
      };
      this.ws = ws;
    },
    appendMessage(conversationId: number, message: DecryptedMessage) {
      const existing = this.messagesByConversation[conversationId] ?? [];
      this.messagesByConversation[conversationId] = [...existing, message];
    },
    disconnectSocket() {
      this.ws?.close();
      this.ws = null;
    },
  },
});
