export type SSEMessage =
  | { type: "meta"; sources?: unknown[]; conversation_id?: string }
  | { type: "delta"; text: string }
  | { type: "done" }
  | { type: "final"; text: string };

export async function postSSE(
  url: string,
  body: unknown,
  onMessage: (msg: SSEMessage) => void,
  signal?: AbortSignal
) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });

  if (!res.ok || !res.body) {
    const t = await res.text().catch(() => "");
    throw new Error(`SSE request failed: ${res.status} ${t}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");

  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // SSE events separated by double newline
    let idx;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const rawEvent = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);

      // We only use "data:" lines
      const dataLines = rawEvent
        .split("\n")
        .filter((l) => l.startsWith("data:"))
        .map((l) => l.replace(/^data:\s?/, ""));

      const dataStr = dataLines.join("\n").trim();
      if (!dataStr) continue;

      try {
        const msg = JSON.parse(dataStr);
        onMessage(msg);
      } catch {
        // ignore parse errors
      }
    }
  }
}
