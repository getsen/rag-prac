#!/usr/bin/env python3
"""
Comprehensive chunk debugging utility.
Dumps all chunks from processed documents into organized files for analysis.
Helps identify chunking issues and missing content.
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Any
from app.chunk.chunk import ChunkProcessor, Chunk

class ChunkDebugger:
    """Debug and visualize chunk formations across documents."""
    
    def __init__(self, docs_folder: str = "docs", output_folder: str = ".chunk_debug"):
        """Initialize the debugger."""
        self.docs_folder = docs_folder
        self.output_folder = output_folder
        self.processor = ChunkProcessor(procedure_aware=True, verbose=False)
        Path(self.output_folder).mkdir(exist_ok=True)
    
    def process_all_documents(self) -> Dict[str, List[Chunk]]:
        """Process all markdown files."""
        all_chunks = {}
        md_files = sorted(Path(self.docs_folder).glob("*.md"))
        
        if not md_files:
            print(f"❌ No markdown files found in {self.docs_folder}")
            return all_chunks
        
        print(f"\n📄 Processing {len(md_files)} markdown files...")
        print("=" * 80)
        
        for md_file in md_files:
            file_name = md_file.name
            print(f"\n📄 Processing: {file_name}")
            
            try:
                chunks = self.processor.process_file(str(md_file))
                all_chunks[file_name] = chunks
                print(f"   ✅ Processed {len(chunks)} chunks")
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        return all_chunks
    
    def write_chunks_to_files(self, all_chunks: Dict[str, List[Chunk]]) -> None:
        """Write chunks to organized files."""
        print(f"\n📝 Writing chunk debug files to {self.output_folder}...")
        print("=" * 80)
        
        for doc_name, chunks in all_chunks.items():
            output_name = doc_name.replace(".md", "")
            self._write_text_visualization(doc_name, chunks, output_name)
            self._write_json_metadata(doc_name, chunks, output_name)
            self._write_html_visualization(doc_name, chunks, output_name)
        
        self._write_summary(all_chunks)
        print(f"\n✅ Debug files written to: {os.path.abspath(self.output_folder)}/")
    
    def _write_text_visualization(self, doc_name: str, chunks: List[Chunk], output_name: str) -> None:
        """Write human-readable text representation of chunks."""
        output_file = Path(self.output_folder) / f"{output_name}_chunks.txt"
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"CHUNK ANALYSIS FOR: {doc_name}\n")
            f.write("=" * 100 + "\n")
            f.write(f"Total Chunks: {len(chunks)}\n\n")
            
            for i, chunk in enumerate(chunks, 1):
                f.write(f"\n{'='*100}\n")
                f.write(f"CHUNK #{i}\n")
                f.write(f"{'='*100}\n")
                f.write(f"Chunk ID: {chunk.chunk_id}\n")
                f.write(f"Kind: {chunk.kind}")
                if chunk.step_no:
                    f.write(f" (Step #{chunk.step_no})")
                f.write(f"\nLines: {chunk.start_line}-{chunk.end_line}\n")
                f.write(f"Has Code: {chunk.has_code}\n")
                f.write(f"Header Level: {chunk.header_level}\n")
                
                if chunk.section_path:
                    section_path = " > ".join(chunk.section_path)
                    f.write(f"Section Path: {section_path}\n")
                else:
                    f.write(f"Section Path: ROOT\n")
                
                if chunk.commands:
                    f.write(f"Commands: {', '.join(chunk.commands)}\n")
                
                f.write(f"\n{'-'*100}\n")
                f.write(f"CONTENT:\n{'-'*100}\n\n")
                f.write(chunk.text)
                f.write(f"\n\n")
        
        print(f"   ✅ {output_file.name}")
    
    def _write_json_metadata(self, doc_name: str, chunks: List[Chunk], output_name: str) -> None:
        """Write JSON metadata for programmatic analysis."""
        output_file = Path(self.output_folder) / f"{output_name}_metadata.json"
        
        chunks_data = []
        for chunk in chunks:
            chunks_data.append({
                "chunk_id": chunk.chunk_id,
                "kind": chunk.kind,
                "step_no": chunk.step_no,
                "section_path": chunk.section_path,
                "header_level": chunk.header_level,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "has_code": chunk.has_code,
                "commands": chunk.commands or [],
                "text_length": len(chunk.text),
            })
        
        metadata = {
            "document": doc_name,
            "total_chunks": len(chunks),
            "chunks": chunks_data
        }
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
    
    def _write_html_visualization(self, doc_name: str, chunks: List[Chunk], output_name: str) -> None:
        """Write interactive HTML visualization of chunks."""
        output_file = Path(self.output_folder) / f"{output_name}_chunks.html"
        
        html = [
            "<!DOCTYPE html><html><head>",
            f"<title>Chunks: {doc_name}</title>",
            "<meta charset='utf-8'><meta name='viewport' content='width=device-width'>",
            "<style>",
            "body{font-family:Arial,sans-serif;background:#f5f5f5;padding:20px;}",
            ".container{max-width:1400px;margin:0 auto;}",
            ".header{background:#2c3e50;color:white;padding:20px;border-radius:5px;margin-bottom:20px;}",
            ".chunk{background:white;margin-bottom:20px;padding:20px;border-left:4px solid #3498db;border-radius:5px;}",
            ".chunk-title{font-weight:bold;font-size:16px;margin-bottom:10px;}",
            ".chunk-meta{font-size:12px;color:#7f8c8d;margin-bottom:10px;}",
            ".tag{display:inline-block;padding:4px 8px;background:#ecf0f1;border-radius:3px;margin-right:5px;font-size:11px;}",
            ".section-path{color:#27ae60;font-size:12px;margin:8px 0;}",
            ".content{background:#f8f9fa;padding:15px;border-radius:3px;font-family:monospace;font-size:12px;max-height:400px;overflow-y:auto;white-space:pre-wrap;}",
            "</style></head><body>",
            "<div class='container'>",
            f"<div class='header'><h1>📄 {doc_name}</h1><p>Total Chunks: {len(chunks)}</p></div>",
        ]
        
        for i, chunk in enumerate(chunks, 1):
            section = " > ".join(chunk.section_path) if chunk.section_path else "ROOT"
            html.append(f"<div class='chunk'>")
            html.append(f"<div class='chunk-title'>Chunk #{i}</div>")
            html.append(f"<div class='chunk-meta'>Lines {chunk.start_line}-{chunk.end_line}</div>")
            html.append(f"<span class='tag'>{chunk.kind}")
            if chunk.step_no:
                html.append(f" #{chunk.step_no}")
            html.append("</span>")
            if chunk.has_code:
                html.append("<span class='tag'>Has Code</span>")
            html.append(f"<div class='section-path'>{section}</div>")
            preview = chunk.text[:500].replace("<", "&lt;").replace(">", "&gt;")
            html.append(f"<div class='content'>{preview}{'...' if len(chunk.text) > 500 else ''}</div>")
            html.append("</div>")
        
        html.extend(["</div></body></html>"])
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(html))
    
    def _write_summary(self, all_chunks: Dict[str, List[Chunk]]) -> None:
        """Write overall summary."""
        output_file = Path(self.output_folder) / "SUMMARY.txt"
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("CHUNK DEBUG SUMMARY\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Total Documents: {len(all_chunks)}\n")
            f.write(f"Total Chunks: {sum(len(c) for c in all_chunks.values())}\n\n")
            
            for doc_name, chunks in all_chunks.items():
                f.write(f"\n{doc_name}:\n")
                f.write(f"  Total Chunks: {len(chunks)}\n")
                
                kinds = {}
                for chunk in chunks:
                    kinds[chunk.kind] = kinds.get(chunk.kind, 0) + 1
                f.write(f"  By Kind: {kinds}\n")
                
                with_code = sum(1 for c in chunks if c.has_code)
                f.write(f"  With Code: {with_code}/{len(chunks)}\n")
                
                if chunks:
                    avg_size = sum(len(c.text) for c in chunks) / len(chunks)
                    f.write(f"  Avg Chunk Size: {avg_size:.0f} chars\n")


def main():
    """Main debug function."""
    debugger = ChunkDebugger(docs_folder="docs", output_folder=".chunk_debug")
    all_chunks = debugger.process_all_documents()
    
    if not all_chunks:
        print("\n❌ No documents to process!")
        return
    
    debugger.write_chunks_to_files(all_chunks)
    
    total_chunks = sum(len(chunks) for chunks in all_chunks.values())
    print(f"\n{'='*80}")
    print(f"📊 STATISTICS")
    print(f"{'='*80}")
    print(f"Total documents: {len(all_chunks)}")
    print(f"Total chunks: {total_chunks}")
    
    for doc_name, chunks in all_chunks.items():
        print(f"\n  {doc_name}: {len(chunks)} chunks")
        
        if "streaming" in doc_name.lower():
            opt_chunks = [c for c in chunks if "Additional Optimizations" in " > ".join(c.section_path)]
            if opt_chunks:
                print(f"    → 'Additional Optimizations' chunks: {len(opt_chunks)}")
                for chunk in opt_chunks:
                    section = " > ".join(chunk.section_path)
                    print(f"      • {section} [{chunk.kind}] ({len(chunk.text)} chars)")
    
    print(f"\n📁 Output: {os.path.abspath(debugger.output_folder)}")
    print(f"💡 Open .chunk_debug/*_chunks.html in your browser")
    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    main()
