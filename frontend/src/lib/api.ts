import { supabase } from "./supabase";

async function getAuthHeaders(): Promise<Record<string, string>> {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) throw new Error("Not authenticated");
  return {
    Authorization: `Bearer ${session.access_token}`,
    "Content-Type": "application/json",
  };
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function readErrorMessage(response: Response, fallback: string) {
  try {
    const body = await response.json();
    if (body && typeof body.detail === "string") return body.detail;
    if (body && typeof body.error === "string") return body.error;
    if (body && typeof body.message === "string") return body.message;
  } catch {
    // Ignore parse failures and use fallback.
  }
  return fallback;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const headers = await getAuthHeaders();
  const response = await fetch(path, {
    ...options,
    headers: { ...headers, ...options.headers },
  });
  if (!response.ok) {
    const message = await readErrorMessage(
      response,
      `API error: ${response.status}`
    );
    throw new ApiError(response.status, message);
  }
  return response.json();
}

export async function apiUpload(
  path: string,
  file: File,
  signal?: AbortSignal
): Promise<Record<string, string>> {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) throw new Error("Not authenticated");

  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(path, {
    method: "POST",
    headers: { Authorization: `Bearer ${session.access_token}` },
    body: formData,
    signal,
  });

  if (!response.ok) {
    const message = await readErrorMessage(
      response,
      `Upload error: ${response.status}`
    );
    throw new ApiError(response.status, message);
  }
  return response.json();
}

interface StreamCallbacks {
  onToken: (token: string) => void;
  onStage: (stage: string) => void;
  onImage: (base64: string, url: string) => void;
  onImages?: (
    images: Record<
      string,
      {
        preview_base64?: string;
        preview_url?: string;
        url?: string;
        base64?: string;
      }
    >
  ) => void;
  onDone: (data: Record<string, unknown>) => void;
  onError?: (error: string) => void;
  onTopics?: (content: string) => void;
}

export async function streamChat(
  conversationId: string,
  content: string,
  type: string,
  callbacks: StreamCallbacks,
  imageUrl?: string,
  platforms?: string[],
  signal?: AbortSignal
): Promise<void> {
  const headers = await getAuthHeaders();

  const body: Record<string, unknown> = {
    conversation_id: conversationId,
    content,
    type,
  };
  if (imageUrl) body.image_url = imageUrl;
  if (platforms) body.platforms = platforms;

  const response = await fetch("/api/chat", {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(`Chat error: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let lastMessageType: string | undefined;

  while (true) {
    // If the caller aborted (e.g. user navigated away), stop reading. The
    // fetch's underlying connection will also error reader.read() with an
    // AbortError, but we also break here so we don't dispatch a final chunk
    // into stale callbacks for an unmounted component.
    if (signal?.aborted) {
      try { await reader.cancel(); } catch { /* ignore */ }
      throw new DOMException("Aborted", "AbortError");
    }
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const jsonStr = line.slice(6).trim();
      if (!jsonStr) continue;

      try {
        const data = JSON.parse(jsonStr);

        if (data.token) callbacks.onToken(data.token);
        if (data.stage) callbacks.onStage(data.stage);
        if (data.message_type) lastMessageType = data.message_type;
        if (
          data.message_type === "topics" &&
          data.content &&
          callbacks.onTopics
        ) {
          callbacks.onTopics(data.content as string);
        }
        if (data.image_base64)
          callbacks.onImage(data.image_base64, data.image_url || "");
        if (data.images && callbacks.onImages)
          callbacks.onImages(
            data.images as Record<
              string,
              {
                preview_base64?: string;
                preview_url?: string;
                url?: string;
                base64?: string;
              }
            >
          );
        if (data.error && callbacks.onError) {
          callbacks.onError(data.error as string);
        }
        if (data.done) {
          if (lastMessageType && !data.message_type) {
            data.message_type = lastMessageType;
          }
          callbacks.onDone(data);
        }
      } catch {
        // Incomplete JSON, will be handled in next chunk
      }
    }
  }
}

export const AVAILABLE_MODELS = [
  { id: "claude-haiku-4-5-20251001", label: "Haiku (fast)" },
  { id: "claude-sonnet-4-20250514", label: "Sonnet" },
  { id: "claude-opus-4-20250514", label: "Opus (best)" },
];

export const listConversations = (signal?: AbortSignal) =>
  apiFetch<Array<Record<string, unknown>>>("/api/conversations", { signal });
export const createConversation = (
  mode: string = "thumbnail",
  signal?: AbortSignal,
  imageProvider: "gemini" | "openai" = "gemini",
) =>
  apiFetch<Record<string, unknown>>("/api/conversations", {
    method: "POST",
    body: JSON.stringify({ mode, image_provider: imageProvider }),
    signal,
  });
export const getConversation = (
  id: string,
  limit: number = 50,
  before?: string,
  signal?: AbortSignal
) => {
  const params = new URLSearchParams({ limit: String(limit) });
  if (before) params.set("before", before);
  return apiFetch<Record<string, unknown> & { has_more?: boolean }>(
    `/api/conversations/${id}?${params}`,
    { signal }
  );
};
export const deleteConversation = (id: string, signal?: AbortSignal) =>
  apiFetch<void>(`/api/conversations/${id}`, { method: "DELETE", signal });
export const updateConversation = (id: string, data: { model?: string }, signal?: AbortSignal) =>
  apiFetch<Record<string, unknown>>(`/api/conversations/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
    signal,
  });
export const getConversationStatus = (id: string, signal?: AbortSignal) =>
  apiFetch<{ status: string; type?: string }>(
    `/api/conversations/${id}/status`,
    { signal }
  );

export const listAssets = (bucket: string, signal?: AbortSignal) =>
  apiFetch<Array<Record<string, unknown>>>(`/api/assets/${bucket}`, { signal });

export const getBatchSignedUrls = (bucket: string, filenames: string[], signal?: AbortSignal) =>
  apiFetch<Array<{ signedURL: string; path: string; error: string | null }>>(
    "/api/assets/batch-signed-urls",
    {
      method: "POST",
      body: JSON.stringify({ bucket, filenames }),
      signal,
    }
  );
export const getBatchThumbnails = (
  bucket: string,
  filenames: string[],
  w: number = 200,
  signal?: AbortSignal
) =>
  apiFetch<Record<string, string>>("/api/assets/batch-thumbnails", {
    method: "POST",
    body: JSON.stringify({ bucket, filenames, w }),
    signal,
  });

export const deleteAsset = (bucket: string, name: string, signal?: AbortSignal) =>
  apiFetch<void>(`/api/assets/${bucket}/${name}`, { method: "DELETE", signal });
export const uploadAsset = (bucket: string, file: File, signal?: AbortSignal) =>
  apiUpload(`/api/assets/${bucket}/upload`, file, signal);

export const reindexPhotos = (signal?: AbortSignal) =>
  apiFetch<{ indexed: number; total: number; skipped: number }>(
    "/api/assets/personal-photos/reindex",
    { method: "POST", signal }
  );

export const analyzeReferenceStyle = (signal?: AbortSignal) =>
  apiFetch<Record<string, unknown>>("/api/assets/reference-thumbs/analyze", {
    method: "POST",
    signal,
  });

export async function fetchAssetText(
  bucket: string,
  name: string,
  signal?: AbortSignal
): Promise<string> {
  const headers = await getAuthHeaders();
  const response = await fetch(`/api/assets/${bucket}/${name}`, {
    headers: { Authorization: headers.Authorization },
    signal,
  });
  if (!response.ok) throw new Error(`Asset fetch error: ${response.status}`);
  return response.text();
}

export interface ScriptSection {
  name: string;
  description: string;
  enabled: boolean;
  order: number;
}

export interface Persona {
  id: string;
  user_id: string;
  channel_name: string;
  language: string;
  persona_text: string;
  script_template: ScriptSection[];
  created_at: string;
  updated_at: string;
}

export const getPersona = (signal?: AbortSignal) =>
  apiFetch<Persona>("/api/personas", { signal }).catch((err) => {
    if (err.message.includes("404")) return null;
    throw err;
  });

export const upsertPersona = (
  data: {
    channel_name: string;
    language: string;
    persona_text: string;
    script_template?: ScriptSection[];
  },
  signal?: AbortSignal
) =>
  apiFetch<Persona>("/api/personas", {
    method: "PUT",
    body: JSON.stringify(data),
    signal,
  });

export const deletePersona = (signal?: AbortSignal) =>
  apiFetch<void>("/api/personas", { method: "DELETE", signal });

export interface Memory {
  id: string;
  user_id: string;
  content: string;
  source_action: string;
  source_feedback: string;
  created_at: string;
}

export const listMemories = (signal?: AbortSignal) =>
  apiFetch<Memory[]>("/api/memories", { signal });

export const deleteMemory = (id: string, signal?: AbortSignal) =>
  apiFetch<void>(`/api/memories/${id}`, { method: "DELETE", signal });
