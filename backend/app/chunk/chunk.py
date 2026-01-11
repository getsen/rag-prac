import re
import logging
from dataclasses import dataclass
from typing import List, Optional

CODE_BLOCK_RE = re.compile(r"```[^\n]*\n(.*?)\n```", re.DOTALL)
COMMENT_RE = re.compile(r"^\s*(#|//)")

CODE_FENCE_BLOCK_RE = re.compile(
    r"```[^\n]*\n(.*?)\n```", re.DOTALL
)

HEADER_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
FENCE_RE = re.compile(r"^```")
STEP_RE = re.compile(r"^\s*(\d+)\.\s+(.+)$")  # "1. Do thing"

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """Represents a chunk of markdown content."""
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


class ChunkProcessor:
    """Processes markdown documents into chunks."""
    
    def __init__(self, procedure_aware: bool = True, verbose: bool = False):
        """
        Initialize ChunkProcessor.
        
        Args:
            procedure_aware: Split numbered procedures into per-step chunks
            verbose: Print chunk details during processing
        """
        self.procedure_aware = procedure_aware
        self.verbose = verbose
        logger.info(f"ChunkProcessor initialized with procedure_aware={procedure_aware}, verbose={verbose}")

    @staticmethod
    def extract_code_blocks_loose(text: str) -> list[str]:
        """
        Extract fenced code blocks using a state machine.
        Tolerates missing closing fences (still returns the block).
        """
        blocks: list[str] = []
        in_fence = False
        buf: list[str] = []

        for line in text.splitlines():
            if line.strip().startswith("```"):
                if not in_fence:
                    in_fence = True
                    buf = []
                else:
                    # closing fence
                    blocks.append("\n".join(buf))
                    buf = []
                    in_fence = False
                continue

            if in_fence:
                buf.append(line)

        # If unclosed fence, keep what we have
        if in_fence and buf:
            blocks.append("\n".join(buf))

        return blocks

    @staticmethod
    def extract_commands_from_blocks(code_blocks: list[str]) -> list[str]:
        """Extract command lines from code blocks."""
        commands: list[str] = []
        for block in code_blocks:
            for line in block.splitlines():
                ln = line.rstrip()
                if not ln.strip():
                    continue
                if ln.lstrip().startswith("#") or ln.lstrip().startswith("//"):
                    continue
                commands.append(ln)
        return commands

    @staticmethod
    def extract_commands(code_blocks: List[str]) -> List[str]:
        """Extract commands from code blocks."""
        cmds: List[str] = []
        for block in code_blocks:
            for line in block.splitlines():
                ln = line.strip("\n")
                if not ln.strip():
                    continue
                if COMMENT_RE.match(ln):
                    continue
                cmds.append(ln.rstrip())
        return cmds

    @staticmethod
    def make_chunk_id(doc_id: str, section_path: List[str], kind: str, step_no: Optional[int], start_line: int) -> str:
        """Generate a unique chunk ID."""
        import hashlib
        raw = f"{doc_id}|{' > '.join(section_path)}|{kind}|{step_no}|{start_line}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def close_unbalanced_fences(text: str) -> str:
        """
        If a chunk contains an odd number of ``` fences, append a closing fence.
        This keeps the chunk syntactically valid Markdown.
        """
        fence_count = sum(1 for line in text.splitlines() if line.strip().startswith("```"))
        if fence_count % 2 == 1:
            return text.rstrip() + "\n```"
        return text
    
    @staticmethod
    def _find_code_block_boundaries(lines: List[str]) -> List[tuple[int, int]]:
        """
        Find start and end line indices of all code blocks.
        Returns list of (start_idx, end_idx) tuples.
        """
        boundaries = []
        in_fence = False
        fence_start = None
        
        for i, line in enumerate(lines):
            if line.strip().startswith("```"):
                if not in_fence:
                    in_fence = True
                    fence_start = i
                else:
                    in_fence = False
                    if fence_start is not None:
                        boundaries.append((fence_start, i))
                        fence_start = None
        
        # If unclosed fence, close at end of lines
        if in_fence and fence_start is not None:
            boundaries.append((fence_start, len(lines) - 1))
        
        return boundaries

    def enrich_chunk(self, doc_id: str, text: str, section_path: List[str], header_level: int, 
                    start_line: int, end_line: int, kind: str, step_no: Optional[int]) -> Chunk:
        """Enrich a chunk with code extraction and metadata."""
        text = self.close_unbalanced_fences(text)
        blocks = self.extract_code_blocks_loose(text)
        cmds = self.extract_commands_from_blocks(blocks)
        has_code = len(blocks) > 0
        
        # Extract language hints from code block headers
        code_languages = self._extract_code_languages(text)
        
        # Enhance text with code block keywords to improve semantic search
        # This ensures code blocks are found even with generic queries
        if has_code and code_languages:
            code_context = f"\n[CODE BLOCK - Languages: {', '.join(code_languages)}]"
            text = text + code_context
        
        # Prepend section headers to improve semantic search
        # This makes "Prerequisites" chunk findable even with vague queries
        if section_path:
            headers_text = " > ".join(section_path)
            text = f"Section: {headers_text}\n\n{text}"
        
        chunk_id = self.make_chunk_id(doc_id, section_path, kind, step_no, start_line)
        return Chunk(
            chunk_id=chunk_id,
            doc_id=doc_id,
            text=text,
            section_path=section_path,
            header_level=header_level,
            start_line=start_line,
            end_line=end_line,
            kind=kind,
            step_no=step_no,
            has_code=has_code,
            commands=cmds,
        )
    
    @staticmethod
    def _extract_code_languages(text: str) -> List[str]:
        """Extract code block language hints (e.g., 'typescript', 'python')."""
        languages = []
        for line in text.splitlines():
            if line.strip().startswith("```"):
                # Extract language after backticks: ```typescript -> 'typescript'
                lang = line.strip()[3:].strip().lower()
                if lang and not lang.startswith("(") and lang not in ['', 'js', 'py']:
                    languages.append(lang)
        return languages

    def _split_steps_with_fences(self, lines: List[str], base_meta: dict, doc_id: str, file_path: str) -> List[Chunk]:
        """
        Split content into narrative + per-step chunks.
        Assumes fences are triple-backticks.
        """
        out: List[Chunk] = []
        in_fence = False

        # Find where the section header ends (we include it in every produced chunk for context)
        header_line = lines[0]
        body_lines = lines[1:]

        # Identify step start indices (only when not in fence)
        step_starts: List[tuple[int, int]] = []  # (body_idx, step_no)
        for i, line in enumerate(body_lines):
            if FENCE_RE.match(line.strip()):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            m = STEP_RE.match(line)
            if m:
                step_starts.append((i, int(m.group(1))))

        # If no steps found, just return as one "section" chunk
        if not step_starts:
            text = "\n".join(lines).strip()
            return [
                self.enrich_chunk(
                    text=text,
                    doc_id=doc_id,
                    section_path=base_meta["section_path"],
                    header_level=base_meta["header_level"],
                    start_line=base_meta["start_line"],
                    end_line=base_meta["end_line"],
                    kind="section",
                    step_no=None,
                )
            ]

        # Narrative = everything before first step (if any meaningful text)
        first_step_idx, _ = step_starts[0]
        narrative_body = body_lines[:first_step_idx]
        narrative_text = "\n".join([header_line] + narrative_body).strip()
        if narrative_text and narrative_text != header_line.strip():
            out.append(
                self.enrich_chunk(
                    text=narrative_text,
                    doc_id=doc_id,
                    section_path=base_meta["section_path"],
                    header_level=base_meta["header_level"],
                    start_line=base_meta["start_line"],
                    end_line=base_meta["end_line"],
                    kind="narrative",
                    step_no=None,
                )
            )

        # Steps = from each step start to just before next step start
        step_ranges = []
        for j, (start_idx, step_no) in enumerate(step_starts):
            end_idx = step_starts[j + 1][0] if j + 1 < len(step_starts) else len(body_lines)
            step_ranges.append((start_idx, end_idx, step_no))

        for start_idx, end_idx, step_no in step_ranges:
            step_text = "\n".join([header_line] + body_lines[start_idx:end_idx]).strip()
            out.append(
                self.enrich_chunk(
                    text=step_text,
                    doc_id=doc_id,
                    section_path=base_meta["section_path"],
                    header_level=base_meta["header_level"],
                    start_line=base_meta["start_line"],
                    end_line=base_meta["end_line"],
                    kind="step",
                    step_no=step_no,
                )
            )

        return out

    def process_file(self, file_path: str) -> List[Chunk]:
        """
        Process a markdown file and return chunks.
        
        Args:
            file_path: Path to markdown file
            
        Returns:
            List of Chunk objects
        """
        logger.info(f"Processing file: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            md = f.read()

        lines = md.splitlines()
        chunks: List[Chunk] = []

        section_stack: List[tuple[int, str]] = []
        current_lines: List[str] = []
        current_start_line = 1
        current_level = 0
        in_fence = False

        def current_path() -> List[str]:
            return [t for _, t in section_stack]
        
        def append_chunk(text: str, base_meta: dict, kind_value: str, step_no_value: int) -> None:
            doc_id = file_path
            chunks.append(
                self.enrich_chunk(
                    text=text,
                    doc_id=doc_id,
                    section_path=base_meta["section_path"],
                    header_level=base_meta["header_level"],
                    start_line=base_meta["start_line"],
                    end_line=base_meta["end_line"],
                    kind=kind_value,
                    step_no=step_no_value,
                )
            )

        def flush(end_line: int) -> None:
            nonlocal current_lines, current_start_line, current_level

            text = "\n".join(current_lines).strip("\n")
            # skip ROOT chunks that are empty/whitespace
            if not text.strip():
                current_lines = []
                current_start_line = end_line + 1
                return

            base_meta = dict(
                section_path=current_path().copy(),
                header_level=current_level,
                start_line=current_start_line,
                end_line=end_line,
            )

            if self.procedure_aware:
                # Split only if the chunk begins with a header line
                if current_lines and HEADER_RE.match(current_lines[0]):
                    chunks.extend(self._split_steps_with_fences(current_lines, base_meta, file_path, file_path))
                else:
                    append_chunk(text, base_meta, "section", None)
            else:
                append_chunk(text, base_meta, "section", None)

            current_lines = []
            current_start_line = end_line + 1

        for idx, line in enumerate(lines, start=1):
            if FENCE_RE.match(line.strip()):
                in_fence = not in_fence
                current_lines.append(line)
                continue

            m = HEADER_RE.match(line) if not in_fence else None
            if m:
                # new header -> flush previous chunk
                flush(idx - 1)

                level = len(m.group(1))
                title = m.group(2).strip()

                while section_stack and section_stack[-1][0] >= level:
                    section_stack.pop()
                section_stack.append((level, title))

                current_level = level
                current_start_line = idx
                current_lines.append(line)
            else:
                current_lines.append(line)

        flush(len(lines))

        if self.verbose:
            for i, c in enumerate(chunks, 1):
                print("\n==============================")
                print(f"CHUNK {i}  [{c.kind}{'' if c.step_no is None else f' #{c.step_no}'}]")
                print("------------------------------")
                path = " > ".join(c.section_path) if c.section_path else "ROOT"
                print(f"Section Path : {path}")
                print(f"Header Level : {c.header_level}")
                print(f"Lines       : {c.start_line}-{c.end_line}")
                print(f"Has Code    : {c.has_code}")
                print("------------------------------")
                print(c.text)

        logger.info(f"Processed {len(chunks)} chunks from {file_path}")
        return chunks


# Global processor instance for backward compatibility
_chunk_processor = ChunkProcessor(procedure_aware=True, verbose=False)


def chunks_from_file(file_path: str, procedure_aware: bool = True) -> List[Chunk]:
    """
    Legacy function for backward compatibility.
    Reads Markdown and chunks by headers, and optionally splits numbered procedures into per-step chunks.
    """
    processor = ChunkProcessor(procedure_aware=procedure_aware, verbose=True)
    return processor.process_file(file_path)


# Legacy helper functions for backward compatibility
def extract_code_blocks_loose(text: str) -> list[str]:
    """Legacy function."""
    return ChunkProcessor.extract_code_blocks_loose(text)


def extract_commands_from_blocks(code_blocks: list[str]) -> list[str]:
    """Legacy function."""
    return ChunkProcessor.extract_commands_from_blocks(code_blocks)


def extract_commands(code_blocks: List[str]) -> List[str]:
    """Legacy function."""
    return ChunkProcessor.extract_commands(code_blocks)


def make_chunk_id(doc_id: str, section_path: List[str], kind: str, step_no: Optional[int], start_line: int) -> str:
    """Legacy function."""
    return ChunkProcessor.make_chunk_id(doc_id, section_path, kind, step_no, start_line)


def close_unbalanced_fences(text: str) -> str:
    """Legacy function."""
    return ChunkProcessor.close_unbalanced_fences(text)
