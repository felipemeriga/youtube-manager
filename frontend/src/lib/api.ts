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
    throw new Error(`API error: ${response.status}`);
  }
  return response.json();
}

export async function apiUpload(
  path: string,
  file: File
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
  });

  if (!response.ok) throw new Error(`Upload error: ${response.status}`);
  return response.json();
}

interface StreamCallbacks {
  onToken: (token: string) => void;
  onStage: (stage: string) => void;
  onImage: (base64: string, url: string) => void;
  onDone: (data: Record<string, unknown>) => void;
  onError?: (error: string) => void;
  onTopics?: (content: string) => void;
}

export async function streamChat(
  conversationId: string,
  content: string,
  type: string,
  callbacks: StreamCallbacks
): Promise<void> {
  const headers = await getAuthHeaders();

  const response = await fetch("/api/chat", {
    method: "POST",
    headers,
    body: JSON.stringify({ conversation_id: conversationId, content, type }),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Chat error: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let lastMessageType: string | undefined;

  while (true) {
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
        if (data.message_type === "topics" && data.content && callbacks.onTopics) {
          callbacks.onTopics(data.content as string);
        }
        if (data.image_base64)
          callbacks.onImage(data.image_base64, data.image_url || "");
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

export const listConversations = () =>
  apiFetch<Array<Record<string, unknown>>>("/api/conversations");
export const createConversation = (mode: string = "thumbnail") =>
  apiFetch<Record<string, unknown>>("/api/conversations", {
    method: "POST",
    body: JSON.stringify({ mode }),
  });
export const getConversation = (id: string) =>
  apiFetch<Record<string, unknown>>(`/api/conversations/${id}`);
export const deleteConversation = (id: string) =>
  apiFetch<void>(`/api/conversations/${id}`, { method: "DELETE" });

export const listAssets = (bucket: string) =>
  apiFetch<Array<Record<string, unknown>>>(`/api/assets/${bucket}`);
export const deleteAsset = (bucket: string, name: string) =>
  apiFetch<void>(`/api/assets/${bucket}/${name}`, { method: "DELETE" });
export const uploadAsset = (bucket: string, file: File) =>
  apiUpload(`/api/assets/${bucket}/upload`, file);
