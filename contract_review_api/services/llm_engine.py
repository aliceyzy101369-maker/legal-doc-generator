from __future__ import annotations

import json
import logging
import os
import re
import socket
import ssl
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, List

from contract_review_api.core.models import FieldCandidate, ReviewIssue
from contract_review_api.services.llm_cleaner import clean_llm_output

logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover - optional dependency fallback
    load_dotenv = None

if load_dotenv:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")


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
        issues = _build_fallback_issues("LLM real mode is enabled but key/base_url/model is missing.")
        return {"raw_output": "", "issues": issues, "fallback_reason": "missing_llm_env"}

    prompt_input = _build_prompt_input(fields, user_position)
    try:
        raw = _call_real_model(prompt_input, api_key=api_key, base_url=base_url, model=model)
    except TimeoutError:
        issues = _build_fallback_issues("LLM call timeout, fallback to degraded review issues.")
        return {"raw_output": "", "issues": issues, "fallback_reason": "timeout"}
    except RuntimeError as exc:
        logger.warning("LLM call failed: %s", exc)
        issues = _build_fallback_issues(f"LLM call failed: {exc}")
        return {"raw_output": "", "issues": issues, "fallback_reason": "request_error"}

    issues = _parse_llm_issues(raw)
    if not issues:
        issues = _build_fallback_issues("LLM returned empty/invalid issues JSON.")
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


def _call_real_model(prompt_input: str, *, api_key: str, base_url: str, model: str, timeout: int = 30) -> str:
    url = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
    request_payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": "你是资深合同审查律师。仅输出JSON数组，不输出解释。"},
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


def _parse_llm_issues(raw: str) -> List[ReviewIssue]:
    cleaned = clean_llm_output(raw)
    if not isinstance(cleaned, list):
        return []

    out: List[ReviewIssue] = []
    for item in cleaned:
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


def _build_fallback_issues(reason: str) -> List[ReviewIssue]:
    return [
        ReviewIssue(
            title="模型审查降级提示",
            comment=reason,
            degree="低",
            category=0,
            evidence=[],
        )
    ]


def _normalize_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


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

