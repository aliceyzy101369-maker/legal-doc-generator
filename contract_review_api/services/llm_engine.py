from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import re
import socket
import ssl
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any, List

from contract_review_api.core.models import FieldCandidate, ReviewIssue
from contract_review_api.services.llm_cleaner import clean_llm_field_json, clean_llm_output

logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover - optional dependency fallback
    load_dotenv = None

if load_dotenv:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def degraded_llm_issues(reason: str, *, error_source: str = "llm_subtask") -> List[ReviewIssue]:
    """Public helper for recoverable LLM failures (e.g. per concurrent sub-task)."""
    return _build_fallback_issues(reason, error_source=error_source)


def run_llm_review(fields: List[FieldCandidate], user_position: str | None = None) -> List[ReviewIssue]:
    mode = str(os.getenv("LLM_MODE", "stub")).strip().lower()
    if mode != "real":
        return _run_llm_review_stub(fields, user_position)
    result = run_llm_review_with_debug(fields, user_position)
    return result["issues"]


def run_llm_review_with_debug(fields: List[FieldCandidate], user_position: str | None = None) -> dict[str, Any]:
    """
    Real/stub review with debug payload:
    {
      "raw_output": str,
      "issues": List[ReviewIssue],
      "fallback_reason": Optional[str]
    }
    """
    mode = str(os.getenv("LLM_MODE", "stub")).strip().lower()
    if mode != "real":
        issues = _run_llm_review_stub(fields, user_position)
        return {"raw_output": "[stub mode] no remote call", "issues": issues, "fallback_reason": None}

    api_key = str(os.getenv("LLM_API_KEY", "")).strip()
    base_url = str(os.getenv("LLM_BASE_URL", "")).strip().rstrip("/")
    model = str(os.getenv("LLM_MODEL", "")).strip()
    if not api_key or not base_url or not model:
        issues = _build_fallback_issues(
            "LLM real mode is enabled but key/base_url/model is missing.",
            error_source="llm_subtask",
        )
        return {"raw_output": "", "issues": issues, "fallback_reason": "missing_llm_env"}

    prompt_input = _build_prompt_input(fields, user_position)
    try:
        raw = _call_real_model(
            prompt_input,
            api_key=api_key,
            base_url=base_url,
            model=model,
            system_content=None,
        )
    except TimeoutError:
        issues = _build_fallback_issues(
            "LLM call timeout, fallback to degraded review issues.",
            error_source="llm_subtask",
        )
        return {"raw_output": "", "issues": issues, "fallback_reason": "timeout"}
    except RuntimeError as exc:
        logger.warning("LLM call failed: %s", exc)
        issues = _build_fallback_issues(f"LLM call failed: {exc}", error_source="llm_subtask")
        return {"raw_output": "", "issues": issues, "fallback_reason": "request_error"}

    issues = _parse_llm_issues(raw)
    if not issues:
        issues = _build_fallback_issues(
            "LLM returned empty/invalid issues JSON.",
            error_source="llm_subtask",
        )
        return {"raw_output": raw, "issues": issues, "fallback_reason": "invalid_or_empty_json"}

    return {"raw_output": raw, "issues": issues, "fallback_reason": None}


def _run_llm_review_stub(fields: List[FieldCandidate], user_position: str | None = None) -> List[ReviewIssue]:
    issues: List[ReviewIssue] = []
    if user_position:
        issues.append(
            ReviewIssue(
                title="用户立场提示",
                comment=f"当前用户立场为{user_position}，建议后续在提示词中强化对该立场的风险倾向。",
                degree="低",
                category=0,
            )
        )

    for field in fields:
        if field.field_key == "party_info" and len(field.value) < 6:
            issues.append(
                ReviewIssue(
                    title="主体信息语义完整性提示",
                    comment="主体信息较短，建议通过语义审查补齐主体全称、身份和责任边界。",
                    degree="中",
                    category=0,
                    evidence=field.evidence_paragraphs,
                )
            )
    return issues


def _build_prompt_input(fields: List[FieldCandidate], user_position: str | None) -> str:
    payload = {
        "user_position": user_position or "",
        "fields": [
            {
                "field_key": f.field_key,
                "value": f.value,
                "evidence_paragraphs": f.evidence_paragraphs,
            }
            for f in fields
        ],
        "output_schema": [
            {
                "title": "审查项标题",
                "comment": "审查意见",
                "degree": "高/中/低",
                "category": "0 或 1",
                "change_type": "可选: 修订/删除/新增",
                "revised_text": "可选",
                "evidence": "可选: 段落编号数组",
            }
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def _field_refine_text_limit() -> int:
    raw = os.getenv("FIELD_REFINE_TEXT_LIMIT", "120000") or "120000"
    try:
        return max(4000, int(raw))
    except ValueError:
        return 120000


def _field_refine_chunk_size() -> int:
    raw = os.getenv("FIELD_REFINE_CHUNK_SIZE", "8000") or "8000"
    try:
        return max(2000, min(int(raw), 32000))
    except ValueError:
        return 8000


def _field_refine_max_chunks() -> int:
    raw = os.getenv("FIELD_REFINE_MAX_CHUNKS", "64") or "64"
    try:
        return max(1, min(int(raw), 256))
    except ValueError:
        return 64


def _field_refine_chunk_max_workers() -> int:
    """Parallel field-refine chunk calls; default 1 = sequential (same as single-threaded merge order)."""
    raw = os.getenv("FIELD_REFINE_CHUNK_MAX_WORKERS", "1") or "1"
    try:
        return max(1, min(int(raw), 16))
    except ValueError:
        return 1


def _field_refine_use_chunks() -> bool:
    return str(os.getenv("FIELD_REFINE_USE_CHUNKS", "true") or "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _field_refine_chunk_soft_break() -> bool:
    return str(os.getenv("FIELD_REFINE_CHUNK_SOFT_BREAK", "true") or "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _field_refine_chunk_break_window(chunk_size: int) -> int:
    """Look back this many chars from the hard cut for a newline (paragraph-friendly split)."""
    raw = os.getenv("FIELD_REFINE_CHUNK_BREAK_WINDOW", "") or ""
    if raw.strip():
        try:
            return max(32, min(int(raw), chunk_size))
        except ValueError:
            pass
    return max(120, min(chunk_size // 5, 2000))


def _field_refine_chunk_strategy() -> str:
    """
    FIELD_REFINE_CHUNK_STRATEGY:
    - soft_newline (default): newline-aware windows (FIELD_REFINE_CHUNK_SOFT_BREAK=false -> hard fixed stride)
    - hard: fixed-size slices only
    - markdown_heading: split at ATX headings (# .. ######) then pack into chunk_size (Dify-friendly sections)
    """
    raw = (os.getenv("FIELD_REFINE_CHUNK_STRATEGY", "") or "").strip().lower()
    if raw in ("hard", "fixed"):
        return "hard"
    if raw in ("markdown_heading", "heading", "markdown"):
        return "markdown_heading"
    return "soft_newline"


_HEADING_LINE_ATX = re.compile(r"^#{1,6}\s")


def _split_segments_at_md_headings(text: str) -> list[str]:
    lines = text.splitlines(keepends=True)
    if not lines:
        return []
    segments: list[str] = []
    buf: list[str] = []
    for line in lines:
        if _HEADING_LINE_ATX.match(line) and buf:
            segments.append("".join(buf))
            buf = [line]
        else:
            buf.append(line)
    if buf:
        segments.append("".join(buf))
    return segments


def _chunk_text_soft_newlines(text: str, chunk_size: int, max_chunks: int) -> list[str]:
    """Soft newline chunking (original FIELD_REFINE_CHUNK_SOFT_BREAK behavior)."""
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    window = _field_refine_chunk_break_window(chunk_size)
    min_piece = max(1, chunk_size // 8)
    out: list[str] = []
    pos = 0
    while pos < len(text) and len(out) < max_chunks:
        remain = len(text) - pos
        if remain <= chunk_size:
            out.append(text[pos:])
            break
        end = pos + chunk_size
        search_start = max(pos, end - window)
        cut = text.rfind("\n", search_start, end)
        if cut >= pos and (cut - pos + 1) >= min_piece:
            next_pos = cut + 1
            out.append(text[pos:next_pos])
            pos = next_pos
            continue
        out.append(text[pos:end])
        pos = end
    return out


def _chunk_text_markdown_heading_pack(text: str, chunk_size: int, max_chunks: int) -> list[str]:
    """Prefer cuts at markdown ATX headings, then pack; oversized sections use soft newlines."""
    segments = _split_segments_at_md_headings(text)
    chunks: list[str] = []
    buf = ""
    for seg in segments:
        if len(chunks) >= max_chunks:
            break
        if len(seg) > chunk_size:
            if buf:
                chunks.append(buf)
                buf = ""
                if len(chunks) >= max_chunks:
                    break
            sub_remaining = max_chunks - len(chunks)
            if sub_remaining <= 0:
                break
            sub = _chunk_text_soft_newlines(seg, chunk_size, sub_remaining)
            chunks.extend(sub)
            continue
        if len(buf) + len(seg) <= chunk_size:
            buf += seg
        else:
            if buf:
                chunks.append(buf)
            buf = seg
    if buf and len(chunks) < max_chunks:
        chunks.append(buf)
    return chunks[:max_chunks]


def _chunk_text_hard(text: str, chunk_size: int, max_chunks: int) -> list[str]:
    out: list[str] = []
    for i in range(0, len(text), chunk_size):
        if len(out) >= max_chunks:
            break
        out.append(text[i : i + chunk_size])
    return out


def _chunk_text_for_field_refine(text: str, chunk_size: int, max_chunks: int) -> list[str]:
    """
    Split contract text for field-refine LLM calls.
    FIELD_REFINE_CHUNK_STRATEGY selects algorithm; default soft_newline uses newline windows unless SOFT_BREAK off.
    """
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    strategy = _field_refine_chunk_strategy()
    if strategy == "hard":
        return _chunk_text_hard(text, chunk_size, max_chunks)
    if strategy == "markdown_heading":
        return _chunk_text_markdown_heading_pack(text, chunk_size, max_chunks)
    if not _field_refine_chunk_soft_break():
        return _chunk_text_hard(text, chunk_size, max_chunks)
    return _chunk_text_soft_newlines(text, chunk_size, max_chunks)


def _merge_llm_field_map_parts(
    left: dict[str, dict[str, Any]], right: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Merge multi-chunk extraction maps: same key joins value with \\n; union evidence; max confidence."""
    out: dict[str, dict[str, Any]] = dict(left)
    for key, spec in right.items():
        rv = str(spec.get("value", "") or "").strip()
        if not rv:
            continue
        if key not in out:
            out[key] = {**spec}
            continue
        cur = out[key]
        lv = str(cur.get("value", "") or "").strip()
        ev_l = _normalize_int_list(cur.get("evidence_paragraphs", []))
        ev_r = _normalize_int_list(spec.get("evidence_paragraphs", []))
        try:
            c_l = float(cur.get("confidence", 0.85))
        except (TypeError, ValueError):
            c_l = 0.85
        try:
            c_r = float(spec.get("confidence", 0.85))
        except (TypeError, ValueError):
            c_r = 0.85
        if not lv:
            out[key] = {"value": rv, "evidence_paragraphs": ev_r, "confidence": c_r}
        elif lv == rv:
            out[key] = {
                "value": lv,
                "evidence_paragraphs": sorted(set(ev_l + ev_r)),
                "confidence": max(c_l, c_r),
            }
        else:
            out[key] = {
                "value": f"{lv}\n{rv}",
                "evidence_paragraphs": sorted(set(ev_l + ev_r)),
                "confidence": max(c_l, c_r),
            }
    return out


def _call_real_model(
    prompt_input: str,
    *,
    api_key: str,
    base_url: str,
    model: str,
    timeout: int = 120,
    system_content: str | None = None,
) -> str:
    url = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
    sys_msg = system_content or "你是资深合同审查律师。仅输出JSON数组，不输出解释。"
    request_payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": prompt_input},
        ],
    }
    body = json.dumps(request_payload).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    # Map the "verify" idea from httpx to urllib: use the provided CA bundle
    # when SSL_CERT_FILE is present, otherwise fall back to system defaults.
    verify = os.environ.get("SSL_CERT_FILE", True)
    if verify is True or verify == "":
        ssl_context: ssl.SSLContext | None = ssl.create_default_context()
    else:
        ssl_context = ssl.create_default_context(cafile=str(verify))
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl_context) as resp:
            response_text = resp.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"http {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise TimeoutError("model request timeout") from exc
        raise RuntimeError(str(exc.reason)) from exc

    try:
        parsed = json.loads(response_text)
        return str(parsed["choices"][0]["message"]["content"])
    except Exception as exc:
        raise RuntimeError(f"invalid model response envelope: {response_text}") from exc


def _issues_list_from_cleaned(cleaned: Any) -> list[Any]:
    """Turn clean_llm_output() result into a list of issue dicts when possible."""
    if isinstance(cleaned, list):
        return cleaned
    if isinstance(cleaned, dict):
        for key in ("issues", "comment_list", "data", "items", "results"):
            val = cleaned.get(key)
            if isinstance(val, list):
                return val
        for val in cleaned.values():
            if isinstance(val, list) and val and isinstance(val[0], dict):
                return val
    return []


def _parse_llm_issues(raw: str) -> List[ReviewIssue]:
    cleaned = clean_llm_output(raw)
    data = _issues_list_from_cleaned(cleaned)
    if not data:
        return []

    out: List[ReviewIssue] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        comment = str(item.get("comment", "")).strip()
        degree = str(item.get("degree", "中")).strip() or "中"
        category = _normalize_int(item.get("category", 0), fallback=0)
        change_type = item.get("change_type")
        revised_text = item.get("revised_text")
        evidence = _normalize_int_list(item.get("evidence", []))
        if not title and not comment:
            continue
        out.append(
            ReviewIssue(
                title=title or "模型审查提示",
                comment=comment or "模型返回了空意见。",
                degree=degree,
                category=1 if category == 1 else 0,
                change_type=str(change_type) if change_type is not None else None,
                revised_text=str(revised_text) if revised_text is not None else None,
                evidence=evidence,
            )
        )
    return out


def _build_fallback_issues(reason: str, *, error_source: str = "llm_subtask") -> List[ReviewIssue]:
    return [
        ReviewIssue(
            title="模型审查降级提示",
            comment=reason[:2000],
            degree="低",
            category=0,
            evidence=[],
            error_source=error_source,
        )
    ]


def _normalize_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _field_refine_system_prompt() -> str:
    prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "field_refine_v14.txt"
    if prompt_path.is_file():
        return prompt_path.read_text(encoding="utf-8").strip()
    return (
        "你是资深法务助理，从合同来源文本中抽取指定字段。"
        "仅输出一个 JSON 对象。键为字段名，值为 {\"value\": string, \"evidence_paragraphs\": number[]}。"
        "字段片段使用 段落编号##段落类型##段落内容 行格式；"
        "描述含总结/提炼时归纳不超过300字；含取值范围【A，B】时须判断是否在范围内。"
    )


def _run_llm_field_extraction_one(
    contract_text: str,
    field_names: List[str],
    *,
    api_key: str,
    base_url: str,
    model: str,
    timeout_sec: int,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Single HTTP completion for one contract text segment."""
    warnings: list[str] = []
    unique_names = sorted({str(x).strip() for x in field_names if str(x).strip()})
    payload = {
        "fields_to_extract": unique_names,
        "contract_text": contract_text,
        "output_contract": (
            "一个 JSON 对象：键必须为上述字段名之一；值为 "
            '{"value": string, "evidence_paragraphs": number[]} ；'
            "找不到时 value 用空字符串。不要 markdown 围栏，不要解释。"
        ),
    }
    prompt_input = json.dumps(payload, ensure_ascii=False)
    system_content = _field_refine_system_prompt()
    try:
        raw = _call_real_model(
            prompt_input,
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout=timeout_sec,
            system_content=system_content,
        )
    except TimeoutError:
        warnings.append("llm_field_refine_timeout")
        return {}, warnings
    except RuntimeError:
        warnings.append("llm_field_refine_request_error")
        return {}, warnings

    obj = clean_llm_field_json(raw)
    if not obj:
        warnings.append("llm_field_refine_parse_failed")
        return {}, warnings

    return _normalize_llm_field_map(obj), warnings


def run_llm_field_extraction(contract_text: str, field_names: List[str]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """
    Dify mode_23-style semantic field extraction from full contract text.
    Returns (normalized_map field_key -> {value, evidence_paragraphs, confidence}, warnings).

    LLM_MODE=stub: no HTTP; returns ({}, []).
    LLM_MODE=real: OpenAI-compatible chat/completions; long text is split into chunks
    (FIELD_REFINE_CHUNK_SIZE, default 8000) unless FIELD_REFINE_USE_CHUNKS=false.
    FIELD_REFINE_CHUNK_STRATEGY selects soft_newline / hard / markdown_heading splits.
    FIELD_REFINE_CHUNK_MAX_WORKERS>1 runs chunk calls in parallel; results merge in chunk order.
    FIELD_REFINE_CHUNK_SOFT_BREAK (default true) prefers cutting at newlines near chunk boundaries (soft_newline / default path).
    """
    warnings: list[str] = []
    mode = str(os.getenv("LLM_MODE", "stub")).strip().lower()
    if mode != "real":
        return {}, []

    api_key = str(os.getenv("LLM_API_KEY", "")).strip()
    base_url = str(os.getenv("LLM_BASE_URL", "")).strip().rstrip("/")
    model = str(os.getenv("LLM_MODEL", "")).strip()
    if not api_key or not base_url or not model:
        warnings.append("llm_field_refine_missing_env")
        return {}, warnings

    limit = _field_refine_text_limit()
    text = contract_text if len(contract_text) <= limit else contract_text[:limit]
    if len(contract_text) > limit:
        warnings.append("llm_field_refine_text_truncated")

    try:
        timeout_sec = int(os.getenv("FIELD_REFINE_LLM_TIMEOUT", "120") or "120")
    except ValueError:
        timeout_sec = 120
    timeout_sec = max(10, min(timeout_sec, 600))

    chunk_size = _field_refine_chunk_size()
    max_chunks = _field_refine_max_chunks()
    use_chunks = _field_refine_use_chunks() and len(text) > chunk_size

    if not use_chunks:
        return _run_llm_field_extraction_one(
            text,
            field_names,
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout_sec=timeout_sec,
        )

    chunks = _chunk_text_for_field_refine(text, chunk_size, max_chunks)
    strat = _field_refine_chunk_strategy()
    if strat != "soft_newline":
        warnings.append(f"llm_field_refine_chunk_strategy:{strat}")
    if len(chunks) > 1:
        warnings.append(f"llm_field_refine_chunked:{len(chunks)}")
    if len(text) > len("".join(chunks)):
        warnings.append("llm_field_refine_chunk_cap_truncated")

    workers = _field_refine_chunk_max_workers()
    merged, chunk_warnings = _run_llm_field_extraction_chunks(
        chunks,
        field_names,
        workers=workers,
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_sec=timeout_sec,
        extraction_fn=None,
    )
    warnings.extend(chunk_warnings)
    if len(chunks) > 1 and workers > 1:
        warnings.append(f"llm_field_refine_chunk_parallel:{workers}")
        logger.info(
            "llm field refine parallel chunk_count=%s workers=%s field_name_count=%s",
            len(chunks),
            workers,
            len(field_names),
        )

    return merged, warnings


def _run_llm_field_extraction_chunks(
    chunks: list[str],
    field_names: List[str],
    *,
    workers: int,
    api_key: str,
    base_url: str,
    model: str,
    timeout_sec: int,
    extraction_fn: Callable[..., tuple[dict[str, dict[str, Any]], list[str]]] | None = None,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Run per-chunk extraction; merge maps in chunk index order (stable vs completion order)."""
    warnings: list[str] = []
    if not chunks:
        return {}, warnings

    one = extraction_fn or _run_llm_field_extraction_one

    if workers <= 1 or len(chunks) == 1:
        merged: dict[str, dict[str, Any]] = {}
        for ch in chunks:
            part, w = one(
                ch,
                field_names,
                api_key=api_key,
                base_url=base_url,
                model=model,
                timeout_sec=timeout_sec,
            )
            warnings.extend(w)
            merged = _merge_llm_field_map_parts(merged, part)
        return merged, warnings

    indexed_results: list[tuple[int, dict[str, dict[str, Any]], list[str]]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_idx = {
            pool.submit(
                one,
                ch,
                field_names,
                api_key=api_key,
                base_url=base_url,
                model=model,
                timeout_sec=timeout_sec,
            ): idx
            for idx, ch in enumerate(chunks)
        }
        for fut in concurrent.futures.as_completed(future_to_idx):
            idx = future_to_idx[fut]
            try:
                part, w = fut.result()
            except Exception as exc:
                warnings.append(f"llm_field_refine_chunk_worker_error:{type(exc).__name__}")
                part, w = {}, []
            indexed_results.append((idx, part, w))

    merged_parallel: dict[str, dict[str, Any]] = {}
    for idx, part, w in sorted(indexed_results, key=lambda x: x[0]):
        warnings.extend(w)
        merged_parallel = _merge_llm_field_map_parts(merged_parallel, part)
    return merged_parallel, warnings


def _normalize_llm_field_map(obj: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for k, v in obj.items():
        key = str(k).strip()
        if not key:
            continue
        if isinstance(v, str):
            out[key] = {"value": v.strip(), "evidence_paragraphs": [], "confidence": 0.85}
            continue
        if isinstance(v, dict):
            val = str(v.get("value", "") or "").strip()
            ev = _normalize_int_list(v.get("evidence_paragraphs", []))
            conf_raw = v.get("confidence", 0.85)
            try:
                conf = float(conf_raw)
            except (TypeError, ValueError):
                conf = 0.85
            out[key] = {"value": val, "evidence_paragraphs": ev, "confidence": min(max(conf, 0.0), 1.0)}
    return out


def _normalize_int_list(value: Any) -> List[int]:
    if isinstance(value, list):
        out: List[int] = []
        for item in value:
            try:
                out.append(int(item))
            except (TypeError, ValueError):
                continue
        return out
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return []
        return _normalize_int_list(parsed)
    return []
