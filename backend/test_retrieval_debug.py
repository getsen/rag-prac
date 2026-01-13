#!/usr/bin/env python3
"""
Debug test to trace where /api/reports/analytics endpoint is lost during retrieval and re-ranking.
"""

import json
import logging
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def simulate_retrieval_test():
    """
    Simulate the retrieval and re-ranking process to find where documents are lost.
    """
    print("=" * 80)
    print("SIMULATING RETRIEVAL AND RE-RANKING FOR: list all api endpoints with get method")
    print("=" * 80)
    
    # Simulate 8 comprehensive sub-queries that would be generated
    search_queries = [
        "list all api endpoints with get method",
        "api endpoints with GET method",
        "GET endpoints",
        "api routes",
        "endpoints",
        "HTTP methods GET POST DELETE PUT",
        "API endpoints",
        "services"
    ]
    
    # Simulate documents that would be retrieved from each search
    # Each search returns k=16 results
    simulated_docs = {
        # Search 1: "list all api endpoints with get method"
        search_queries[0]: [
            {"id": "analytics_api_1", "name": "POST /api/reports", "distance": 0.15, "source": "analytics_api.json"},
            {"id": "analytics_api_2", "name": "DELETE /api/reports/{report_id}", "distance": 0.18, "source": "analytics_api.json"},
            {"id": "session_api_1", "name": "GET /api/sessions", "distance": 0.12, "source": "api_endpoints.json"},
            {"id": "session_api_2", "name": "DELETE /api/sessions/{id}", "distance": 0.22, "source": "api_endpoints.json"},
            {"id": "session_api_3", "name": "POST /api/users", "distance": 0.20, "source": "api_endpoints.json"},
            # Missing: analytics_api_0 (GET /api/reports/analytics) - distance 0.35
        ] + [{"id": f"other_{i}", "name": f"Other doc {i}", "distance": 0.40 + i*0.02, "source": "unknown.json"} for i in range(10)],
        
        # Search 2: "api endpoints with GET method"
        search_queries[1]: [
            {"id": "session_api_1", "name": "GET /api/sessions", "distance": 0.08, "source": "api_endpoints.json"},
            {"id": "session_api_3", "name": "POST /api/users", "distance": 0.14, "source": "api_endpoints.json"},
            {"id": "analytics_api_2", "name": "GET /api/reports/{report_id}", "distance": 0.19, "source": "analytics_api.json"},
            {"id": "analytics_api_0", "name": "GET /api/reports/analytics", "distance": 0.25, "source": "analytics_api.json"},
            # Missing others...
        ] + [{"id": f"other_b_{i}", "name": f"Other {i}", "distance": 0.40 + i*0.02, "source": "unknown.json"} for i in range(12)],
        
        # Search 3: "GET endpoints"
        search_queries[2]: [
            {"id": "session_api_1", "name": "GET /api/sessions", "distance": 0.10, "source": "api_endpoints.json"},
            {"id": "analytics_api_2", "name": "GET /api/reports/{report_id}", "distance": 0.16, "source": "analytics_api.json"},
            {"id": "analytics_api_0", "name": "GET /api/reports/analytics", "distance": 0.24, "source": "analytics_api.json"},
            {"id": "session_api_2", "name": "DELETE /api/sessions/{id}", "distance": 0.30, "source": "api_endpoints.json"},
        ] + [{"id": f"other_c_{i}", "name": f"Other {i}", "distance": 0.40 + i*0.02, "source": "unknown.json"} for i in range(12)],
        
        # Search 4-8: Similar patterns
        search_queries[3]: [
            {"id": "session_api_1", "name": "GET /api/sessions", "distance": 0.11, "source": "api_endpoints.json"},
            {"id": "analytics_api_0", "name": "GET /api/reports/analytics", "distance": 0.26, "source": "analytics_api.json"},
            {"id": "analytics_api_2", "name": "GET /api/reports/{report_id}", "distance": 0.17, "source": "analytics_api.json"},
        ] + [{"id": f"other_d_{i}", "name": f"Other {i}", "distance": 0.40 + i*0.02, "source": "unknown.json"} for i in range(13)],
        
        search_queries[4]: [
            {"id": "session_api_1", "name": "GET /api/sessions", "distance": 0.09, "source": "api_endpoints.json"},
            {"id": "analytics_api_0", "name": "GET /api/reports/analytics", "distance": 0.23, "source": "analytics_api.json"},
        ] + [{"id": f"other_e_{i}", "name": f"Other {i}", "distance": 0.40 + i*0.02, "source": "unknown.json"} for i in range(14)],
        
        search_queries[5]: [
            {"id": "session_api_1", "name": "GET /api/sessions", "distance": 0.13, "source": "api_endpoints.json"},
        ] + [{"id": f"other_f_{i}", "name": f"Other {i}", "distance": 0.40 + i*0.02, "source": "unknown.json"} for i in range(15)],
        
        search_queries[6]: [
            {"id": "session_api_1", "name": "GET /api/sessions", "distance": 0.12, "source": "api_endpoints.json"},
            {"id": "analytics_api_0", "name": "GET /api/reports/analytics", "distance": 0.28, "source": "analytics_api.json"},
        ] + [{"id": f"other_g_{i}", "name": f"Other {i}", "distance": 0.40 + i*0.02, "source": "unknown.json"} for i in range(14)],
        
        search_queries[7]: [
            {"id": "session_api_1", "name": "GET /api/sessions", "distance": 0.14, "source": "api_endpoints.json"},
        ] + [{"id": f"other_h_{i}", "name": f"Other {i}", "distance": 0.40 + i*0.02, "source": "unknown.json"} for i in range(15)],
    }
    
    print("\nStep 1: Simulating individual search results")
    print("-" * 80)
    
    for search_idx, query in enumerate(search_queries):
        docs = simulated_docs[query]
        get_docs = [d for d in docs if "GET" in d["name"]]
        print(f"\nSearch {search_idx + 1}: '{query}'")
        print(f"  Total results: {len(docs)}")
        print(f"  GET endpoints found: {len(get_docs)}")
        for doc in get_docs:
            analytics_marker = " ⚠️ ANALYTICS" if "reports/analytics" in doc["name"] else ""
            print(f"    - {doc['name']} (distance: {doc['distance']:.2f}){analytics_marker}")
    
    print("\n\nStep 2: Aggregating results with deduplication")
    print("-" * 80)
    
    # Simulate the aggregation logic from adaptive_rag.py
    all_hits = {}
    search_order = {}
    k = 16
    
    for search_idx, query in enumerate(search_queries):
        docs = simulated_docs[query]
        for doc in docs:
            hit_id = f"{doc['source']}_{doc['name']}"
            combined_score = doc['distance'] + (search_idx * 0.01)
            
            if hit_id not in all_hits:
                all_hits[hit_id] = {
                    "text": doc['name'],
                    "distance": doc['distance'],
                    "combined_score": combined_score,
                    "found_in_searches": [search_idx],
                    "source": doc['source'],
                    "doc_id": doc['id'],
                }
                search_order[hit_id] = search_idx
            else:
                # Keep better score
                if combined_score < all_hits[hit_id]["combined_score"]:
                    all_hits[hit_id]["distance"] = doc['distance']
                    all_hits[hit_id]["combined_score"] = combined_score
                all_hits[hit_id]["found_in_searches"].append(search_idx)
    
    print(f"Total unique documents found: {len(all_hits)}")
    print(f"GET endpoint documents found:")
    
    get_hits = {hit_id: hit for hit_id, hit in all_hits.items() if "GET" in hit["text"]}
    for hit_id, hit in sorted(get_hits.items(), key=lambda x: x[1]["combined_score"]):
        analytics_marker = " ⚠️ ANALYTICS" if "reports/analytics" in hit["text"] else ""
        searches_found = ", ".join(str(s) for s in hit["found_in_searches"])
        print(f"  - {hit['text']}")
        print(f"    Distance: {hit['distance']:.2f}, Combined: {hit['combined_score']:.2f}, Found in searches: [{searches_found}]{analytics_marker}")
    
    # Sort and take top k
    hits = sorted(all_hits.values(), key=lambda x: x['combined_score'])[:k]
    
    print(f"\n\nStep 3: After taking top {k} documents")
    print("-" * 80)
    print(f"Total documents retrieved: {len(hits)}")
    
    get_hits_final = [h for h in hits if "GET" in h["text"]]
    print(f"GET endpoints in final results: {len(get_hits_final)}")
    
    for hit in get_hits_final:
        analytics_marker = " ⚠️ ANALYTICS" if "reports/analytics" in hit["text"] else ""
        print(f"  - {hit['text']} (combined_score: {hit['combined_score']:.2f}){analytics_marker}")
    
    # Check if analytics is present
    analytics_present = any("reports/analytics" in h["text"] for h in get_hits_final)
    if not analytics_present:
        print("\n❌ ISSUE FOUND: /api/reports/analytics is NOT in final retrieved results!")
        print("\nAnalyzing why it was lost:")
        analytics_hit = all_hits.get("analytics_api.json_GET /api/reports/analytics")
        if analytics_hit:
            print(f"  - It was found in searches: {analytics_hit['found_in_searches']}")
            print(f"  - Combined score: {analytics_hit['combined_score']:.2f}")
            print(f"  - Rank in all documents: {len([h for h in all_hits.values() if h['combined_score'] < analytics_hit['combined_score']]) + 1}")
    
    print("\n\nStep 4: Simulating re-ranking with cross-encoder")
    print("-" * 80)
    
    original_query = "list all api endpoints with get method"
    
    # Simulate re-ranking scores (cross-encoder would give these)
    # Higher scores are better for cross-encoder
    rerank_scores = {
        "api_endpoints.json_GET /api/sessions": 8.5,
        "analytics_api.json_GET /api/reports/analytics": 7.2,  # Lower score = worse ranking
        "analytics_api.json_GET /api/reports/{report_id}": 7.8,
    }
    
    print(f"Query: '{original_query}'")
    print(f"\nSimulated re-ranking scores:")
    
    ranked_pairs = []
    for hit in get_hits_final:
        rerank_score = rerank_scores.get(f"{hit['source']}_{hit['text']}", 6.5)
        ranked_pairs.append((hit, rerank_score))
        is_analytics = " ⚠️ ANALYTICS" if "reports/analytics" in hit["text"] else ""
        print(f"  - {hit['text']}: {rerank_score:.2f}{is_analytics}")
    
    # Sort by rerank score descending
    ranked_pairs = sorted(ranked_pairs, key=lambda x: x[1], reverse=True)
    
    print(f"\nAfter re-ranking (top 16):")
    for i, (hit, score) in enumerate(ranked_pairs[:16], 1):
        is_analytics = " ⚠️ ANALYTICS" if "reports/analytics" in hit["text"] else ""
        print(f"  {i}. {hit['text']} (score: {score:.2f}){is_analytics}")
    
    # Check final result
    analytics_final = any("reports/analytics" in h[0]["text"] for h in ranked_pairs[:16])
    if not analytics_final:
        print("\n❌ CRITICAL: /api/reports/analytics was lost during re-ranking!")
        print(f"\nWhy? The re-ranker gave it a score of {rerank_scores.get('analytics_api.json_GET /api/reports/analytics', 'N/A')}")
        print("This is lower than other GET endpoints, causing it to be ranked out of top results.")
    else:
        print("\n✅ /api/reports/analytics is present in final results")


if __name__ == "__main__":
    simulate_retrieval_test()
