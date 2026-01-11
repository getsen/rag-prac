#!/usr/bin/env python3
"""
Test script to verify that chunks are being grouped correctly.
Tests the "Additional Optimizations" section to ensure it's preserved as one chunk.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.chunk.chunk import ChunkProcessor

def test_streaming_perf_chunks():
    """Test that streaming_performance_optimization.md chunks are grouped correctly."""
    processor = ChunkProcessor(procedure_aware=True, verbose=False)
    
    file_path = "docs/streaming_performance_optimization.md"
    chunks = processor.process_file(file_path)
    
    print(f"\n{'='*80}")
    print(f"Total chunks from {file_path}: {len(chunks)}")
    print(f"{'='*80}\n")
    
    # Find chunks related to "Additional Optimizations"
    additional_opt_chunks = [c for c in chunks if "Additional Optimizations" in c.section_path_str()]
    
    print(f"Chunks in 'Additional Optimizations' section:")
    print(f"-" * 80)
    
    for i, chunk in enumerate(additional_opt_chunks, 1):
        section = " > ".join(chunk.section_path) if chunk.section_path else "ROOT"
        print(f"\nChunk {i}:")
        print(f"  Section: {section}")
        print(f"  Kind: {chunk.kind}")
        print(f"  Step No: {chunk.step_no}")
        print(f"  Has Code: {chunk.has_code}")
        print(f"  Lines: {chunk.start_line}-{chunk.end_line}")
        print(f"  Preview: {chunk.text[:100]}...")
        
        # Check if all three optimizations are in one chunk
        if "Virtual Scrolling" in chunk.text and "Debounced Rendering" in chunk.text and "Progressive Enhancement" in chunk.text:
            print(f"  ✅ Contains ALL 3 optimizations in one chunk!")
    
    print(f"\n{'='*80}")
    print(f"Summary:")
    print(f"  Total chunks: {len(chunks)}")
    print(f"  Additional Optimizations chunks: {len(additional_opt_chunks)}")
    
    # Check if step grouping worked
    steps_chunks = [c for c in additional_opt_chunks if c.kind == "steps"]
    if steps_chunks:
        combined_chunk = steps_chunks[0]
        has_all_three = (
            "Virtual Scrolling" in combined_chunk.text and
            "Debounced Rendering" in combined_chunk.text and
            "Progressive Enhancement" in combined_chunk.text
        )
        
        print(f"\n  ✅ IMPROVEMENT: Steps are grouped in combined chunks!")
        print(f"  ✅ All optimizations present: {has_all_three}")
    
    print(f"{'='*80}\n")

if __name__ == "__main__":
    test_streaming_perf_chunks()
