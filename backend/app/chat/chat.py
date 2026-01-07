from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import logging
import json
from app.rag.rag_query import _looks_like_command_request, retrieve_chunks, build_context
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
    mode: str = "normal"  # "normal" | "commands_only"

class ChatResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    used_filters: Dict[str, Any]

OLLAMA_MODEL = "llama2" 

@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    # Retrieval defaults:
    # - If asking for commands/steps, it's often best to bias to step chunks w/ code
    # You can override via request fields.
    hits = retrieve_chunks(
        query=req.message,
        k=req.top_k,
        kind_filter=req.kind,
        require_code=req.require_code,
        section_contains=req.section_contains,
    )

    ctx = build_context(req.message, hits)

    # auto suggest mode
    if req.mode == "normal" and _looks_like_command_request(req.message):
        inferred_mode = "commands_only"
    else:
        inferred_mode = req.mode

    logger.info(f"Chat inferred mode: {inferred_mode}")
    
    if inferred_mode == "commands_only":
        # system = (
        #     "You are a precise runbook assistant. Use ONLY the provided context. "
        #     "Return ONLY the commands, in execution order, one per line. "
        #     "Do not add explanations. Do not add extra commands. "
        #     "If the commands are not present in the context, reply exactly: NOT_FOUND"
        # )

        # prompt = f"""User question:
        # {req.message}

        # Context:
        # {ctx['context_text']}

        # Return ONLY the commands, one per line, in order:
        # """

        # flatten commands from hits in order
        cmds = []
        for h in hits:
            cmds.extend(h["metadata"].get("commands") or [])
        cmds = [c for c in cmds if c.strip()]

        answer = "\n".join(cmds) if cmds else "NOT_FOUND"

        if answer != "NOT_FOUND":
            # Choose language if you can infer; bash is safe default
            answer = f"```bash\n{answer}\n```"

        return ChatResponse(
            answer=answer,
            sources=ctx["sources"],
            used_filters={
                "top_k": req.top_k,
                "kind": req.kind,
                "require_code": req.require_code,
                "section_contains": req.section_contains,
                "mode": req.mode,
            },
        )
    else:
        system = (
            "You are a precise technical assistant. Use ONLY the provided context. "
            "Do not invent commands, flags, or steps. "
            "If the answer is not in the context, say you cannot find it in the docs. "
            "Keep steps/commands in original order. "
            "Avoid time estimates or operational claims not present in the docs."
        )
        sources_text = "\n".join(f"- {s['source']}" for s in ctx["sources"])
        prompt = f"""User question:
        {req.message}

        Context:
        {ctx['context_text']}

        Instructions:
        - Answer using the context only.
        - If providing steps/commands, keep order and be brief.
        - Sources:
        {sources_text}

        Answer:
    """

    answer = ollama_generate(model=OLLAMA_MODEL, prompt=prompt, system=system, temperature=0.2)

    return ChatResponse(
        answer=answer.strip(),
        sources=ctx["sources"],
        used_filters={
            "top_k": req.top_k,
            "kind": req.kind,
            "require_code": req.require_code,
            "section_contains": req.section_contains,
        },
    )

@router.post("/chat/stream")
def chat_stream(req: ChatRequest):
    hits = retrieve_chunks(
        query=req.message,
        k=req.top_k,
        kind_filter=req.kind,
        require_code=req.require_code,
        section_contains=req.section_contains,
    )

    ctx = build_context(req.message, hits)

    # commands_only: stream is optional; simplest is return once as SSE
    if req.mode == "commands_only":
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

        for chunk in ollama_generate_stream(
            model=OLLAMA_MODEL,
            prompt=prompt,
            system=system,
            temperature=0.2,
        ):
            yield f"data: {json.dumps({'type':'delta','text':chunk}, ensure_ascii=False)}\n\n"

        yield f"data: {json.dumps({'type':'done'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(sse_gen(), media_type="text/event-stream")


@router.get("/health")
def health():
    return {"ok": True}