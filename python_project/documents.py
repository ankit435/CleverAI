"""Safe local-file conversion and Markdown chunking for chat retrieval."""
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Dict, List
import re

from fastapi import HTTPException, UploadFile

ALLOWED_SUFFIXES = {'.pdf', '.docx', '.pptx', '.xlsx', '.xls', '.csv', '.txt', '.md', '.html', '.htm', '.json', '.xml'}
MAX_MARKDOWN_CHARS = 2_000_000
CHUNK_SIZE = 1_500
CHUNK_OVERLAP = 200

def _safe_suffix(filename: str | None) -> str:
    suffix = Path(filename or '').suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail='Unsupported document type.')
    return suffix

def chunk_markdown(markdown: str) -> List[Dict[str, Any]]:
    """Split by headings first, then into bounded overlapping chunks for retrieval."""
    parts = re.split(r'(?m)^(#{1,6}\s+.+)$', markdown)
    sections: List[tuple[str | None, str]] = []
    heading: str | None = None
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
    try:
        from markitdown import MarkItDown
    except ImportError as exc:
        raise HTTPException(status_code=503, detail='MarkItDown is not installed. Use Python 3.10+ and install project requirements.') from exc
    with NamedTemporaryFile(suffix=suffix, delete=False) as temp:
        temporary_path = Path(temp.name)
        while data := await upload.read(1024 * 1024):
            temp.write(data)
    try:
        markdown = MarkItDown(enable_plugins=False).convert_local(temporary_path).text_content.strip()
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f'Unable to extract this document: {str(exc)[:300]}') from exc
    finally:
        temporary_path.unlink(missing_ok=True)
    if not markdown:
        raise HTTPException(status_code=422, detail='No readable text was extracted from this document.')
    if len(markdown) > MAX_MARKDOWN_CHARS:
        raise HTTPException(status_code=413, detail='Extracted document text is too large.')
    return {'markdown': markdown, 'chunks': chunk_markdown(markdown)}
