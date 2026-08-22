"""Safe local-file conversion and Markdown chunking for chat retrieval."""
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Dict, List, Optional, Tuple
import re

from fastapi import HTTPException, UploadFile

ALLOWED_SUFFIXES = {'.pdf', '.docx', '.pptx', '.xlsx', '.xls', '.csv', '.txt', '.md', '.html', '.htm', '.json', '.xml'}
MAX_MARKDOWN_CHARS = 2_000_000
CHUNK_SIZE = 1_500
CHUNK_OVERLAP = 200

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
    suffix = _safe_suffix(upload.filename)
    raw_bytes = await upload.read()

    markdown = ""
    try:
        from markitdown import MarkItDown
        with NamedTemporaryFile(suffix=suffix, delete=False) as temp:
            temporary_path = Path(temp.name)
            temp.write(raw_bytes)
        try:
            res = MarkItDown(enable_plugins=False).convert_local(temporary_path)
            markdown = (getattr(res, 'text_content', '') or str(res)).strip()
        finally:
            temporary_path.unlink(missing_ok=True)
    except Exception as exc:
        if suffix in {'.txt', '.md', '.csv', '.json', '.xml', '.html', '.htm'}:
            try:
                markdown = raw_bytes.decode('utf-8', errors='replace').strip()
            except Exception:
                pass

    if not markdown:
        try:
            markdown = raw_bytes.decode('utf-8', errors='replace').strip()
        except Exception:
            pass

    if not markdown:
        raise HTTPException(status_code=422, detail='No readable text was extracted from this document.')
    if len(markdown) > MAX_MARKDOWN_CHARS:
        raise HTTPException(status_code=413, detail='Extracted document text is too large.')
    return {'markdown': markdown, 'chunks': chunk_markdown(markdown)}
