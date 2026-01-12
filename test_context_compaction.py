#!/usr/bin/env python3
"""
Test script to demonstrate context compaction in action.
Shows how context is reduced while maintaining conversation understanding.
"""

import sys
sys.path.insert(0, '/Users/senthilkumar/git/rag-prac/backend')

from app.chat.conversation_context import ConversationContextManager
from datetime import datetime


def test_context_compaction():
    """Test the context compaction feature."""
    
    # Create a conversation manager
    ctx = ConversationContextManager(max_history_turns=50, context_window_size=10)
    
    # Simulate a multi-turn conversation
    turns_data = [
        ("user", "What is RAG (Retrieval Augmented Generation)?"),
        ("assistant", "RAG is a technique that combines retrieval and generation. It retrieves relevant documents from a knowledge base and uses them to generate more accurate responses."),
        ("user", "How does it improve search results?"),
        ("assistant", "RAG improves search by providing context from actual documents, reducing hallucinations and improving factual accuracy in responses."),
        ("user", "Tell me about vector embeddings"),
        ("assistant", "Vector embeddings are numerical representations of text. They capture semantic meaning and allow similarity calculations between documents and queries."),
        ("user", "How are embeddings used in RAG systems?"),
        ("assistant", "Embeddings are used to find relevant documents from the knowledge base by comparing query embeddings with document embeddings using similarity metrics."),
        ("user", "What about chunk fragmentation?"),
        ("assistant", "Chunk fragmentation occurs when related content is split across multiple chunks. This can lead to incomplete context retrieval."),
        ("user", "How do we fix it?"),
        ("assistant", "We fix fragmentation by merging subsections and using intelligent chunking strategies that keep related content together."),
    ]
    
    print("=" * 80)
    print("CONTEXT COMPACTION DEMONSTRATION")
    print("=" * 80)
    
    # Add all turns to context manager
    for role, content in turns_data:
        ctx.add_turn(role, content)
    
    # Get uncompacted context
    print("\n1. FULL CONTEXT (Uncompacted):")
    print("-" * 80)
    full_context = ctx.get_context_window(include_system=False)
    print(full_context)
    print(f"\nFull context length: {len(full_context)} characters, ~{len(full_context) // 4} tokens")
    
    # Get compacted context
    print("\n\n2. COMPACTED CONTEXT:")
    print("-" * 80)
    compacted_context = ctx._compact_context(max_recent_turns=4)
    print(compacted_context)
    print(f"\nCompacted context length: {len(compacted_context)} characters, ~{len(compacted_context) // 4} tokens")
    
    # Calculate reduction
    reduction = 100 * (1 - len(compacted_context) / len(full_context))
    print(f"\nContext reduction: {reduction:.1f}%")
    
    # Test get_context_for_rag with compaction
    print("\n\n3. RAG CONTEXT (with compaction enabled):")
    print("-" * 80)
    rag_context_compact = ctx.get_context_for_rag(use_compact=True)
    print(f"Conversation ID: {rag_context_compact['conversation_id']}")
    print(f"Turn count: {rag_context_compact['turn_count']}")
    print(f"\nFull context (compacted):\n{rag_context_compact['full_context']}")
    print(f"\nFull context length: {len(rag_context_compact['full_context'])} characters")
    
    # Test get_context_for_rag without compaction (for comparison)
    print("\n\n4. RAG CONTEXT (without compaction for comparison):")
    print("-" * 80)
    rag_context_full = ctx.get_context_for_rag(use_compact=False)
    print(f"Full context length: {len(rag_context_full['full_context'])} characters")
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total conversation turns: {ctx.turn_counter}")
    print(f"Original context: {len(rag_context_full['full_context'])} chars (~{len(rag_context_full['full_context']) // 4} tokens)")
    print(f"Compacted context: {len(rag_context_compact['full_context'])} chars (~{len(rag_context_compact['full_context']) // 4} tokens)")
    print(f"Reduction: {100 * (1 - len(rag_context_compact['full_context']) / len(rag_context_full['full_context'])):.1f}%")
    print("\nKey benefits of compaction:")
    print("✓ Reduces token usage in subsequent queries")
    print("✓ Keeps recent context for immediate conversation understanding")
    print("✓ Summarizes older context to key entities and topics")
    print("✓ Prevents context bloat in long conversations")


if __name__ == "__main__":
    try:
        test_context_compaction()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
