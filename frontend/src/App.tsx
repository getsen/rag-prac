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

const API_BASE = "http://localhost:8000/api";

function uid() {
  return Math.random().toString(16).slice(2) + Date.now().toString(16);
}

export default function App() {
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
  const [requireCode, setRequireCode] = useState(true);
  const [kind, setKind] = useState<string>("step");
  const [topK, setTopK] = useState(8);

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
      top_k: topK,
      kind: kind || null,
      require_code: requireCode,
      section_contains: null,
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

  const stop = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsStreaming(false);
    setActiveAssistantId(null);
  };

  return (
    <div className="app">
      <div className="header">
        <div className="header-inner">
          <div className="brand">RAG Runbook Chat</div>
          <div className="controls">
            <label>
              Kind:&nbsp;
              <select value={kind} onChange={(e) => setKind(e.target.value)}>
                <option value="">any</option>
                <option value="step">step</option>
                <option value="section">section</option>
                <option value="narrative">narrative</option>
              </select>
            </label>

            <label>
              <input
                type="checkbox"
                checked={requireCode}
                onChange={(e) => setRequireCode(e.target.checked)}
              />
              &nbsp;require code
            </label>

            <label>
              topK:&nbsp;
              <select
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
              >
                {[4, 6, 8, 10, 12].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>

            {isStreaming ? (
              <button onClick={stop}>Stop</button>
            ) : (
              <button onClick={send} disabled={!input.trim()}>
                Send
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="container">
        <div className="chat">
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
                      <div style={{ fontWeight: 600, marginBottom: 6 }}>
                        Sources
                      </div>
                      <ul style={{ margin: 0, paddingLeft: 18 }}>
                        {m.sources.map((s: any, idx: number) => (
                          <li key={idx}>
                            {s.source} — {s.section}
                          </li>
                        ))}
                      </ul>
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
