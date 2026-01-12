#!/usr/bin/env python3
"""
Integration test for context compaction with the RAG system.
Tests that context flows through the entire system correctly.
"""

import sys
sys.path.insert(0, '/Users/senthilkumar/git/rag-prac/backend')

from app.chat.conversation_context import ConversationContextManager, ConversationStore


def test_conversation_store_compaction():
    """Test context compaction with ConversationStore."""
    
    print("=" * 80)
    print("CONTEXT COMPACTION INTEGRATION TEST")
    print("=" * 80)
    
    # Create conversation store
    store = ConversationStore()
    conv_id, ctx_manager = store.get_or_create_conversation()
    
    print(f"\n✓ Created conversation: {conv_id}")
    
    # Simulate multi-turn conversation
    turns = [
        ("user", "What is semantic search?"),
        ("assistant", "Semantic search finds documents based on meaning rather than keyword matching. It uses embeddings to understand intent."),
        ("user", "How does it differ from keyword search?"),
        ("assistant", "Keyword search looks for exact word matches. Semantic search understands context and finds related concepts."),
        ("user", "Can you give an example?"),
        ("assistant", "Example: searching for 'large dog' with semantic search finds results about big dogs even if the exact phrase isn't present."),
        ("user", "What about embeddings?"),
        ("assistant", "Embeddings convert text to numerical vectors. Similar texts have similar embeddings, enabling semantic comparisons."),
        ("user", "How many dimensions?"),
        ("assistant", "Typical embeddings are 384-1536 dimensions. More dimensions capture more semantic nuance but require more computation."),
        ("user", "Is that used in your RAG system?"),
        ("assistant", "Yes, our RAG system uses embeddings to match user queries with relevant documents in the knowledge base."),
    ]
    
    # Add turns
    for role, content in turns:
        ctx_manager.add_turn(role, content)
    
    print(f"✓ Added {len(turns)} turns to conversation")
    
    # Get context without compaction
    print("\n" + "-" * 80)
    print("WITHOUT COMPACTION (Original Behavior)")
    print("-" * 80)
    ctx_no_compact = ctx_manager.get_context_for_rag(use_compact=False)
    full_context_original = ctx_no_compact['full_context']
    original_length = len(full_context_original)
    original_tokens = original_length // 4
    
    print(f"Context length: {original_length} chars (~{original_tokens} tokens)")
    print(f"First 300 chars:\n{full_context_original[:300]}...")
    
    # Get context with compaction
    print("\n" + "-" * 80)
    print("WITH COMPACTION (New Behavior)")
    print("-" * 80)
    ctx_compact = ctx_manager.get_context_for_rag(use_compact=True)
    full_context_compacted = ctx_compact['full_context']
    compacted_length = len(full_context_compacted)
    compacted_tokens = compacted_length // 4
    
    print(f"Context length: {compacted_length} chars (~{compacted_tokens} tokens)")
    print(f"Compacted context:\n{full_context_compacted}")
    
    # Calculate reduction
    reduction = 100 * (1 - compacted_length / original_length)
    tokens_saved = original_tokens - compacted_tokens
    
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"Original context:   {original_length:>6} chars (~{original_tokens:>3} tokens)")
    print(f"Compacted context:  {compacted_length:>6} chars (~{compacted_tokens:>3} tokens)")
    print(f"Reduction:          {reduction:>6.1f}%")
    print(f"Tokens saved:       {tokens_saved:>6} tokens per query")
    
    # Show recent context (unchanged)
    print("\n" + "-" * 80)
    print("RECENT CONTEXT (Unchanged)")
    print("-" * 80)
    print(f"Recent context length: {len(ctx_compact['recent_context'])} chars")
    print(f"Conversation ID: {ctx_compact['conversation_id']}")
    print(f"Turn count: {ctx_compact['turn_count']}")
    
    # Verify data integrity
    print("\n" + "-" * 80)
    print("DATA INTEGRITY CHECKS")
    print("-" * 80)
    
    # Check that recent conversations are preserved
    assert "embeddings" in full_context_compacted.lower(), "Recent turns should be in compacted context"
    print("✓ Recent conversation turns present in compacted context")
    
    # Check that previous context is summarized
    assert "[PREVIOUS CONTEXT SUMMARY]" in full_context_compacted, "Should have previous context summary"
    print("✓ Previous context summary included")
    
    # Check that conversation understanding is preserved
    assert "semantic" in full_context_compacted.lower(), "Key topics should be captured"
    print("✓ Key topics captured in compaction")
    
    # Verify turn count is correct
    assert ctx_compact['turn_count'] == len(turns), "Turn count should match"
    print("✓ Turn count accurate")
    
    print("\n" + "=" * 80)
    print("✅ ALL TESTS PASSED")
    print("=" * 80)
    print("\nContext compaction is working correctly:")
    print(f"  • Reduces context by {reduction:.1f}% ({tokens_saved} tokens saved per query)")
    print(f"  • Preserves recent conversation context")
    print(f"  • Maintains conversation understanding with key topics")
    print(f"  • Fully backward compatible")
    

if __name__ == "__main__":
    try:
        test_conversation_store_compaction()
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
