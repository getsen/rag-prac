#!/usr/bin/env python3
"""
Test to show the actual aggregation behavior of the current code.
"""

import json
import logging
from typing import Dict, List, Any

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_aggregation_logic():
    """
    Simulate the exact aggregation logic from adaptive_rag.py
    to understand what's happening with document deduplication.
    """
    
    print("\n" + "="*80)
    print("TESTING AGGREGATION LOGIC FROM adaptive_rag.py")
    print("="*80)
    
    # Simulate what the retrieval loop produces
    # Each search finds 16 documents, some duplicates
    
    # Using realistic scenario: 8 searches, each returns 16 docs
    # After aggregation we should have ~31 unique documents (as shown in logs)
    # But the actual log showed only 10 documents in final results
    
    k = 16  # For comprehensive queries
    
    # Simulate the all_hits dictionary that would be built
    all_hits = {}
    
    # Simulate 8 searches finding various documents
    # Using realistic combined_score calculations
    searches = [
        # Search 0: main query
        [
            ("api_endpoints.json_['GET /api/sessions']", 0.15, 0),
            ("api_endpoints.json_['DELETE /api/sessions/{id}']", 0.18, 0),
            ("api_endpoints.json_['POST /api/users']", 0.20, 0),
            ("api_endpoints.json_['PUT /api/users/{id}']", 0.22, 0),
            ("analytics_api.json_['GET /api/reports/{report_id}']", 0.19, 0),
            ("analytics_api.json_['POST /api/reports']", 0.15, 0),
            # Note: /api/reports/analytics has distance ~0.30, might not be in top 16
            *[(f"unknown_{i}.json_[doc{i}]", 0.40 + i*0.02, 0) for i in range(10)],
        ],
        # Search 1: "endpoint"
        [
            ("api_endpoints.json_['GET /api/sessions']", 0.08, 1),  # Better distance
            ("analytics_api.json_['GET /api/reports/analytics']", 0.25, 1),  # KEY: Found here!
            ("analytics_api.json_['GET /api/reports/{report_id}']", 0.16, 1),
            ("analytics_api.json_['POST /api/reports']", 0.17, 1),
            *[(f"unknown_{i}.json_[doc{i}]", 0.40 + i*0.02, 1) for i in range(10)],
        ],
        # Search 2: "endpoint methods"
        [
            ("api_endpoints.json_['GET /api/sessions']", 0.10, 2),
            ("analytics_api.json_['GET /api/reports/analytics']", 0.24, 2),  # Better score in this search
            ("analytics_api.json_['GET /api/reports/{report_id}']", 0.16, 2),
            *[(f"unknown_{i}.json_[doc{i}]", 0.40 + i*0.02, 2) for i in range(10)],
        ],
        # Search 3: "HTTP endpoints"
        [
            ("api_endpoints.json_['GET /api/sessions']", 0.11, 3),
            ("analytics_api.json_['GET /api/reports/analytics']", 0.26, 3),
            *[(f"unknown_{i}.json_[doc{i}]", 0.40 + i*0.02, 3) for i in range(10)],
        ],
        # Search 4: "endpoint API"
        [
            ("api_endpoints.json_['GET /api/sessions']", 0.09, 4),
            *[(f"unknown_{i}.json_[doc{i}]", 0.40 + i*0.02, 4) for i in range(10)],
        ],
        # Search 5: "api"
        [
            ("api_endpoints.json_['GET /api/sessions']", 0.14, 5),
            *[(f"unknown_{i}.json_[doc{i}]", 0.40 + i*0.02, 5) for i in range(10)],
        ],
        # Search 6: "method"
        [
            ("analytics_api.json_['GET /api/reports/analytics']", 0.28, 6),
            *[(f"unknown_{i}.json_[doc{i}]", 0.40 + i*0.02, 6) for i in range(10)],
        ],
        # Search 7: "method API"
        [
            ("api_endpoints.json_['GET /api/sessions']", 0.13, 7),
            *[(f"unknown_{i}.json_[doc{i}]", 0.40 + i*0.02, 7) for i in range(10)],
        ],
    ]
    
    # Run the exact aggregation logic
    print("\nProcessing searches with aggregation logic:")
    for search_idx, results in enumerate(searches):
        logger.info(f"Search {search_idx}: {len(results)} results")
        
        for hit_id, dist, idx in results:
            # Calculate combined_score exactly as in the code
            combined_score = dist + (search_idx * 0.01)
            
            if hit_id not in all_hits:
                all_hits[hit_id] = {
                    "id": hit_id,
                    "distance": dist,
                    "combined_score": combined_score,
                    "found_in_searches": [search_idx]
                }
            else:
                # Update if better combined score
                if combined_score < all_hits[hit_id]["combined_score"]:
                    all_hits[hit_id].update({
                        "distance": dist,
                        "combined_score": combined_score,
                    })
                all_hits[hit_id]["found_in_searches"].append(search_idx)
    
    print(f"\n✓ Total aggregated documents: {len(all_hits)}")
    
    # Sort and take top k
    sorted_hits = sorted(all_hits.values(), key=lambda x: x['combined_score'])
    
    print(f"\nAfter sorting by combined_score:")
    print(f"  - Lowest 3 (best): {sorted_hits[:3]}")
    print(f"  - Highest 3 (worst): {sorted_hits[-3:]}")
    print(f"  - Taking top {k} of {len(sorted_hits)}")
    
    if k < len(sorted_hits):
        cutoff = sorted_hits[k-1]
        next_doc = sorted_hits[k]
        print(f"  - Cutoff boundary:")
        print(f"    - doc[{k-1}]: {cutoff['id']} (score: {cutoff['combined_score']:.4f})")
        print(f"    - doc[{k}]: {next_doc['id']} (score: {next_doc['combined_score']:.4f})")
    
    final_hits = sorted_hits[:k]
    
    print(f"\n✓ Final retrieved documents: {len(final_hits)}")
    
    # Check if analytics endpoint made it
    analytics_found = None
    for hit in final_hits:
        if 'analytics' in hit['id'].lower():
            analytics_found = hit
            break
    
    if analytics_found:
        print(f"\n✓ /api/reports/analytics IS in final results:")
        print(f"  - ID: {analytics_found['id']}")
        print(f"  - Combined Score: {analytics_found['combined_score']:.4f}")
        print(f"  - Found in searches: {analytics_found['found_in_searches']}")
    else:
        print(f"\n✗ /api/reports/analytics NOT in final results")
        print(f"\nDocuments around cutoff (k={k}):")
        for i in range(max(0, k-3), min(len(sorted_hits), k+3)):
            hit = sorted_hits[i]
            marker = "<<< CUTOFF >>>" if i == k else ""
            print(f"  [{i}] {hit['id']} (score: {hit['combined_score']:.4f}) {marker}")


if __name__ == "__main__":
    test_aggregation_logic()
