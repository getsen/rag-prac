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
        compact_parts = []
        
        # Keep recent N turns verbatim
        if total_turns <= max_recent_turns:
            # If we have few turns, return full context
            return self.get_context_window(include_system=False)
        
        recent_start = max(0, total_turns - max_recent_turns)
        
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
        
        return "\n".join(compact_parts)
    
    def get_context_for_rag(self, use_compact: bool = True) -> Dict[str, str]:
        """
        Get context formatted specifically for RAG queries.
        
        Args:
            use_compact: If True, uses compacted context for full_context.
                        If False, returns full uncompacted context.
        
        Returns:
            Dictionary with 'recent_context' and 'full_context'
        """
        if use_compact:
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
