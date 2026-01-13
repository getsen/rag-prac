import json
import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """Represents a chunk of JSON content."""
    chunk_id: str
    doc_id: str
    text: str
    section_path: List[str]
    header_level: int
    start_line: int
    end_line: int
    kind: str
    step_no: Optional[int] = None
    has_code: bool = False
    commands: List[str] = None


class JsonChunkProcessor:
    """Processes JSON documents into semantic chunks."""
    
    def __init__(self, verbose: bool = False):
        """
        Initialize JsonChunkProcessor.
        
        Args:
            verbose: Print chunk details during processing
        """
        self.verbose = verbose
        logger.info(f"JsonChunkProcessor initialized with verbose={verbose}")

    @staticmethod
    def make_chunk_id(doc_id: str, section_path: List[str], kind: str, start_line: int) -> str:
        """Generate a unique chunk ID."""
        path_str = "_".join(section_path).replace(" ", "_").replace("/", "_")
        return f"{doc_id}_{path_str}_{kind}_{start_line}".replace("\\", "/").replace(".json", "")

    def enrich_chunk(
        self,
        text: str,
        doc_id: str,
        section_path: List[str],
        header_level: int,
        start_line: int,
        end_line: int,
        kind: str,
        step_no: Optional[int] = None,
    ) -> Chunk:
        """
        Create a Chunk with enriched metadata.
        
        Args:
            text: The chunk text content
            doc_id: Document identifier
            section_path: Path to this section
            header_level: Header level (0-6)
            start_line: Starting line number
            end_line: Ending line number
            kind: Type of chunk (json_object, json_array, json_property, etc.)
            step_no: Step number if applicable
            
        Returns:
            Enriched Chunk object
        """
        chunk_id = self.make_chunk_id(doc_id, section_path, kind, start_line)
        
        chunk = Chunk(
            chunk_id=chunk_id,
            doc_id=doc_id,
            text=text,
            section_path=section_path,
            header_level=header_level,
            start_line=start_line,
            end_line=end_line,
            kind=kind,
            step_no=step_no,
            has_code=False,
            commands=None,
        )
        
        if self.verbose:
            logger.info(f"Created chunk: {chunk_id} (kind={kind}, lines={start_line}-{end_line})")
        
        return chunk

    def _chunk_json_object(self, obj: Dict[str, Any], doc_id: str, path: List[str] = None, start_line: int = 1) -> List[Chunk]:
        """
        Chunk a JSON object by creating chunks for significant properties.
        
        Args:
            obj: JSON object to chunk
            doc_id: Document ID
            path: Current path in hierarchy
            start_line: Starting line number
            
        Returns:
            List of chunks
        """
        if path is None:
            path = []
        
        chunks = []
        line_num = start_line
        
        for key, value in obj.items():
            current_path = path + [key]
            
            # Create a chunk for this property
            if isinstance(value, (dict, list)):
                # For complex types, serialize and chunk
                text = json.dumps({key: value}, indent=2, ensure_ascii=False)
                kind = "json_object" if isinstance(value, dict) else "json_array"
            else:
                # For scalar values, just show the key-value pair
                text = json.dumps({key: value}, ensure_ascii=False)
                kind = "json_property"
            
            chunk = self.enrich_chunk(
                text=text,
                doc_id=doc_id,
                section_path=current_path,
                header_level=len(current_path),
                start_line=line_num,
                end_line=line_num,
                kind=kind,
                step_no=None,
            )
            chunks.append(chunk)
            line_num += 1
            
            # Recursively chunk nested objects
            if isinstance(value, dict) and value:
                nested_chunks = self._chunk_json_object(value, doc_id, current_path, line_num)
                chunks.extend(nested_chunks)
                line_num += len(nested_chunks)
            
            # For arrays with dict items, create chunks for each item
            elif isinstance(value, list) and value and isinstance(value[0], dict):
                for idx, item in enumerate(value):
                    if isinstance(item, dict):
                        item_path = current_path + [f"[{idx}]"]
                        item_text = json.dumps(item, indent=2, ensure_ascii=False)
                        item_chunk = self.enrich_chunk(
                            text=item_text,
                            doc_id=doc_id,
                            section_path=item_path,
                            header_level=len(item_path),
                            start_line=line_num,
                            end_line=line_num,
                            kind="json_array_item",
                            step_no=idx + 1,
                        )
                        chunks.append(item_chunk)
                        line_num += 1
        
        return chunks

    def process_file(self, file_path: str) -> List[Chunk]:
        """
        Process a JSON file and return semantic chunks.
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            List of Chunk objects
        """
        logger.info(f"Processing JSON file: {file_path}")
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON file {file_path}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return []
        
        chunks: List[Chunk] = []
        doc_id = file_path
        
        if isinstance(data, dict):
            # Chunk object properties
            chunks = self._chunk_json_object(data, doc_id, [], 1)
        
        elif isinstance(data, list):
            # Chunk array items
            for idx, item in enumerate(data):
                text = json.dumps(item, indent=2, ensure_ascii=False)
                chunk = self.enrich_chunk(
                    text=text,
                    doc_id=doc_id,
                    section_path=[f"[{idx}]"],
                    header_level=1,
                    start_line=idx + 1,
                    end_line=idx + 1,
                    kind="json_array_item",
                    step_no=idx + 1,
                )
                chunks.append(chunk)
        
        else:
            # Scalar value at root
            text = json.dumps(data, indent=2, ensure_ascii=False)
            chunk = self.enrich_chunk(
                text=text,
                doc_id=doc_id,
                section_path=["root"],
                header_level=0,
                start_line=1,
                end_line=1,
                kind="json_scalar",
                step_no=None,
            )
            chunks.append(chunk)
        
        logger.info(f"Processed JSON file {file_path}: {len(chunks)} chunks created")
        return chunks


def chunks_from_json_file(file_path: str) -> List[Chunk]:
    """
    Process a JSON file and return semantic chunks.
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        List of Chunk objects
    """
    processor = JsonChunkProcessor(verbose=True)
    return processor.process_file(file_path)
