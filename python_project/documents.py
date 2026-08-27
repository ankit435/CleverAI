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
    # 1. Primary extractor: MarkItDown
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
    except Exception:
        markdown = ""

    # 2. PDF Fallback: pdfplumber & pdfminer.six for robust PDF text & table extraction
    if suffix == '.pdf' and (not markdown or len(markdown) < 20):
        try:
            import pdfplumber
            import io
            with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
                pages_text = []
                for i, page in enumerate(pdf.pages):
                    p_text = page.extract_text()
                    if p_text and p_text.strip():
                        pages_text.append(f"## Page {i + 1}\n\n{p_text.strip()}")
                if pages_text:
                    markdown = '\n\n'.join(pages_text)
        except Exception:
            pass

    # 3. Plaintext/UTF-8 fallback for textual documents
    if not markdown and suffix in {'.txt', '.md', '.csv', '.json', '.xml', '.html', '.htm'}:
        try:
            markdown = raw_bytes.decode('utf-8', errors='replace').strip()
        except Exception:
            pass

    # 4. Binary/Raw fallback decode if still empty
    if not markdown:
        try:
            decoded = raw_bytes.decode('utf-8', errors='replace').strip()
            # Only use if printable characters dominate
            printable = sum(1 for c in decoded if c.isprintable() or c in '\n\r\t')
            if printable > len(decoded) * 0.7:
                markdown = decoded
        except Exception:
            pass

    if not markdown:
        raise HTTPException(status_code=422, detail='No readable text was extracted from this document.')
    if len(markdown) > MAX_MARKDOWN_CHARS:
        raise HTTPException(status_code=413, detail='Extracted document text is too large.')
    return {'markdown': markdown, 'chunks': chunk_markdown(markdown)}
