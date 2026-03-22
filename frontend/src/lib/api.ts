const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api";

export type ApiMethod = "GET" | "POST" | "PATCH" | "DELETE";

export async function apiRequest<T>(
  path: string,
  options: {
    method?: ApiMethod;
    token?: string | null;
    body?: unknown;
    isFormData?: boolean;
  } = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  if (!options.isFormData) {
    headers["Content-Type"] = "application/json";
  }
  if (options.token) {
    headers.Authorization = `Bearer ${options.token}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body
      ? options.isFormData
        ? (options.body as BodyInit)
        : JSON.stringify(options.body)
      : undefined,
  });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const data = await response.json();
      detail = data.detail ?? JSON.stringify(data);
    } catch {
      // ignore
    }
    throw new Error(detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export function websocketUrl(conversationId: number, token: string): string {
  const configured = import.meta.env.VITE_WS_BASE ?? "ws://localhost:8000";
  return `${configured}/ws/conversations/${conversationId}/?token=${encodeURIComponent(token)}`;
}

export function videoWebsocketUrl(conversationId: number, token: string): string {
  const configured = import.meta.env.VITE_WS_BASE ?? "ws://localhost:8000";
  return `${configured}/ws/video/conversations/${conversationId}/?token=${encodeURIComponent(token)}`;
}
