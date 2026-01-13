#!/usr/bin/env python3
"""
Test script for hybrid search strategy.
"""

from app.rag.hybrid_search import QueryDecomposer, HybridSearchStrategy


def test_query_decomposition():
    """Test query decomposition."""
    print("=" * 70)
    print("Testing Query Decomposition")
    print("=" * 70)
    
    test_queries = [
        "list all api endpoints with get method",
        "how to create a user",
        "show me all reports",
        "what are database configurations",
        "explain session management",
    ]
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        search_query = QueryDecomposer.decompose(query)
        print(f"  Intent: {search_query.intent}")
        print(f"  Comprehensive: {search_query.is_comprehensive}")
        print(f"  Sub-queries:")
        for i, sq in enumerate(search_query.decomposed, 1):
            print(f"    {i}. {sq}")


def test_synonym_expansion():
    """Test synonym expansion."""
    print("\n" + "=" * 70)
    print("Testing Synonym Expansion")
    print("=" * 70)
    
    test_queries = [
        "get user endpoints",
        "delete configuration settings",
        "create new API",
    ]
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        expanded = QueryDecomposer.expand_with_synonyms(query)
        print(f"  Expanded queries:")
        for i, eq in enumerate(expanded, 1):
            print(f"    {i}. {eq}")


def test_hybrid_search_strategy():
    """Test hybrid search strategy."""
    print("\n" + "=" * 70)
    print("Testing Hybrid Search Strategy")
    print("=" * 70)
    
    strategy = HybridSearchStrategy()
    
    test_queries = [
        "list all api endpoints with get method",
        "why you missed reports endpoint",
    ]
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        search_queries = strategy.get_search_queries(query)
        print(f"  Search queries to execute ({len(search_queries)}):")
        for i, sq in enumerate(search_queries, 1):
            print(f"    {i}. {sq}")
        
        analysis = strategy.analyze_query(query)
        print(f"  Analysis:")
        print(f"    Intent: {analysis['intent']}")
        print(f"    Comprehensive: {analysis['is_comprehensive']}")
        print(f"    Should expand: {analysis['should_expand']}")
        print(f"    Should use BM25: {analysis['should_use_bm25']}")


if __name__ == "__main__":
    test_query_decomposition()
    test_synonym_expansion()
    test_hybrid_search_strategy()
    print("\n" + "=" * 70)
    print("All tests completed!")
    print("=" * 70)
