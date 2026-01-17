import type { SSEMessage } from "./sse";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github-dark.css";
import "./styles.css";
import { postSSE } from "./sse";

type Role = "user" | "assistant";

type ChatMsg = {
  id: string;
  role: Role;
  content: string;
  sources?: unknown[];
};

type ConversationSummary = {
  conversation_id: string;
  first_turn_preview?: string;
  turn_count: number;
  created_at: string;
};

const API_BASE = "http://localhost:8000/api";

function uid() {
  return Math.random().toString(16).slice(2) + Date.now().toString(16);
}

function getConversationId(): string {
  let id = localStorage.getItem("current_conversation_id");
  if (!id) {
    id = uid();
    localStorage.setItem("current_conversation_id", id);
  }
  return id;
}

export default function App() {
  const [conversationId, setConversationId] = useState(getConversationId());
  const [messages, setMessages] = useState<ChatMsg[]>([
    {
      id: uid(),
      role: "assistant",
      content:
        "Hi! Ask me about onboarding/maintenance runbooks. I can stream responses and render tables/code cleanly.",
    },
  ]);
  const [input, setInput] = useState("");
  const [activeAssistantId, setActiveAssistantId] = useState<string | null>(
    null
  );
  const [isStreaming, setIsStreaming] = useState(false);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [showSidebar, setShowSidebar] = useState(true);
  const [mode, setMode] = useState<"rag" | "agentic">("rag");

  const abortRef = useRef<AbortController | null>(null);
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  // Keep autoscroll if user is near bottom
  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;

    const onScroll = () => {
      const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
      setAutoScroll(nearBottom);
    };
    el.addEventListener("scroll", onScroll);
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  // Load conversation history when conversation ID changes
  useEffect(() => {
    const loadConversation = async () => {
      try {
        const res = await fetch(
          `${API_BASE}/conversations/${conversationId}`
        ).catch(() => null);
        if (res?.ok) {
          const data = await res.json();
          if (data.history && data.history.length > 0) {
            setMessages(
              data.history.map((turn: any, idx: number) => ({
                id: uid(),
                role: turn.role,
                content: turn.content,
              }))
            );
          }
        }
      } catch (e) {
        console.error("Failed to load conversation:", e);
      }
    };
    loadConversation();
  }, [conversationId]);

  // Load conversation list once on mount, and refresh when conversation changes
  useEffect(() => {
    const loadConversations = async () => {
      try {
        const res = await fetch(`${API_BASE}/conversations`);
        if (res.ok) {
          const data = await res.json();
          setConversations(data.conversations || []);
        }
      } catch (e) {
        console.error("Failed to load conversations:", e);
      }
    };
    loadConversations();
  }, [conversationId]); // Refresh when conversation changes

  useEffect(() => {
    if (!autoScroll) return;
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, autoScroll]);

  const send = async () => {
    const text = input.trim();
    if (!text || isStreaming) return;

    setInput("");
    const userMsg: ChatMsg = { id: uid(), role: "user", content: text };
    const assistantId = uid();
    setActiveAssistantId(assistantId);
    const assistantMsg: ChatMsg = {
      id: assistantId,
      role: "assistant",
      content: "",
    };

    setMessages((m) => [...m, userMsg, assistantMsg]);
    setIsStreaming(true);

    const body = {
      message: text,
      section_contains: null,
      conversation_id: conversationId,
      mode: mode,
    };

    const abort = new AbortController();
    abortRef.current = abort;

    try {
      await postSSE(
        `${API_BASE}/chat/stream`,
        body,
        (msg: SSEMessage) => {
          if (msg.type === "meta" && msg.sources) {
            setMessages((prev) =>
              prev.map((x) =>
                x.id === assistantId ? { ...x, sources: msg.sources } : x
              )
            );
            return;
          }

          if (msg.type === "delta") {
            // ✅ stop showing loader when first token arrives
            setActiveAssistantId(null);

            setMessages((prev) =>
              prev.map((x) =>
                x.id === assistantId
                  ? { ...x, content: x.content + (msg.text ?? "") }
                  : x
              )
            );
            return;
          }

          if (msg.type === "done") {
            setIsStreaming(false);
            setActiveAssistantId(null);
            abortRef.current = null;
            return;
          }

          if (msg.type === "final") {
            setActiveAssistantId(null); // ✅ clear loader when final arrives
            setMessages((prev) =>
              prev.map((x) =>
                x.id === assistantId
                  ? { ...x, content: msg.text ?? x.content }
                  : x
              )
            );
            return;
          }
        },
        abort.signal
      );
    } catch (e: any) {
      setActiveAssistantId(null);
      setIsStreaming(false);
      abortRef.current = null;
      setMessages((prev) =>
        prev.map((x) =>
          x.id === assistantId
            ? { ...x, content: `Error: ${e?.message ?? "Unknown error"}` }
            : x
        )
      );
    }
  };

  const startNewChat = async () => {
    try {
      const res = await fetch(`${API_BASE}/conversations`, {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        const newId = data.conversation_id;
        setConversationId(newId);
        localStorage.setItem("current_conversation_id", newId);
        setMessages([
          {
            id: uid(),
            role: "assistant",
            content:
              "Hi! Ask me about onboarding/maintenance runbooks. I can stream responses and render tables/code cleanly.",
          },
        ]);
        // Add new conversation to the list
        setConversations((prev) => [
          {
            conversation_id: newId,
            turn_count: 0,
            created_at: new Date().toISOString(),
          },
          ...prev,
        ]);
      }
    } catch (e) {
      console.error("Failed to create conversation:", e);
    }
  };

  const switchConversation = (id: string) => {
    setConversationId(id);
    localStorage.setItem("current_conversation_id", id);
  };

  const deleteConversation = async (id: string) => {
    try {
      await fetch(`${API_BASE}/conversations/${id}`, { method: "DELETE" });
      setConversations((prev) => prev.filter((c) => c.conversation_id !== id));
      if (id === conversationId) {
        startNewChat();
      }
    } catch (e) {
      console.error("Failed to delete conversation:", e);
    }
  };

  return (
    <div className="app">
      <div className="header">
        <div className="header-inner">
          <button
            className="sidebar-toggle"
            onClick={() => setShowSidebar(!showSidebar)}
          >
            ☰
          </button>
          <div className="brand">RAG Runbook Chat</div>
        </div>
      </div>

      <div className="container">
        {showSidebar && (
          <div className="sidebar">
            <div className="sidebar-header">
              <button className="new-chat-btn" onClick={startNewChat}>
                + New Chat
              </button>
            </div>

            <div className="conversations-list">
              <div className="sidebar-section-title">Conversations</div>
              {conversations.length === 0 ? (
                <div className="empty-conversations">No conversations yet</div>
              ) : (
                conversations.map((conv) => (
                  <div
                    key={conv.conversation_id}
                    className={`conversation-item ${
                      conv.conversation_id === conversationId ? "active" : ""
                    }`}
                  >
                    <div
                      className="conv-content"
                      onClick={() => switchConversation(conv.conversation_id)}
                    >
                      <div className="conv-preview">
                        {conv.first_turn_preview || "New conversation"}
                      </div>
                      <div className="conv-meta">
                        {conv.turn_count} messages
                      </div>
                    </div>
                    <button
                      className="delete-conv-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteConversation(conv.conversation_id);
                      }}
                    >
                      ✕
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        <div className="chat">
          <div className="mode-toggle">
            <button
              className={`mode-btn ${mode === "rag" ? "active" : ""}`}
              onClick={() => setMode("rag")}
            >
              RAG
            </button>
            <button
              className={`mode-btn ${mode === "agentic" ? "active" : ""}`}
              onClick={() => setMode("agentic")}
            >
              Agentic
            </button>
          </div>
          <div className="messages" ref={scrollerRef}>
            {messages.map((m) => (
              <div className={`msg ${m.role}`} key={m.id}>
                <div className="role">{m.role}</div>
                <div className="bubble">
                  {m.role === "assistant" &&
                  m.id === activeAssistantId &&
                  !m.content ? (
                    <div className="loader">
                      <span>Thinking</span>
                      <span className="dot" />
                      <span className="dot" />
                      <span className="dot" />
                    </div>
                  ) : (
                    <div className="markdown">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        rehypePlugins={[rehypeHighlight]}
                      >
                        {m.content}
                      </ReactMarkdown>
                    </div>
                  )}

                  {m.sources?.length ? (
                    <div
                      style={{ marginTop: 10, color: "#6b7280", fontSize: 12 }}
                    >
                      <details>
                        <summary
                          style={{
                            fontWeight: 600,
                            marginBottom: 6,
                            cursor: "pointer",
                            listStyle: "none",
                          }}
                        >
                          Sources
                        </summary>
                        <ul style={{ margin: 0, paddingLeft: 18 }}>
                          {m.sources.map((s: any, idx: number) => (
                            <li key={idx}>
                              {s.source} — {s.section}
                            </li>
                          ))}
                        </ul>
                      </details>
                    </div>
                  ) : null}
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>

          <div className="composer">
            <textarea
              rows={3}
              value={input}
              placeholder="Ask about onboarding/maintenance steps..."
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
            />
            <button onClick={send} disabled={isStreaming || !input.trim()}>
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
