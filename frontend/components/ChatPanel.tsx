"use client";

import { useState, useRef, useEffect } from "react";
import { streamChat, type ChatEvent } from "@/lib/chat-api";

interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

interface ChatPanelProps {
  entityContext?: Record<string, unknown>;
  onToolResult?: (event: ChatEvent) => void;
  autoSuggest?: boolean;
}

export function ChatPanel({ entityContext, onToolResult, autoSuggest = false }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [toolStatus, setToolStatus] = useState<string | null>(null);
  const [hasAutoSuggested, setHasAutoSuggested] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const entityShaRef = useRef<string | undefined>(undefined);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Auto-suggest when entity changes
  useEffect(() => {
    const sha = entityContext?.sha256 as string | undefined;
    if (autoSuggest && sha && sha !== entityShaRef.current && !isStreaming) {
      entityShaRef.current = sha;
      setHasAutoSuggested(false);
    }
  }, [entityContext?.sha256, autoSuggest, isStreaming]);

  // Auto-suggest effect is below sendMessageInternal definition

  const sendMessageInternal = async (newMessages: ChatMessage[]) => {
    setMessages(newMessages);
    setIsStreaming(true);
    setToolStatus(null);

    let assistantContent = "";

    try {
      const events: ChatEvent[] = [];
      for await (const event of streamChat(
        newMessages.map((m) => ({ role: m.role, content: m.content })),
        entityContext,
      )) {
        events.push(event);
      }

      for (const event of events) {
        if (event.type === "text" && event.content) {
          assistantContent += event.content;
        } else if (event.type === "tool_result") {
          onToolResult?.(event);
        }
      }
    } catch (e) {
      assistantContent += `\nError: ${e}`;
    }

    if (assistantContent) {
      setMessages([...newMessages, { role: "assistant", content: assistantContent }]);
    }
    setIsStreaming(false);
  };

  const sendMessage = async () => {
    if (!input.trim() || isStreaming) return;

    const userMsg: ChatMessage = { role: "user", content: input.trim() };
    const newMessages = [...messages, userMsg];
    setInput("");
    await sendMessageInternal(newMessages);
  };

  // Auto-suggest when entity loads (after sendMessageInternal is defined)
  useEffect(() => {
    if (autoSuggest && entityContext && !hasAutoSuggested && !isStreaming && entityShaRef.current) {
      setHasAutoSuggested(true);
      const autoMsg: ChatMessage = { role: "user", content: "Suggest improvements for this entity" };
      sendMessageInternal([autoMsg]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasAutoSuggested, autoSuggest, entityContext, isStreaming]);

  return (
    <div className="flex flex-col h-full">
      {/* Entity context badge */}
      {entityContext && (
        <div className="px-4 py-2 bg-cyan-50 border-b text-xs text-cyan-700">
          Editing: {String((entityContext.provenance as Array<{name?: string}>)?.[0]?.name ?? (entityContext.sha256 as string)?.slice(0, 12))} ({String((entityContext.semantic as Record<string, string>)?.data_type ?? "entity")})
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-auto p-4 space-y-3">
        {messages.length === 0 && (
          <div className="text-center text-gray-400 py-8">
            <p className="text-lg mb-2">Curation Assistant</p>
            <p className="text-sm">Ask me to suggest ontology annotations, fix units, improve descriptions, or ingest new sources.</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`text-sm ${
              msg.role === "user"
                ? "bg-blue-50 text-blue-900 ml-8"
                : "bg-gray-50 text-gray-800 mr-8"
            } rounded-lg p-3`}
          >
            <div className="text-xs text-gray-400 mb-1">{msg.role === "user" ? "You" : "Assistant"}</div>
            <div className="whitespace-pre-wrap">{msg.content}</div>
          </div>
        ))}
        {toolStatus && (
          <div className="text-xs text-orange-600 bg-orange-50 rounded p-2 animate-pulse">
            {toolStatus}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t p-3">
        <div className="flex gap-2">
          <input
            type="text"
            className="flex-1 border rounded px-3 py-2 text-sm"
            placeholder="Ask the curation assistant..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendMessage()}
            disabled={isStreaming}
          />
          <button
            className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50"
            onClick={sendMessage}
            disabled={isStreaming || !input.trim()}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
