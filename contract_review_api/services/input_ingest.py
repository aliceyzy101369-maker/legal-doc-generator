from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from contract_review_api.api.schemas import ReviewCreateRequest
from contract_review_api.services.document_provider import (
    DocumentNotFoundError,
    DocumentProvider,
    DocumentProviderConfigError,
    get_document_provider,
)

# Rough upper bound: merged base text + attachment texts + file sizes (bytes treated as char budget).
MAX_CONTRACT_INPUT_CHARS = 500_000


class InputIngestError(ValueError):
    pass


def resolve_input_sources(payload: ReviewCreateRequest) -> List[Path]:
    """Local paths only (main file_path then attachment_paths)."""
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
    if not (
        (payload.text and payload.text.strip())
        or bool(payload.file_path)
        or bool(payload.resolved_main_document_id())
    ):
        raise InputIngestError("Either text, file_path, or a main document id must be provided.")


def gather_resolved_contract_bundle(
    payload: ReviewCreateRequest,
    provider: DocumentProvider | None = None,
) -> Tuple[str, List[str], List[Path], List[str]]:
    """
    Resolve remote ids + inline text into a main narrative string, remote attachment bodies,
    local filesystem paths, and soft warnings (missing/empty attachments do not fail the request).
    """
    prov = provider or get_document_provider()
    warnings: list[str] = []

    main_chunks: list[str] = []
    main_id = payload.resolved_main_document_id()
    if main_id:
        try:
            main_chunks.append(str(prov.fetch_text(main_id) or "").strip())
        except DocumentNotFoundError as exc:
            raise InputIngestError(str(exc)) from exc
        except DocumentProviderConfigError as exc:
            raise InputIngestError(str(exc)) from exc

    if payload.text and payload.text.strip():
        main_chunks.append(payload.text.strip())

    base_text = "\n\n".join(m for m in main_chunks if m)

    remote_attachment_texts: list[str] = []
    for aid in payload.resolved_attachment_document_ids():
        try:
            t = str(prov.fetch_text(aid) or "")
            if not t.strip():
                warnings.append(f"attachment_empty:{aid}")
            remote_attachment_texts.append(t)
        except DocumentNotFoundError:
            warnings.append(f"attachment_not_found:{aid}")
            remote_attachment_texts.append("")
        except DocumentProviderConfigError as exc:
            warnings.append(f"attachment_fetch_failed:{aid}:{type(exc).__name__}")
            remote_attachment_texts.append("")

    local_paths = resolve_input_sources(payload)
    return base_text, remote_attachment_texts, local_paths, warnings


def estimate_input_budget(
    base_text: str,
    remote_attachment_texts: List[str],
    file_paths: List[Path],
    *,
    extra_chars: int = 0,
) -> int:
    total = len(base_text or "")
    for t in remote_attachment_texts:
        total += len(t or "")
    for p in file_paths:
        try:
            total += int(p.stat().st_size)
        except OSError:
            continue
    return total + max(0, int(extra_chars or 0))


def check_contract_input_budget(total: int) -> None:
    if total > MAX_CONTRACT_INPUT_CHARS:
        raise InputIngestError(
            f"Contract input exceeds maximum allowed size ({MAX_CONTRACT_INPUT_CHARS} characters, approximate)."
        )


# Backward compatibility for older tests
def check_contract_input_size(payload: ReviewCreateRequest, file_sources: List[Path]) -> None:
    total = len(payload.text or "")
    for p in file_sources:
        try:
            total += int(p.stat().st_size)
        except OSError:
            continue
    check_contract_input_budget(total)
