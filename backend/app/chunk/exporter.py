import json
from typing import List, Dict, Any
from .chunk import Chunk


def chunk_to_record(c: Chunk) -> Dict[str, Any]:
    """
    This is a "vector DB ready" record:
    - id: stable chunk id
    - text: the field you embed
    - metadata: filters + provenance
    """
    return {
        "id": c.chunk_id,
        "text": c.text,
        "metadata": {
            "doc_id": c.doc_id,
            "section_path": c.section_path,
            "section_path_str": " > ".join(c.section_path),
            "kind": c.kind,
            "step_no": c.step_no,
            "has_code": c.has_code,
            "commands": c.commands or [],
            "header_level": c.header_level,
            "start_line": c.start_line,
            "end_line": c.end_line,
        },
    }


def write_jsonl(records: List[dict], out_path: str) -> None:
    with open(out_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
