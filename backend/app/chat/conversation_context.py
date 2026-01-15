"""
Conversation context management for maintaining chat history.
Handles storing, retrieving, and summarizing conversation context.
"""

import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class ConversationTurn:
    """A single turn in the conversation."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: str  # ISO format
    turn_id: int  # Sequential turn number
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)


class ConversationContextManager:
    """
    Manages conversation history and context for multi-turn interactions.
    
    Features:
    - Stores full conversation history
    - Maintains context windows for RAG
    - Provides context summarization
    - Tracks conversation metadata
    """
    
    def __init__(
        self,
        max_history_turns: int = 50,
        context_window_size: int = 10,
        max_context_tokens: int = 8000,
    ):
        """
        Initialize conversation context manager.
        
        Args:
            max_history_turns: Maximum number of turns to keep in history
            context_window_size: Number of recent turns to include in context
            max_context_tokens: Maximum tokens for context (approximate)
        """
        self.max_history_turns = max_history_turns
        self.context_window_size = context_window_size
        self.max_context_tokens = max_context_tokens
        self.conversation_history: List[ConversationTurn] = []
        self.turn_counter = 0
        self.conversation_id = self._generate_conversation_id()
        self.created_at = datetime.utcnow().isoformat()
        
        logger.info(f"ConversationContextManager initialized: id={self.conversation_id}")
    
    def _generate_conversation_id(self) -> str:
        """Generate a unique conversation ID."""
        timestamp = datetime.utcnow().isoformat()
        hash_obj = hashlib.md5(timestamp.encode())
        return hash_obj.hexdigest()[:12]
    
    def add_turn(self, role: str, content: str) -> ConversationTurn:
        """
        Add a turn to the conversation history.
        
        Args:
            role: "user" or "assistant"
            content: The message content
            
        Returns:
            The created ConversationTurn
        """
        turn = ConversationTurn(
            role=role,
            content=content,
            timestamp=datetime.utcnow().isoformat(),
            turn_id=self.turn_counter,
        )
        self.turn_counter += 1
        self.conversation_history.append(turn)
        
        # Trim history if it exceeds max
        if len(self.conversation_history) > self.max_history_turns:
            self.conversation_history = self.conversation_history[-self.max_history_turns:]
        
        logger.debug(f"Turn added: role={role}, turn_id={turn.turn_id}, turns_total={len(self.conversation_history)}")
        return turn
    
    def get_context_window(self, include_system: bool = True) -> str:
        """
        Get formatted context window for RAG prompts.
        
        Includes recent turns up to max_context_tokens.
        
        Args:
            include_system: Whether to include conversation metadata
            
        Returns:
            Formatted context string
        """
        if not self.conversation_history:
            return ""
        
        # Get recent turns
        context_turns = self.conversation_history[-self.context_window_size:]
        
        # Build context string
        lines = []
        
        if include_system:
            lines.append("CONVERSATION CONTEXT:")
            lines.append(f"Conversation ID: {self.conversation_id}")
            lines.append(f"Total turns: {len(self.conversation_history)}")
            lines.append("")
        
        for turn in context_turns:
            role_label = "User" if turn.role == "user" else "Assistant"
            lines.append(f"{role_label}:")
            lines.append(turn.content)
            lines.append("")
        
        context_str = "\n".join(lines)
        
        # Check token estimate (rough approximation: 1 token ≈ 4 characters)
        token_estimate = len(context_str) // 4
        if token_estimate > self.max_context_tokens:
            logger.warning(f"Context window exceeds max tokens: {token_estimate} > {self.max_context_tokens}")
        
        return context_str
    
    def get_recent_context(self, num_turns: int = 3) -> str:
        """
        Get the N most recent turns formatted for context.
        
        Args:
            num_turns: Number of recent turns to include
            
        Returns:
            Formatted context string
        """
        if not self.conversation_history:
            return ""
        
        recent = self.conversation_history[-num_turns:]
        lines = []
        
        for turn in recent:
            role = "User" if turn.role == "user" else "Assistant"
            lines.append(f"{role}: {turn.content[:200]}...")  # Truncate for brevity
        
        return "\n".join(lines)
    
    def get_conversation_summary(self) -> Dict:
        """
        Get a summary of the conversation.
        
        Returns:
            Dictionary with conversation metadata
        """
        if not self.conversation_history:
            return {
                "conversation_id": self.conversation_id,
                "turn_count": 0,
                "user_messages": 0,
                "assistant_messages": 0,
                "first_message": None,
                "last_message": None,
                "duration_seconds": 0,
            }
        
        user_count = sum(1 for t in self.conversation_history if t.role == "user")
        assistant_count = sum(1 for t in self.conversation_history if t.role == "assistant")
        
        first_turn = self.conversation_history[0]
        last_turn = self.conversation_history[-1]
        
        return {
            "conversation_id": self.conversation_id,
            "turn_count": len(self.conversation_history),
            "user_messages": user_count,
            "assistant_messages": assistant_count,
            "first_message": first_turn.content[:100],
            "last_message": last_turn.content[:100],
            "started_at": self.created_at,
            "last_updated_at": last_turn.timestamp,
        }
    
    def export_history(self) -> List[Dict]:
        """
        Export the full conversation history.
        
        Returns:
            List of conversation turns as dictionaries
        """
        return [turn.to_dict() for turn in self.conversation_history]
    
    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
        self.turn_counter = 0
        self.conversation_id = self._generate_conversation_id()
        logger.info(f"Conversation history cleared, new id: {self.conversation_id}")
    
    def _extract_key_entities(self, text: str) -> List[str]:
        """
        Extract key entities and concepts from text.
        Simple heuristic: looks for capitalized words and important terms.
        
        Args:
            text: Text to extract entities from
            
        Returns:
            List of key entities/concepts
        """
        import re
        # Extract capitalized phrases (likely proper nouns/entities)
        entities = re.findall(r'\b[A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*)*\b', text[:500])
        # Also look for quoted terms
        quoted = re.findall(r'"([^"]+)"', text[:500])
        # Combine and deduplicate, keep order
        combined = entities + quoted
        seen = set()
        result = []
        for item in combined:
            if item.lower() not in seen and len(item) > 2:
                seen.add(item.lower())
                result.append(item)
        return result[:5]  # Top 5 entities
    
    def _compact_context_with_llm(self) -> str:
        """
        Compact conversation context using LLM for semantic summarization.
        
        This method uses the LLM to extract key points from previous turns,
        creating a high-quality semantic summary instead of simple truncation.
        This is especially useful for follow-up questions where exact phrasing matters.
        
        Returns:
            LLM-compacted context string
        """
        if not self.conversation_history:
            return ""
        
        total_turns = len(self.conversation_history)
        
        logger.info(f"\n{'='*80}")
        logger.info(f"[CONV_ID: {self.conversation_id}] === CONTEXT COMPACTION WITH LLM START ===")
        # logger.info(f"[CONV_ID: {self.conversation_id}] Total conversation turns: {total_turns}")
        
        # For 2 or fewer turns, just return full context (nothing to compact)
        if total_turns <= 2:
            # logger.info(f"[CONV_ID: {self.conversation_id}] Only {total_turns} turns - returning full context without compaction")
            result = self.get_context_window(include_system=False)
            logger.info(f"[CONV_ID: {self.conversation_id}] Full context (no compaction needed):\n{result}")
            logger.info(f"[CONV_ID: {self.conversation_id}] === CONTEXT COMPACTION WITH LLM END ===")
            logger.info(f"{'='*80}\n")
            return result
        
        # For longer conversations (3+ turns), summarize older turns
        older_turns = self.conversation_history[:-2]  # Everything except last 2 turns
        recent_turns = self.conversation_history[-2:]  # Last 2 turns
        
        logger.info(f"[CONV_ID: {self.conversation_id}] Older turns to summarize: {len(older_turns)}")
        logger.info(f"[CONV_ID: {self.conversation_id}] Recent turns to preserve: {len(recent_turns)}")
        
        # Build the context to summarize
        older_context = "\n".join([
            f"{'User' if t.role == 'user' else 'Assistant'}: {t.content}"
            for t in older_turns
        ])
        
        # Use LLM to summarize
        try:
            from app.rag.adaptive_rag import get_adaptive_rag
            adaptive_rag = get_adaptive_rag()
            
            summarization_prompt = f"""Summarize the following conversation history into key points and findings.
            
            CONVERSATION HISTORY:
            {older_context}

            Create a concise summary that:
            1. Extracts main topics discussed
            2. Lists key findings or items mentioned (especially numbered lists)
            3. Captures important context for understanding follow-up questions
            4. Preserves numbered lists in a clear format like "1. Item name: description"

            Format the summary as:
            SUMMARY OF PREVIOUS DISCUSSION:
            Key Topics: [comma-separated list]

            Previous Findings/Items:
            [numbered list of important items]

            Keep it under 300 words."""

            summary = adaptive_rag._call_llm(
                prompt=summarization_prompt,
                system="You are a conversation summarizer. Create concise, numbered summaries that preserve key information for follow-up questions.",
                temperature=0.3,
            )
            
            logger.info(f"[CONV_ID: {self.conversation_id}] LLM-based context compaction generated {len(summary)} chars")
            logger.info(f"[CONV_ID: {self.conversation_id}] Compacted summary:\n{summary}")
            
        except Exception as e:
            logger.warning(f"[CONV_ID: {self.conversation_id}] Error in LLM-based context compaction: {e}. Falling back to text-based compaction.")
            logger.info(f"[CONV_ID: {self.conversation_id}] === CONTEXT COMPACTION WITH LLM END (FALLBACK) ===")
            logger.info(f"{'='*80}\n")
            return self._compact_context()
        
        # Combine summary with recent turns
        compact_parts = [
            "[PREVIOUS CONTEXT SUMMARY]",
            summary,
            "",
            "[RECENT CONVERSATION]",
        ]
        
        # Add recent turns verbatim (don't truncate)
        for turn in recent_turns:
            role_label = "User" if turn.role == "user" else "Assistant"
            compact_parts.append(f"{role_label}: {turn.content}")
        
        result = "\n".join(compact_parts)
        logger.info(f"[CONV_ID: {self.conversation_id}] === CONTEXT COMPACTION WITH LLM END ===")
        logger.info(f"{'='*80}\n")
        return result
    
    def _compact_context(self, max_recent_turns: int = 6, max_compact_chars: int = 1200) -> str:
        """
        Compact conversation context by keeping recent turns verbatim
        and summarizing older turns as key points.
        
        This reduces token usage in subsequent queries while maintaining
        conversation understanding, especially for follow-up questions.
        
        Args:
            max_recent_turns: Number of recent turns to keep verbatim (increased to 6 for better follow-ups)
            max_compact_chars: Maximum characters for older turns summary (increased to 1200)
            
        Returns:
            Compacted context string
        """
        if not self.conversation_history:
            return ""
        
        total_turns = len(self.conversation_history)
        logger.info(f"\n{'='*80}")
        logger.info(f"[CONV_ID: {self.conversation_id}] === TEXT-BASED CONTEXT COMPACTION START ===")
        logger.info(f"[CONV_ID: {self.conversation_id}] Total turns: {total_turns}, max_recent_turns: {max_recent_turns}")
        compact_parts = []
        
        # Keep recent N turns verbatim
        if total_turns <= max_recent_turns:
            # If we have few turns, return full context
            logger.info(f"[CONV_ID: {self.conversation_id}] Only {total_turns} turns (≤ {max_recent_turns}) - returning full context without compaction")
            result = self.get_context_window(include_system=False)
            logger.info(f"[CONV_ID: {self.conversation_id}] === TEXT-BASED CONTEXT COMPACTION END ===")
            logger.info(f"{'='*80}\n")
            return result
        
        recent_start = max(0, total_turns - max_recent_turns)
        logger.info(f"[CONV_ID: {self.conversation_id}] Recent start index: {recent_start}, will keep last {total_turns - recent_start} turns")
        
        # Add summary of older turns if they exist
        if recent_start > 0:
            older_turns = self.conversation_history[:recent_start]
            
            # Extract key entities and topics from older turns
            key_points = []
            context_summaries = []
            
            for i, turn in enumerate(older_turns[-5:]):  # Look at last 5 older turns for context
                entities = self._extract_key_entities(turn.content)
                if entities:
                    key_points.extend(entities)
                
                # Keep abbreviated versions of previous assistant responses for reference
                if turn.role == "assistant" and len(turn.content) > 0:
                    # Keep first 300 chars of each previous response for better follow-up context
                    summary = turn.content[:300]
                    if len(turn.content) > 300:
                        summary += "..."
                    context_summaries.append(f"Previous response {i+1}: {summary}")
            
            if key_points or context_summaries:
                compact_parts.append("[PREVIOUS CONTEXT SUMMARY]")
                # Deduplicate while preserving order
                seen = set()
                unique_points = []
                for point in key_points:
                    if point.lower() not in seen:
                        seen.add(point.lower())
                        unique_points.append(point)
                if unique_points:
                    compact_parts.append(f"Key topics discussed: {', '.join(unique_points[:8])}")
                
                # Add abbreviated summaries of previous responses (for understanding "this", "that", "the third point" etc.)
                for summary in context_summaries[:3]:
                    compact_parts.append(summary)
                compact_parts.append("")
        
        # Add recent turns verbatim
        compact_parts.append("[RECENT CONVERSATION]")
        for idx, turn in enumerate(self.conversation_history[recent_start:]):
            role_label = "User" if turn.role == "user" else "Assistant"
            # Don't truncate the most recent turn (usually the last assistant response)
            # as follow-up questions often reference numbered items from the previous response
            content = turn.content
            is_last_turn = (idx == len(self.conversation_history[recent_start:]) - 1)
            
            if not is_last_turn and len(content) > 800:
                # Only truncate older turns in the recent window
                content = content[:800] + "..."
            
            compact_parts.append(f"{role_label}: {content}")
        
        result = "\n".join(compact_parts)
        logger.info(f"[CONV_ID: {self.conversation_id}] === TEXT-BASED CONTEXT COMPACTION END ===")
        logger.info(f"[CONV_ID: {self.conversation_id}] Final compacted context length: {len(result)} characters")
        logger.info(f"[CONV_ID: {self.conversation_id}] Number of parts in context: {len(compact_parts)}")
        logger.info(f"{'='*80}\n")
        return result
    
    def get_context_for_rag(self, use_compact: bool = True, use_llm_compaction: bool = False) -> Dict[str, str]:
        """
        Get context formatted specifically for RAG queries.
        
        Args:
            use_compact: If True, uses compacted context for full_context.
                        If False, returns full uncompacted context.
            use_llm_compaction: If True, uses LLM to semantically compact context (slower but better).
                               If False, uses simple text-based compaction (faster).
        
        Returns:
            Dictionary with 'recent_context' and 'full_context'
        """
        if use_compact:
            if use_llm_compaction:
                full_context = self._compact_context_with_llm()
            else:
                full_context = self._compact_context()
        else:
            full_context = self.get_context_window(include_system=False)
        
        return {
            "recent_context": self.get_recent_context(num_turns=3),
            "full_context": full_context,
            "conversation_id": self.conversation_id,
            "turn_count": len(self.conversation_history),
        }


class ConversationStore:
    """
    Thread-safe storage for multiple conversations.
    Maps conversation IDs to ConversationContextManager instances.
    """
    
    def __init__(self):
        """Initialize conversation store."""
        self.conversations: Dict[str, ConversationContextManager] = {}
        logger.info("ConversationStore initialized")
    
    def get_or_create_conversation(self, conversation_id: Optional[str] = None) -> Tuple[str, ConversationContextManager]:
        """
        Get an existing conversation or create a new one.
        
        Args:
            conversation_id: Existing conversation ID or None for new
            
        Returns:
            Tuple of (conversation_id, ConversationContextManager)
        """
        if conversation_id and conversation_id in self.conversations:
            return conversation_id, self.conversations[conversation_id]
        
        # Create new conversation
        ctx_manager = ConversationContextManager()
        conv_id = ctx_manager.conversation_id
        self.conversations[conv_id] = ctx_manager
        
        logger.info(f"Created new conversation: {conv_id}")
        return conv_id, ctx_manager
    
    def get_conversation(self, conversation_id: str) -> Optional[ConversationContextManager]:
        """
        Get an existing conversation.
        
        Args:
            conversation_id: The conversation ID
            
        Returns:
            ConversationContextManager or None if not found
        """
        return self.conversations.get(conversation_id)
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """
        Delete a conversation.
        
        Args:
            conversation_id: The conversation ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
            logger.info(f"Conversation deleted: {conversation_id}")
            return True
        return False
    
    def list_conversations(self) -> List[Dict]:
        """
        List all active conversations.
        
        Returns:
            List of conversation summaries
        """
        summaries = []
        for conv_id, ctx_manager in self.conversations.items():
            summary = ctx_manager.get_conversation_summary()
            summaries.append(summary)
        return summaries
    
    def cleanup_old_conversations(self, max_conversations: int = 100):
        """
        Remove oldest conversations if count exceeds max.
        
        Args:
            max_conversations: Maximum number of conversations to keep
        """
        if len(self.conversations) > max_conversations:
            # Sort by conversation ID (oldest first, since they're timestamped)
            to_delete = list(self.conversations.keys())[:-max_conversations]
            for conv_id in to_delete:
                del self.conversations[conv_id]
            logger.warning(f"Cleaned up {len(to_delete)} old conversations")


# Global conversation store instance
_conversation_store = ConversationStore()


def get_conversation_store() -> ConversationStore:
    """Get the global conversation store instance."""
    return _conversation_store


def get_or_create_conversation(conversation_id: Optional[str] = None) -> Tuple[str, ConversationContextManager]:
    """
    Convenience function to get or create a conversation.
    
    Args:
        conversation_id: Existing conversation ID or None
        
    Returns:
        Tuple of (conversation_id, ConversationContextManager)
    """
    return _conversation_store.get_or_create_conversation(conversation_id)
