"""Document conversion and semantic Markdown chunking powered by Microsoft MarkItDown."""
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Dict, List, Optional, Tuple
import re

from fastapi import HTTPException, UploadFile
from markitdown import MarkItDown

ALLOWED_SUFFIXES = {'.pdf', '.docx', '.pptx', '.xlsx', '.xls', '.csv', '.txt', '.md', '.html', '.htm', '.json', '.xml'}
MAX_MARKDOWN_CHARS = 2_000_000
CHUNK_SIZE = 1_500
CHUNK_OVERLAP = 200

# Initialize Microsoft MarkItDown converter instance
markitdown_engine = MarkItDown(enable_plugins=False)

def _safe_suffix(filename: Optional[str]) -> str:
    if not filename:
        return '.txt'
    suffix = Path(filename).suffix.lower()
    if not suffix or suffix not in ALLOWED_SUFFIXES:
        return '.txt'
    return suffix

def chunk_markdown(markdown: str) -> List[Dict[str, Any]]:
    """Split by headings first, then into bounded overlapping chunks for retrieval."""
    parts = re.split(r'(?m)^(#{1,6}\s+.+)$', markdown)
    sections: List[Tuple[Optional[str], str]] = []
    heading: Optional[str] = None
    for part in parts:
        if re.match(r'^#{1,6}\s+', part):
            heading = re.sub(r'^#+\s*', '', part).strip()
        elif part.strip():
            sections.append((heading, part.strip()))
    chunks: List[Dict[str, Any]] = []
    for heading, section in sections or [(None, markdown.strip())]:
        start = 0
        while start < len(section):
            end = min(len(section), start + CHUNK_SIZE)
            if end < len(section):
                boundary = section.rfind('\n', start, end)
                if boundary > start + CHUNK_SIZE // 2:
                    end = boundary
            content = section[start:end].strip()
            if content:
                chunks.append({'ordinal': len(chunks), 'heading': heading, 'content': content})
            if end >= len(section):
                break
            start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks

async def convert_upload(upload: UploadFile) -> Dict[str, Any]:
    """Convert any supported document file to clean Markdown using Microsoft MarkItDown."""
    suffix = _safe_suffix(upload.filename)
    raw_bytes = await upload.read()

    markdown = ""
    temporary_path: Optional[Path] = None

    try:
        with NamedTemporaryFile(suffix=suffix, delete=False) as temp:
            temporary_path = Path(temp.name)
            temp.write(raw_bytes)
        
        # Primary conversion: Microsoft MarkItDown engine
        conversion_result = markitdown_engine.convert(str(temporary_path))
        if conversion_result and hasattr(conversion_result, 'text_content'):
            markdown = conversion_result.text_content.strip()
        elif conversion_result:
            markdown = str(conversion_result).strip()
    except Exception as exc:
        # Fallback for plain text formats (.txt, .md, .csv, .json, .xml, .html)
        if suffix in {'.txt', '.md', '.csv', '.json', '.xml', '.html', '.htm'}:
            try:
                markdown = raw_bytes.decode('utf-8', errors='replace').strip()
            except Exception:
                raise HTTPException(status_code=422, detail=f'Microsoft MarkItDown conversion error: {str(exc)[:300]}')
        else:
            raise HTTPException(status_code=422, detail=f'Microsoft MarkItDown conversion error: {str(exc)[:300]}')
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink(missing_ok=True)

    if not markdown and suffix in {'.txt', '.md', '.csv', '.json', '.xml', '.html', '.htm'}:
        markdown = raw_bytes.decode('utf-8', errors='replace').strip()

    if not markdown:
        raise HTTPException(status_code=422, detail='No readable text was extracted by Microsoft MarkItDown.')
    if len(markdown) > MAX_MARKDOWN_CHARS:
        raise HTTPException(status_code=413, detail='Extracted document Markdown exceeds size limits.')

    return {
        'markdown': markdown,
        'chunks': chunk_markdown(markdown)
    }
