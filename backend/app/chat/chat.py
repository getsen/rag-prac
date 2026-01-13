from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import logging
import json
import re
import asyncio
import random
from app.config import settings
from app.rag.rag_query import retrieve_chunks, build_context
from app.llm.ollama.ollama_client_stream import ollama_generate_stream
from app.chat.conversation_context import get_or_create_conversation


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

class ChatRequest(BaseModel):
    message: str
    section_contains: Optional[str] = None
    conversation_id: Optional[str] = None  # For maintaining context across turns

class ChatResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    used_filters: Dict[str, Any]
    conversation_id: Optional[str] = None  # Return conversation ID for client to track


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
    def is_greeting(message: str) -> bool:
        """Check if message is a greeting."""
        greetings = [
            r'\bhi\b', r'\bhello\b', r'\bhey\b', r'\bgreetings\b',
            r'\bhowdy\b', r'\bgood\s+(morning|afternoon|evening)\b',
            r'\bwhat\s+is\s+up\b', r'\bwhats\s+up\b', r'\bsup\b',
            r'\bhow\s+are\s+you\b', r'\bhow\s+do\s+you\s+do\b',
            r'\b(hello|hi)\s+there\b', r'\bhello\s+(there|world)\b'
        ]
        message_lower = message.strip().lower()
        return any(re.search(pattern, message_lower) for pattern in greetings)

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

    def _stream_greeting(self, conversation_id: Optional[str] = None) -> StreamingResponse:
        """Stream a friendly greeting response."""
        # Get conversation context
        conv_id, ctx_manager = get_or_create_conversation(conversation_id)
        
        greetings = [
            "Hello! 👋 I'm your technical assistant. How can I help you today?",
            "Hi there! 👋 What technical information can I help you find?",
            "Hey! 👋 Ask me anything about the runbooks and documentation.",
            "Greetings! 👋 I'm here to help with technical questions.",
        ]
        
        greeting_response = random.choice(greetings)
        
        def gen():
            # Stream greeting response word by word
            words = greeting_response.split()
            yield f"data: {json.dumps({'type':'meta','sources': [], 'conversation_id': conv_id}, ensure_ascii=False)}\n\n"
            
            for word in words:
                yield f"data: {json.dumps({'type':'delta','text': word + ' '}, ensure_ascii=False)}\n\n"
            
            yield f"data: {json.dumps({'type':'final','text': greeting_response}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type':'done'}, ensure_ascii=False)}\n\n"
            
            # Record greeting in conversation history
            ctx_manager.add_turn("assistant", greeting_response)
        
        return StreamingResponse(gen(), media_type="text/event-stream")

    def process_chat_stream(self, req: ChatRequest) -> StreamingResponse:
        """Process a chat request and return streaming response with adaptive RAG."""
        logger.info("--------------------------------------------------------------------------")
        logger.info(f"Processing chat request with conversation_id: {req.conversation_id}")
        
        # Get or create conversation context
        conv_id, ctx_manager = get_or_create_conversation(req.conversation_id)
        
        logger.info(f"Using conversation ID: {conv_id}, message: {req.message[:50]}")
        
        # Add user message to conversation history
        ctx_manager.add_turn("user", req.message)
        
        # Check if this is a greeting
        if self.is_greeting(req.message):
            greeting_response = self._stream_greeting(conversation_id=conv_id)
            return greeting_response
        
        # Lazy import to avoid circular dependencies
        from app.rag.adaptive_rag import get_adaptive_rag
        
        # Use adaptive RAG for intelligent retrieval and generation
        adaptive_rag = get_adaptive_rag()
        
        # Get conversation context to enrich the query
        conv_context = ctx_manager.get_context_for_rag()
        
        def sse_gen():
            response_text = ""
            try:
                # Run async adaptive RAG in sync context with conversation context
                result = adaptive_rag.query_sync(
                    req.message, 
                    conversation_context=conv_context.get('full_context', '')
                )
                
                response_text = result.get('response', '')
                sources = result.get('sources', [])
                
                # Check for failure only if response is empty or explicitly indicates failure
                failure_indicators = [
                    'could not find',
                    'not found',
                    'Error processing',
                    'I could not find',
                ]
                is_failure = (not response_text or 
                             any(indicator.lower() in response_text.lower() for indicator in failure_indicators))
                
                if is_failure:
                    logger.warning(f"Adaptive RAG failed to retrieve relevant content for: {req.message}")
                    yield f"data: {json.dumps({'type':'meta','sources': [], 'conversation_id': conv_id}, ensure_ascii=False)}\n\n"
                    yield f"data: {json.dumps({'type':'final','text': 'NOT_FOUND: Not covered by the indexed documents.'}, ensure_ascii=False)}\n\n"
                    yield f"data: {json.dumps({'type':'done'}, ensure_ascii=False)}\n\n"
                    return
                
                # Send sources with conversation ID
                yield f"data: {json.dumps({'type':'meta','sources': sources, 'conversation_id': conv_id}, ensure_ascii=False)}\n\n"
                
                # Process response for formatting
                parts = response_text.split()
                full_text = []
                
                for part in parts:
                    full_text.append(part)
                    current_text = ' '.join(full_text)
                    
                    # Normalize and format
                    normalized = self.normalize_whitespace(current_text)
                    formatted = self.wrap_command_runs(normalized, lang="bash")
                    
                    # Stream delta
                    yield f"data: {json.dumps({'type':'delta','text': part + ' '}, ensure_ascii=False)}\n\n"
                    # Stream formatted version
                    yield f"data: {json.dumps({'type':'final','text': formatted}, ensure_ascii=False)}\n\n"
                
                # Final response
                final_text = self.normalize_whitespace(response_text)
                final_text = self.wrap_command_runs(final_text, lang="bash")
                response_text = final_text
                
                yield f"data: {json.dumps({'type':'final','text': final_text}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type':'done'}, ensure_ascii=False)}\n\n"
                
                logger.info(f"Adaptive RAG completed successfully for query, attempts={result.get('attempts', 1)}")
                
            except Exception as e:
                logger.error(f"Error in adaptive RAG streaming: {e}")
                error_msg = f'Error: {str(e)}'
                response_text = error_msg
                yield f"data: {json.dumps({'type':'meta','sources': [], 'conversation_id': conv_id}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type':'final','text': error_msg}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type':'done'}, ensure_ascii=False)}\n\n"
            
            finally:
                # Add assistant response to conversation history
                if response_text:
                    ctx_manager.add_turn("assistant", response_text)
        
        return StreamingResponse(sse_gen(), media_type="text/event-stream")

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
            "You are a friendly and helpful technical assistant.\n"
            "You must respond using ONLY the provided context content for technical questions.\n\n"

            "GREETING HANDLING:\n"
            "- If the user greets you (Hi, Hello, Hey, etc.), respond warmly and ask how you can help.\n"
            "- For greetings, ignore the context and provide a friendly response.\n"
            "- Keep greetings brief and welcoming.\n\n"

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

        prompt = f"""Represent this sentence for searching relevant passages: 
        {query}

        Context:
            {ctx['context_text']}

        Instructions:
        - Answer using the context only.
        - If commands/steps are required, keep order and be concise.
        - Automatically detect any commands, configuration, or code.
        - Separate them from explanatory text.
        - Each block must be explicitly labeled as "text" or "code".
        - Do not merge text and code in the same block.
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


@router.post("/conversations")
def create_conversation():
    """Create a new conversation and get its ID."""
    from app.chat.conversation_context import get_conversation_store
    conv_store = get_conversation_store()
    conv_id, ctx_manager = conv_store.get_or_create_conversation()
    
    summary = ctx_manager.get_conversation_summary()
    return {
        "conversation_id": conv_id,
        "summary": summary,
    }


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
    """Get conversation history and metadata."""
    from app.chat.conversation_context import get_conversation_store
    conv_store = get_conversation_store()
    ctx_manager = conv_store.get_conversation(conversation_id)
    
    if not ctx_manager:
        return {"error": "Conversation not found"}, 404
    
    return {
        "conversation_id": conversation_id,
        "summary": ctx_manager.get_conversation_summary(),
        "history": ctx_manager.export_history(),
    }


@router.get("/conversations/{conversation_id}/summary")
def get_conversation_summary(conversation_id: str):
    """Get conversation summary without full history."""
    from app.chat.conversation_context import get_conversation_store
    conv_store = get_conversation_store()
    ctx_manager = conv_store.get_conversation(conversation_id)
    
    if not ctx_manager:
        return {"error": "Conversation not found"}, 404
    
    return ctx_manager.get_conversation_summary()


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str):
    """Delete a conversation."""
    from app.chat.conversation_context import get_conversation_store
    conv_store = get_conversation_store()
    deleted = conv_store.delete_conversation(conversation_id)
    
    if not deleted:
        return {"error": "Conversation not found"}, 404
    
    return {"message": f"Conversation {conversation_id} deleted"}


@router.get("/conversations")
def list_conversations():
    """List all active conversations."""
    from app.chat.conversation_context import get_conversation_store
    conv_store = get_conversation_store()
    conversations = conv_store.list_conversations()
    
    return {
        "total_conversations": len(conversations),
        "conversations": conversations,
    }


@router.get("/health")
def health():
    """Health check endpoint."""
    return {"ok": True}
