from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import logging
import json
import re
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

OLLAMA_MODEL = "llama2" 

def normalize_whitespace(text: str) -> str:
    # collapse 3+ newlines into 2 newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # trim trailing spaces per line
    text = "\n".join(line.rstrip() for line in text.splitlines())
    return text.strip()

COMMAND_LINE_RE = re.compile(
    r"^\s*(sudo\s+|kubectl\s+|systemctl\s+|apt-get\s+|yum\s+|docker\s+|helm\s+|npm\s+|yarn\s+|python\s+|pip\s+|curl\s+|wget\s+|git\s+)",
    re.IGNORECASE,
)

def normalize_whitespace(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(line.rstrip() for line in text.splitlines())
    return text.strip()

def wrap_command_runs(markdown: str, lang: str = "bash") -> str:
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

        if not in_fence and COMMAND_LINE_RE.match(line):
            cmd_buf.append(line.rstrip())
            continue

        flush()
        out.append(line)

    flush()
    return "\n".join(out).strip()


# @router.post("/chat", response_model=ChatResponse)
# def chat(req: ChatRequest):
#     # Retrieval defaults:
#     # - If asking for commands/steps, it's often best to bias to step chunks w/ code
#     # You can override via request fields.
#     hits = retrieve_chunks(
#         query=req.message,
#         k=req.top_k,
#         kind_filter=req.kind,
#         require_code=req.require_code,
#         section_contains=req.section_contains,
#     )

#     ctx = build_context(req.message, hits)

#     # auto suggest mode
#     if req.mode == "normal" and _looks_like_command_request(req.message):
#         inferred_mode = "commands_only"
#     else:
#         inferred_mode = req.mode

#     logger.info(f"Chat inferred mode: {inferred_mode}")
    
#     if inferred_mode == "commands_only":
#         # system = (
#         #     "You are a precise runbook assistant. Use ONLY the provided context. "
#         #     "Return ONLY the commands, in execution order, one per line. "
#         #     "Do not add explanations. Do not add extra commands. "
#         #     "If the commands are not present in the context, reply exactly: NOT_FOUND"
#         # )

#         # prompt = f"""User question:
#         # {req.message}

#         # Context:
#         # {ctx['context_text']}

#         # Return ONLY the commands, one per line, in order:
#         # """

#         # flatten commands from hits in order
#         cmds = []
#         for h in hits:
#             cmds.extend(h["metadata"].get("commands") or [])
#         cmds = [c for c in cmds if c.strip()]

#         answer = "\n".join(cmds) if cmds else "NOT_FOUND"

#         if answer != "NOT_FOUND":
#             # Choose language if you can infer; bash is safe default
#             answer = f"```bash\n{answer}\n```"

#         return ChatResponse(
#             answer=answer,
#             sources=ctx["sources"],
#             used_filters={
#                 "top_k": req.top_k,
#                 "kind": req.kind,
#                 "require_code": req.require_code,
#                 "section_contains": req.section_contains,
#                 "mode": req.mode,
#             },
#         )
#     else:
#         system = (
#             "You are a precise technical assistant. Use ONLY the provided context. "
#             "Do not invent commands, flags, or steps. "
#             "If the answer is not in the context, say you cannot find it in the docs. "
#             "Keep steps/commands in original order. "
#             "Avoid time estimates or operational claims not present in the docs."
#         )
#         sources_text = "\n".join(f"- {s['source']}" for s in ctx["sources"])
#         prompt = f"""User question:
#         {req.message}

#         Context:
#         {ctx['context_text']}

#         Instructions:
#         - Answer using the context only.
#         - If providing steps/commands, keep order and be brief.
#         - Sources:
#         {sources_text}

#         Answer:
#     """

#     answer = ollama_generate(model=OLLAMA_MODEL, prompt=prompt, system=system, temperature=0.2)

#     return ChatResponse(
#         answer=answer.strip(),
#         sources=ctx["sources"],
#         used_filters={
#             "top_k": req.top_k,
#             "kind": req.kind,
#             "require_code": req.require_code,
#             "section_contains": req.section_contains,
#         },
#     )

@router.post("/chat/stream")
def chat_stream(req: ChatRequest):
    hits = retrieve_chunks(
        query=req.message,
        k=req.top_k,
        kind_filter=req.kind,
        section_contains=req.section_contains,
    )

    ctx = build_context(req.message, hits)

    mode = decide_mode(req.message, hits)

    # commands_only: stream is optional; simplest is return once as SSE
    if mode == "commands_only":
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
    else:
        system = (
            "You are a precise technical assistant. Use ONLY the provided context. "
            "Do not invent commands, flags, or steps. "
            "Avoid time estimates or claims not present in the docs. "
            "Keep procedures in the original order."
        )

        sources_text = "\n".join(f"- {s['source']}" for s in ctx["sources"])

        prompt = f"""User question:
        {req.message}

        Context:
            {ctx['context_text']}

        Instructions:
        - Answer using the context only.
        - If commands/steps are required, keep order and be concise.
        - End with:
        Sources:
        {sources_text}

        Answer:
    """

    def sse_gen():
        # send sources first (so UI can show “grounding” immediately if you want)
        yield f"data: {json.dumps({'type':'meta','sources':ctx['sources']}, ensure_ascii=False)}\n\n"

        # 1) buffer all deltas
        parts = []
        for chunk in ollama_generate_stream(
            model=OLLAMA_MODEL,
            prompt=prompt,
            system=system,
            temperature=0.2,
        ):
            parts.append(chunk)

            full = "".join(parts)

            # 2) normalize + wrap command runs into fenced code blocks
            full = normalize_whitespace(full)
            full = wrap_command_runs(full, lang="bash")

            # 3) send as one delta
            yield f"data: {json.dumps({'type':'delta','text':full}, ensure_ascii=False)}\n\n"
    
        yield f"data: {json.dumps({'type':'done'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(sse_gen(), media_type="text/event-stream")


@router.get("/health")
def health():
    return {"ok": True}