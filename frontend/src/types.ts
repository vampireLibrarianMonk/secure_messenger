export interface AuthResponse {
  access: string;
  refresh: string;
  user: {
    id: number;
    username: string;
    email: string;
  };
}

export interface Device {
  id: number;
  name: string;
  identity_key: string;
  fingerprint: string;
  is_verified: boolean;
  created_at: string;
}

export interface Workspace {
  id: number;
  name: string;
  created_by: number;
  created_at: string;
}

export interface Conversation {
  id: number;
  workspace: number | null;
  channel: number | null;
  kind: "dm" | "group" | "channel";
  title: string;
  created_by: number;
  created_at: string;
  last_message_id: number | null;
  last_message_sender: number | null;
}

export interface Attachment {
  id: number;
  message: number;
  blob: string;
  mime_type: string;
  size: number;
  sha256: string;
  wrapped_file_key: string;
  file_nonce: string;
  created_at: string;
}

export interface MessageEnvelope {
  id: number;
  conversation: number;
  sender: number;
  sender_device: number | null;
  ciphertext: string;
  nonce: string;
  aad: string;
  message_index: number;
  attachments: Attachment[];
  created_at: string;
}
