#!/usr/bin/env python3
"""
Test with REAL embedding distances to understand aggregation behavior.
"""

import chromadb
from sentence_transformers import SentenceTransformer
import json
from typing import Dict, List, Any

model = SentenceTransformer("BAAI/bge-large-en-v1.5")
client = chromadb.PersistentClient(path="/Users/senthilkumar/git/rag-prac/backend/chroma_db")
collection = client.get_collection("runbook_chunks")

def simulate_with_real_data():
    """Run simul with real embedding distances"""
    
    # The actual queries that hybrid search generates
    queries_to_search = [
        "list all api endpoints with get method",  # Index 0
        "endpoint",  # Index 1
        "endpoint methods",  # Index 2
        "HTTP endpoints",  # Index 3
        "endpoint API",  # Index 4
        "api",  # Index 5
        "method",  # Index 6
        "method API"  # Index 7
    ]
    
    k = 16  # For comprehensive queries
    
    print("=" * 80)
    print("SIMULATING WITH REAL EMBEDDING DISTANCES")
    print("=" * 80)
    
    # Retrieve documents for each query
    all_results = {}
    
    for search_idx, query in enumerate(queries_to_search):
        qemb = model.encode([query], normalize_embeddings=True).tolist()
        res = collection.query(
            query_embeddings=qemb,
            n_results=k,
            include=["documents", "metadatas", "distances"]
        )
        
        docs_list = res["documents"][0] if res.get("documents") else []
        metas_list = res["metadatas"][0] if res.get("metadatas") else []
        dists = res["distances"][0] if res.get("distances") else []
        
        print(f"\n[Search {search_idx}] Query: '{query}'")
        print(f"  Found {len(docs_list)} documents")
        
        all_results[search_idx] = {
            "query": query,
            "results": []
        }
        
        # Store results
        for doc_text, md, dist in zip(docs_list, metas_list, dists):
            doc_id = md.get('doc_id', 'unknown')
            section_path = json.loads(md.get('section_path_json', '[]'))
            hit_id = doc_id + "_" + str(section_path)
            
            is_analytics = '/api/reports/analytics' in doc_text and 'GET' in doc_text
            
            result = {
                "id": hit_id,
                "doc_id": doc_id,
                "section_path": section_path,
                "distance": dist,
                "is_analytics": is_analytics,
                "doc_snippet": doc_text[:50]
            }
            
            all_results[search_idx]["results"].append(result)
            
            if is_analytics:
                print(f"    ⭐ ANALYTICS found at dist={dist:.4f}")
    
    # Now aggregate like the real code does
    print("\n" + "=" * 80)
    print("AGGREGATION PHASE")
    print("=" * 80)
    
    all_hits = {}
    
    for search_idx, data in all_results.items():
        for result in data["results"]:
            hit_id = result["id"]
            dist = result["distance"]
            combined_score = dist + (search_idx * 0.01)
            
            if hit_id not in all_hits:
                all_hits[hit_id] = {
                    "id": hit_id,
                    "distance": dist,
                    "combined_score": combined_score,
                    "is_analytics": result["is_analytics"],
                    "found_in_searches": [search_idx]
                }
            else:
                # Update if better score
                if combined_score < all_hits[hit_id]["combined_score"]:
                    all_hits[hit_id]["combined_score"] = combined_score
                    all_hits[hit_id]["distance"] = dist
                all_hits[hit_id]["found_in_searches"].append(search_idx)
    
    print(f"\nTotal unique documents: {len(all_hits)}")
    
    # Sort
    sorted_hits = sorted(all_hits.values(), key=lambda x: x['combined_score'])
    
    # Check analytics
    analytics_docs = [h for h in sorted_hits if h['is_analytics']]
    
    print(f"\nAnalytics endpoint documents found: {len(analytics_docs)}")
    for doc in analytics_docs:
        print(f"  - Position in sorted list: {sorted_hits.index(doc)}")
        print(f"    - combined_score: {doc['combined_score']:.4f}")
        print(f"    - distance: {doc['distance']:.4f}")
        print(f"    - found_in_searches: {doc['found_in_searches']}")
    
    # Take top k
    final_hits = sorted_hits[:k]
    
    print(f"\nAfter taking top {k}:")
    analytics_in_final = [h for h in final_hits if h['is_analytics']]
    if analytics_in_final:
        print(f"  ✓ Analytics endpoint IS in final results")
        print(f"    Position: {final_hits.index(analytics_in_final[0])}")
    else:
        print(f"  ✗ Analytics endpoint NOT in final results")
        print(f"\n  Cutoff boundary:")
        if k < len(sorted_hits):
            cutoff = sorted_hits[k-1]
            next_item = sorted_hits[k]
            print(f"    - Position {k-1}: score={cutoff['combined_score']:.4f} (in final)")
            print(f"    - Position {k}: score={next_item['combined_score']:.4f} (NOT in final)")
            
            if analytics_docs:
                for doc in analytics_docs:
                    pos = sorted_hits.index(doc)
                    print(f"    - Analytics at position {pos}: score={doc['combined_score']:.4f}")

if __name__ == "__main__":
    simulate_with_real_data()
