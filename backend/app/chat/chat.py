from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import logging
import json
import re
from app.config import settings
from app.rag.rag_query import decide_mode, retrieve_chunks, build_context
from app.llm.ollama.ollama_client import ollama_generate
from app.llm.ollama.ollama_client_stream import ollama_generate_stream


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

class ChatRequest(BaseModel):
    message: str
    top_k: int = 8
    kind: Optional[str] = None
    require_code: bool = False
    section_contains: Optional[str] = None

class ChatResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    used_filters: Dict[str, Any]


class ChatService:
    """Service for handling chat operations with RAG context."""
    
    def __init__(
        self,
        ollama_model: str = "llama2",
        max_distance: float = 0.60,
        temperature: float = 0.2,
    ):
        """
        Initialize ChatService.
        
        Args:
            ollama_model: Ollama model to use (default from config or "llama2")
            max_distance: Maximum distance threshold for relevant chunks
            temperature: Temperature for model generation
        """
        self.ollama_model = ollama_model or (settings.ollama_model if hasattr(settings, 'ollama_model') else "llama2")
        self.max_distance = max_distance
        self.temperature = temperature
        self.command_line_re = re.compile(
            r"^\s*(sudo\s+|kubectl\s+|systemctl\s+|apt-get\s+|yum\s+|docker\s+|helm\s+|npm\s+|yarn\s+|python\s+|pip\s+|curl\s+|wget\s+|git\s+)",
            re.IGNORECASE,
        )
        logger.info(f"ChatService initialized with ollama_model={self.ollama_model}, max_distance={self.max_distance}")

    @staticmethod
    def normalize_whitespace(text: str) -> str:
        """Normalize whitespace in text."""
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = "\n".join(line.rstrip() for line in text.splitlines())
        return text.strip()

    def wrap_command_runs(self, markdown: str, lang: str = "bash") -> str:
        """Wrap standalone command lines in code fences."""
        lines = markdown.splitlines()
        out = []
        in_fence = False
        cmd_buf = []

        def flush():
            nonlocal cmd_buf
            if cmd_buf:
                out.append(f"```{lang}")
                out.extend(cmd_buf)
                out.append("```")
                cmd_buf = []

        for line in lines:
            s = line.strip()

            if s.startswith("```"):
                flush()
                out.append(line)
                in_fence = not in_fence
                continue

            if not in_fence and self.command_line_re.match(line):
                cmd_buf.append(line.rstrip())
                continue

            flush()
            out.append(line)

        flush()
        return "\n".join(out).strip()

    def stream_not_found(self, message: str = "NOT_FOUND: Not covered by the indexed runbook documents.") -> StreamingResponse:
        """Return a streaming response indicating query was not found."""
        def gen():
            yield f"data: {json.dumps({'type':'meta','sources': []}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type':'final','text': message}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type':'done'}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    def process_chat_stream(self, req: ChatRequest) -> StreamingResponse:
        """Process a chat request and return streaming response."""
        hits = retrieve_chunks(
            query=req.message,
            k=req.top_k,
            kind_filter=req.kind,
            section_contains=req.section_contains,
        )

        if not hits:
            logger.warning(f"No relevant chunks found for query: {req.message}")
            return self.stream_not_found()

        best_dist = hits[0].get("distance")
        logger.debug(f"best_dist={best_dist}, query={req.message}")

        if best_dist is not None and best_dist > self.max_distance:
            logger.warning(f"Query rejected: distance {best_dist} exceeds max_distance {self.max_distance}")
            return self.stream_not_found()
        
        ctx = build_context(req.message, hits)
        mode = decide_mode(req.message, hits)

        # commands_only mode: return only commands
        if mode == "commands_only":
            return self._stream_commands_only(hits)
        else:
            return self._stream_with_context(req.message, ctx)

    def _stream_commands_only(self, hits: List[Dict[str, Any]]) -> StreamingResponse:
        """Stream only command lines without LLM processing."""
        cmds = []
        for h in hits:
            cmds.extend(h["metadata"].get("commands") or [])
        cmds = [c for c in cmds if c.strip()]
        answer = "\n".join(cmds) if cmds else "NOT_FOUND"
        if answer != "NOT_FOUND":
            answer = f"```bash\n{answer}\n```"

        def sse_once():
            payload = {"type": "delta", "text": answer}
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type':'done'})}\n\n"

        return StreamingResponse(sse_once(), media_type="text/event-stream")

    def _stream_with_context(self, query: str, ctx: Dict[str, Any]) -> StreamingResponse:
        """Stream LLM response with context."""
        system = (
            "You are a factual technical assistant.\n"
            "You must respond using ONLY the provided context content.\n\n"

            "CRITICAL RULES:\n"
            "- NEVER mention files, folders, paths, documents, links, or navigation steps.\n"
            "- NEVER say things like 'open', 'navigate', 'refer to', 'click', or 'see section'.\n"
            "- NEVER explain where the information comes from.\n"
            "- NEVER describe how to access the content.\n\n"

            "CONTENT RULES:\n"
            "- If the user asks to 'share', 'explain', or 'describe' something, "
            "return the actual content itself.\n"
            "- Summarise or structure the content if needed, but do not add new facts.\n"
            "- If the context does not contain the requested information, respond with NOT_FOUND.\n\n"

            "FORMATTING RULES:\n"
            "- Use clear paragraphs, lists, or tables where appropriate.\n"
            "- Do not include disclaimers or meta commentary.\n"
        )

        prompt = f"""User question:
        {query}

        Context:
            {ctx['context_text']}

        Instructions:
        - Answer using the context only.
        - If commands/steps are required, keep order and be concise.
        - Do NOT reference files, folders, or documents.
        - Return the requested information directly.
        - If information is missing, respond with NOT_FOUND.

        Answer:
    """

        def sse_gen():
            # send sources first
            yield f"data: {json.dumps({'type':'meta','sources':ctx['sources']}, ensure_ascii=False)}\n\n"

            parts = []

            # stream raw deltas
            for chunk in ollama_generate_stream(
                model=self.ollama_model,
                prompt=prompt,
                system=system,
                temperature=self.temperature,
            ):
                parts.append(chunk)
                yield f"data: {json.dumps({'type':'delta','text':chunk}, ensure_ascii=False)}\n\n"

                # build final formatted answer
                full = "".join(parts)
                full = self.normalize_whitespace(full)
                full = self.wrap_command_runs(full, lang="bash")

                # send final replacement
                yield f"data: {json.dumps({'type':'final','text':full}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'type':'done'}, ensure_ascii=False)}\n\n"

        return StreamingResponse(sse_gen(), media_type="text/event-stream")


# Initialize service with defaults
_chat_service = ChatService()


@router.post("/chat/stream")
def chat_stream(req: ChatRequest):
    """API endpoint for streaming chat responses."""
    return _chat_service.process_chat_stream(req)


@router.get("/health")
def health():
    """Health check endpoint."""
    return {"ok": True}
