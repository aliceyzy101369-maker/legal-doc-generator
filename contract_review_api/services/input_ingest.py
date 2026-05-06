from __future__ import annotations

from pathlib import Path
from typing import List

from contract_review_api.api.schemas import ReviewCreateRequest

# Rough upper bound: text length + file sizes (bytes treated as char budget).
MAX_CONTRACT_INPUT_CHARS = 500_000


class InputIngestError(ValueError):
    pass


def resolve_input_sources(payload: ReviewCreateRequest) -> List[Path]:
    sources: List[Path] = []
    if payload.file_path:
        path = Path(payload.file_path).expanduser()
        if not path.exists():
            raise InputIngestError(f"file_path does not exist: {path}")
        sources.append(path)

    for item in payload.attachment_paths:
        path = Path(item).expanduser()
        if not path.exists():
            raise InputIngestError(f"attachment_path does not exist: {path}")
        sources.append(path)
    return sources


def ensure_request_valid(payload: ReviewCreateRequest) -> None:
    if not payload.text and not payload.file_path:
        raise InputIngestError("Either text or file_path must be provided.")


def check_contract_input_size(payload: ReviewCreateRequest, file_sources: List[Path]) -> None:
    total = len(payload.text or "")
    for p in file_sources:
        try:
            total += int(p.stat().st_size)
        except OSError:
            continue
    if total > MAX_CONTRACT_INPUT_CHARS:
        raise InputIngestError(
            f"Contract input exceeds maximum allowed size ({MAX_CONTRACT_INPUT_CHARS} characters, approximate)."
        )
