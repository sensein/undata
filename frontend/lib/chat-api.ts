/**
 * SSE streaming chat client for the curation LLM assistant.
 */

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8002";

export interface ChatEvent {
  type: "text" | "tool_call" | "tool_result";
  content?: string;
  name?: string;
  arguments?: Record<string, unknown>;
  result?: Record<string, unknown>;
  status?: string;
}

export async function* streamChat(
  messages: Array<{ role: string; content: string }>,
  entityContext?: Record<string, unknown>,
): AsyncGenerator<ChatEvent> {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;

  const response = await fetch(`${BACKEND_URL}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ messages, entityContext }),
  });

  if (!response.ok) {
    yield { type: "text", content: `Error: ${response.status} ${response.statusText}` };
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) return;

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const data = line.slice(6).trim();
        if (data === "[DONE]") return;
        try {
          yield JSON.parse(data) as ChatEvent;
        } catch {
          // Skip malformed JSON
        }
      }
    }
  }
}
