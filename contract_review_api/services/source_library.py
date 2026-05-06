from __future__ import annotations

from pathlib import Path


def build_source_library(
    contract_subject: str,
    main_contract: str,
    annexes: str,
    business_info: str,
) -> list[dict]:
    """
    Dify-style field source library (src=1..4). Empty strings are kept; do not drop entries.
    """
    return [
        {"src": 1, "content": contract_subject or ""},
        {"src": 2, "content": main_contract or ""},
        {"src": 3, "content": annexes or ""},
        {"src": 4, "content": business_info or ""},
    ]


def assemble_source_inputs(
    base_text: str,
    remote_attachment_texts: list[str],
    local_paths: list[Path],
    *,
    contract_subject: str = "",
    business_info: str = "",
) -> tuple[str, str, str, str]:
    """
    Map ingest outputs into the four source slots.
    - Main narrative: inline/remote main text plus first local file body (if any).
    - Annexes: remote attachment bodies + further local paths.
    """
    from contract_review_api.services.text_processing import read_contract_path

    main_parts: list[str] = []
    if str(base_text or "").strip():
        main_parts.append(str(base_text).strip())
    if local_paths:
        main_parts.append(read_contract_path(Path(local_paths[0])).strip())
    main_contract = "\n\n".join(p for p in main_parts if p)

    annex_chunks: list[str] = []
    for t in remote_attachment_texts or []:
        s = str(t or "").strip()
        if s:
            annex_chunks.append(s)
    for p in list(local_paths or [])[1:]:
        s = read_contract_path(Path(p)).strip()
        if s:
            annex_chunks.append(s)
    annexes = "\n\n".join(annex_chunks)

    return (
        str(contract_subject or ""),
        main_contract,
        annexes,
        str(business_info or ""),
    )


def format_source_library_for_llm(library: list[dict]) -> str:
    """Serialize sources for mode_23-style extraction (labeled blocks, no raw secrets)."""
    parts: list[str] = []
    for item in library or []:
        try:
            src = int(item.get("src", 0))
        except (TypeError, ValueError):
            src = 0
        content = str(item.get("content", "") or "")
        parts.append(f"[src={src}]\n{content}")
    return "\n\n".join(parts)
