export interface AuthResponse {
  access: string;
  refresh: string;
  user: {
    id: number;
    username: string;
    email: string;
    must_reset_password?: boolean;
    is_security_admin?: boolean;
  };
}

export interface SecurityJourneyReport {
  id: number;
  title: string;
  flow_type: "dm" | "video" | "both";
  status: "draft" | "review" | "final";
  executive_summary: string;
  reality_check_answers: Record<string, string>;
  created_by: number;
  created_at: string;
  updated_at: string;
}

export interface SecurityAnalysisRun {
  id: number;
  report: number;
  triggered_by: number | null;
  triggered_by_username?: string;
  flow_type: "dm" | "video" | "both";
  requested_checks: string[];
  status: "queued" | "running" | "completed" | "failed";
  run_summary: Record<string, unknown>;
  failure_reason: string;
  created_at: string;
  updated_at: string;
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
