from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, List

from contract_review_api.core.models import Paragraph


def _read_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="ignore")

    if suffix == ".docx":
        try:
            from docx import Document  # type: ignore
        except ImportError as exc:
            raise RuntimeError("python-docx is required for .docx parsing") from exc
        document = Document(str(path))
        return "\n".join(p.text for p in document.paragraphs if p.text.strip())

    if suffix == ".pdf":
        try:
            from pypdf import PdfReader  # type: ignore
        except ImportError as exc:
            raise RuntimeError("pypdf is required for .pdf parsing") from exc
        reader = PdfReader(str(path))
        chunks = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(chunks)

    raise RuntimeError(f"Unsupported file format: {path.suffix}")


def split_into_paragraphs(review_id: str, text: str, doc_type: str) -> List[Paragraph]:
    normalized = re.sub(r"\r\n?", "\n", text).strip()
    raw_paras = [p.strip() for p in re.split(r"\n{2,}", normalized) if p.strip()]
    return [
        Paragraph(review_id=review_id, doc_type=doc_type, paragraph_no=i + 1, text=raw)
        for i, raw in enumerate(raw_paras)
    ]


def build_paragraphs(review_id: str, base_text: str, files: Iterable[Path]) -> List[Paragraph]:
    paragraphs: List[Paragraph] = []
    if base_text.strip():
        paragraphs.extend(split_into_paragraphs(review_id, base_text, "main_text"))

    for idx, path in enumerate(files):
        text = _read_file(path)
        doc_type = "contract_file" if idx == 0 else "attachment"
        paragraphs.extend(split_into_paragraphs(review_id, text, doc_type))
    return paragraphs


def chunk_tasks(tasks: list[dict], limit: int = 8000) -> list[dict]:
    """
    Chunk long task inputs so each task "source" stays <= limit characters.

    Chunk strategy:
    1. If the source is a JSON list string, chunk by elements.
    2. If the source is markdown, first split by 一级标题 "# " blocks, then fill chunks by lines.
    3. Keep other fields unchanged; only replace the source field.

    Note: This project historically uses "待审文本" as the source key, while the plan mentions "取值来源".
    We support both keys by preferring "取值来源" and falling back to "待审文本".
    """
    if limit <= 0:
        return list(tasks)

    out: list[dict] = []

    def get_source_key(task: dict) -> str | None:
        if "取值来源" in task:
            return "取值来源"
        if "待审文本" in task:
            return "待审文本"
        return None

    for task in tasks:
        source_key = get_source_key(task)
        if not source_key:
            out.append(task)
            continue

        source = str(task.get(source_key, "") or "")
        if len(source) <= limit:
            out.append(task)
            continue

        # 1) JSON list string chunking
        stripped = source.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            try:
                parsed = json.loads(stripped)
            except Exception:
                parsed = None
            if isinstance(parsed, list):
                chunks: list[str] = []
                current_parts: list[str] = []
                current_len = 0
                for item in parsed:
                    part = str(item)
                    extra = part if not current_parts else "\n" + part
                    if current_parts and current_len + len(extra) > limit:
                        chunks.append("\n".join(current_parts))
                        current_parts = [part]
                        current_len = len(part)
                    else:
                        current_parts.append(part)
                        current_len += len(extra)
                if current_parts:
                    chunks.append("\n".join(current_parts))

                for chunk in chunks:
                    new_task = dict(task)
                    new_task[source_key] = chunk
                    out.append(new_task)
                continue

        # 2) Markdown chunking
        # Split into semantic blocks by 一级标题 "# " (single #).
        lines = source.splitlines()
        blocks: list[list[str]] = []
        current_block: list[str] = []
        for line in lines:
            if re.match(r"^#\s", line):
                if current_block:
                    blocks.append(current_block)
                current_block = [line]
            else:
                if not current_block:
                    current_block = [line]
                else:
                    current_block.append(line)
        if current_block:
            blocks.append(current_block)

        chunks: list[list[str]] = []
        current_chunk: list[str] = []
        current_len = 0
        for block in blocks:
            # Ensure block text doesn't overflow; if it does, split by lines.
            for line in block:
                extra = line if not current_chunk else "\n" + line
                if current_chunk and current_len + len(extra) > limit:
                    chunks.append(current_chunk)
                    current_chunk = [line]
                    current_len = len(line)
                else:
                    current_chunk.append(line)
                    current_len += len(extra)
        if current_chunk:
            chunks.append(current_chunk)

        for chunk_lines in chunks:
            new_task = dict(task)
            new_task[source_key] = "\n".join(chunk_lines).strip()
            out.append(new_task)

    return out
