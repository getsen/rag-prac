# Chunk Debugging Guide

## Overview

The chunk debugging system helps you understand how your markdown documents are being split into chunks for the RAG system. This is crucial for diagnosing why searches return incomplete or fragmented results.

## Running the Debug Tool

### Basic Usage
```bash
cd /path/to/rag-prac/backend
python3 debug_chunks.py
```

### What It Does
1. Scans the `docs/` folder for all `.md` files
2. Processes each document using the ChunkProcessor
3. Applies the merging logic for subsections
4. Generates debug files in `.chunk_debug/` folder
5. Prints statistics to console

### Example Output
```
📄 Processing 6 markdown files...
================================================================================
📄 Processing: streaming_performance_optimization.md
   ✅ Processed 28 chunks
   ...
📝 Writing chunk debug files to .chunk_debug...
   ✅ streaming_performance_optimization_chunks.txt
   ✅ streaming_performance_optimization_metadata.json
   ✅ streaming_performance_optimization_chunks.html

📊 STATISTICS
================================================================================
Total documents: 6
Total chunks: 93
  streaming_performance_optimization.md: 14 chunks
    → 'Additional Optimizations' chunks: 1
      • Streaming Performance Optimizations > Additional Optimizations (Future) [merged_section] (1294 chars)
```

## Output Files

### 1. Text Analysis (`*_chunks.txt`)
Human-readable breakdown of all chunks with:
- Chunk number and ID
- Chunk kind (section, narrative, step, steps, merged_section)
- Header level
- Line numbers in source file
- Section path hierarchy
- Code detection and extracted commands
- Full chunk content

**Use Case**: Read this to see exactly what content is in each chunk

**Example**:
```
==============================
CHUNK #24
==============================
Chunk ID: c5aee7d9dbc4cc...
Kind: section
Lines: 291-307
Has Code: True
Header Level: 3
Section Path: Streaming Performance Optimizations > Additional Optimizations (Future) > 1. Virtual Scrolling
Commands: <FixedSizeList, height={600}, ...>

------------------------------------
CONTENT:
------------------------------------
Section: Streaming Performance Optimizations > Additional Optimizations (Future) > 1. Virtual Scrolling

### 1. Virtual Scrolling
Only render visible messages:
```typescript
...
```
```

### 2. JSON Metadata (`*_metadata.json`)
Machine-readable chunk metadata useful for:
- Programmatic analysis
- Building tools that consume chunk data
- Comparing chunk compositions
- Automated quality checks

**Structure**:
```json
{
  "document": "filename.md",
  "total_chunks": 14,
  "chunks": [
    {
      "chunk_id": "abc123...",
      "kind": "section",
      "step_no": null,
      "section_path": ["Streaming Performance Optimizations", "Additional Optimizations (Future)"],
      "header_level": 2,
      "start_line": 287,
      "end_line": 290,
      "has_code": false,
      "commands": [],
      "text_length": 175
    },
    ...
  ]
}
```

### 3. HTML Visualization (`*_chunks.html`)
Interactive browser-based visualization

**How to use**:
1. Open the `.chunk_debug/streaming_performance_optimization_chunks.html` in your browser
2. Click through chunks to see:
   - Chunk metadata (ID, kind, lines)
   - Color-coded tags (section, narrative, step, merged_section, has code)
   - Section path hierarchy
   - Content preview (500 chars, scrollable)

**Color Coding**:
- 🟢 Green: section chunks
- 🔵 Blue: narrative chunks
- 🟡 Yellow: step chunks
- 🟠 Orange: merged_section chunks
- 🟣 Purple: chunks with code

### 4. Summary (`SUMMARY.txt`)
High-level statistics:
- Total documents and chunks
- Breakdown per document
- Chunk kind distribution
- Code detection statistics
- Average chunk sizes

**Example**:
```
CHUNK DEBUG SUMMARY
================================================================================

Total Documents: 6
Total Chunks: 93

DOCUMENT BREAKDOWN:
--------------------------------------------------------------------------------

streaming_performance_optimization.md:
  Total Chunks: 14
  By Kind: {'section': 12, 'steps': 1, 'merged_section': 1}
  With Code: 7/14
  Avg Chunk Size: 892 chars
```

## Understanding Chunk Types

### `section`
Regular content chunk from a markdown section. Usually created when a header is encountered.

### `narrative`
Introductory text before numbered steps. Contains prose without the procedural steps.

### `step`
Individual procedural step extracted when `procedure_aware=True`. Created from numbered items (1., 2., 3., etc.)

### `steps`
Combined procedural steps. Created when multiple numbered steps are found in a section and grouped together.

### `merged_section`
**New type!** Created when H3+ subsections are merged under a common H2 parent. This prevents fragmentation of related content.

**Example**: "Additional Optimizations" with 3 sub-techniques merged into one chunk.

## How to Diagnose Issues

### Issue: Search Returns Only Partial Content

1. Run `debug_chunks.py`
2. Search in the generated `.html` file for the relevant section
3. Check if content is split across multiple chunks
4. Look at chunk sizes - if one chunk is very small and others are larger, it might be fragmented
5. Check the "Section Path" - sibling paths suggest fragmentation

**Solution**: Consider adding more aggressive merging in `_merge_subsections()`

### Issue: Too Many Chunks

1. Check average chunk size in SUMMARY.txt
2. If very small (< 200 chars average), chunks might be too granular
3. Look at the `.html` visualization to see many small chunks
4. Consider lowering the header level threshold for merging

### Issue: Related Content Not Merged

1. Find the section in the `.txt` file
2. Check the header levels (number of #'s)
3. Verify section paths are related
4. The merging logic only merges H3+ under H2 parents
5. For other patterns, you may need to adjust `_merge_subsections()` logic

## Modifying the Chunking Strategy

The main logic is in `app/chunk/chunk.py`:

### To Change Merging Behavior

Edit the conditions in `_merge_subsections()`:
```python
if (current_chunk.header_level == 2 and  # ← Change threshold here
    next_chunk.header_level >= 3 and     # ← Or here
    len(next_chunk.section_path) == len(current_chunk.section_path) + 1):
```

### To Enable/Disable Merging

```python
# In ChunkProcessor.__init__()
# Add a parameter:
def __init__(self, procedure_aware=True, verbose=False, merge_subsections=True):
    self.merge_subsections = merge_subsections
```

Then conditionally call merging in `process_file()`.

## Workflow for Iterative Improvement

1. **Run debug script**:
   ```bash
   python3 debug_chunks.py
   ```

2. **Review output**:
   - Check `.html` visualization
   - Look for fragmentation patterns
   - Note section paths that seem too granular

3. **Modify chunking logic** in `app/chunk/chunk.py`:
   - Adjust merging conditions
   - Change header level thresholds
   - Add new merging patterns

4. **Re-run debug script** to see changes:
   ```bash
   python3 debug_chunks.py
   ```

5. **Compare statistics**:
   - Check total chunk count
   - Verify "Additional Optimizations" is merged correctly
   - Look for new patterns

6. **Clear database and re-index**:
   ```bash
   rm -rf chroma_db/
   # Restart backend - it will re-index
   ```

7. **Test in the UI**:
   - Query for the section you modified
   - Verify you get complete, uncut responses

## Tips & Tricks

### Finding Specific Sections
Use grep:
```bash
grep -A 10 "Virtual Scrolling" .chunk_debug/streaming_performance_optimization_chunks.txt
```

### Comparing Before/After
Keep previous `.chunk_debug/` folder, run again with different name:
```bash
# Before changes
mkdir .chunk_debug_old
cp -r .chunk_debug/* .chunk_debug_old/

# Make changes, run again
python3 debug_chunks.py

# Compare
diff .chunk_debug_old/SUMMARY.txt .chunk_debug/SUMMARY.txt
```

### Finding All Merged Chunks
```bash
grep "merged_section" .chunk_debug/*_chunks.txt
```

### Check Specific Document
To debug only one document, modify `debug_chunks.py`:
```python
md_files = sorted(Path(self.docs_folder).glob("streaming_performance_optimization.md"))
```

### Validate Chunk Content
Search for keywords in chunks:
```bash
grep -n "Virtual Scrolling\|Debounced Rendering\|Progressive Enhancement" \
  .chunk_debug/streaming_performance_optimization_chunks.txt
```

## Common Issues & Solutions

### "Additional Optimizations" is still fragmented
- Check that H3 subsections are under an H2 parent
- Verify merging condition is correct: `header_level == 2` for parent
- Run debug script to see actual chunk kind values

### Too many small chunks
- Check average chunk size in SUMMARY.txt
- Lower the merging threshold (merge more aggressively)
- Adjust `header_level == 2` to `header_level <= 2`

### Chunks are too large (>2000 chars)
- Increase chunk size for merging
- Split merged chunks into smaller groups
- Adjust the sibling matching logic

### Section paths are confusing
- Section path shows markdown hierarchy: "Parent > Child > Grandchild"
- Each level is one `#` or `##` in markdown
- Use grep to find all chunks with a section:
  ```bash
  grep "Section Path.*Additional Optimizations" .chunk_debug/*.txt
  ```

## Next Steps

After diagnosing and fixing chunk issues:

1. Clear the database: `rm -rf chroma_db/`
2. Restart backend to re-index with new chunks
3. Test queries in the UI
4. Verify improved response quality
5. Run debug script again to confirm chunk structure

The backend will automatically re-index on startup, showing logs like:
```
Merged subsections: 28 → 14 chunks
Ingested document: docs/streaming_performance_optimization.md with 14 chunks
```
