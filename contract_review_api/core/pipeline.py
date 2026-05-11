from __future__ import annotations

import concurrent.futures
import logging
import os
import time
import uuid

from contract_review_api.api.schemas import (
    FieldOutput,
    IssueOutput,
    ReviewCreateRequest,
    ReviewDryRunResponse,
    ReviewResponse,
)
from contract_review_api.core.models import ReviewIssue, ReviewRequest
from contract_review_api.services.document_provider import get_document_provider
from contract_review_api.services.field_extraction import (
    extract_field_candidates_coarse,
    refine_field_candidates,
)
from contract_review_api.services.input_ingest import (
    check_contract_input_budget,
    ensure_request_valid,
    estimate_input_budget,
    gather_resolved_contract_bundle,
)
from contract_review_api.services.llm_engine import degraded_llm_issues, run_llm_review, run_llm_review_with_debug
from contract_review_api.services.markdown_line_parser import is_dify_markdown_line_document, parse_markdown_lines
from contract_review_api.services.output_transform import build_final_output
from contract_review_api.services.report_render import build_summary, render_markdown
from contract_review_api.services.review_task_builder import build_review_tasks
from contract_review_api.services.ruleset_loader import load_review_rules
from contract_review_api.services.field_extraction_tasks import (
    build_field_extraction_task_split,
    enrich_field_extraction_tasks_with_sources,
)
from contract_review_api.services.pending_field_library import build_pending_object_field_library
from contract_review_api.services.result_merge import issues_for_error_collection, merge_issues, partition_issues_for_final_output
from contract_review_api.services.source_library import assemble_source_inputs, build_source_library
from contract_review_api.services.rule_engine import run_rule_review
from contract_review_api.services.text_processing import build_paragraphs, chunk_tasks

logger = logging.getLogger(__name__)

DEGRADED_ISSUE_TITLE = "模型审查降级提示"


def _review_task_max_workers() -> int:
    """Align with Dify-style iterator default (10), clamped for safety."""
    raw = os.getenv("REVIEW_TASK_MAX_WORKERS", "10") or "10"
    try:
        n = int(raw)
    except ValueError:
        n = 10
    return max(1, min(n, 32))


def _trace_id_for(payload: ReviewCreateRequest) -> str:
    tid = str(payload.trace_id or "").strip()
    return tid or str(uuid.uuid4())


def _should_include_field_extraction_tasks(payload: ReviewCreateRequest) -> bool:
    """Dify §5.1 observability in full review: opt-in via request or FIELD_EXTRACTION_INCLUDE_IN_REVIEW."""
    if payload.include_field_extraction_tasks is True:
        return True
    if payload.include_field_extraction_tasks is False:
        return False
    raw = (os.getenv("FIELD_EXTRACTION_INCLUDE_IN_REVIEW") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _prepare_contract_state(payload: ReviewCreateRequest, review_id: str, trace_id: str) -> dict:
    provider = get_document_provider()
    base_text, remote_atts, local_paths, gather_warnings = gather_resolved_contract_bundle(payload, provider)
    extra_budget = len(str(payload.contract_subject or "")) + len(payload.resolved_src4_business_slot())
    budget = estimate_input_budget(base_text, remote_atts, local_paths, extra_chars=extra_budget)
    check_contract_input_budget(budget)

    source_library = build_source_library(
        *assemble_source_inputs(
            base_text,
            remote_atts,
            local_paths,
            contract_subject=str(payload.contract_subject or "").strip(),
            business_info=payload.resolved_src4_business_slot(),
        )
    )

    input_parse_mode = "plain"
    markdown_line_count = 0
    if base_text.strip() and is_dify_markdown_line_document(base_text):
        input_parse_mode = "markdown_lines"
        markdown_line_count = len(parse_markdown_lines(base_text))

    logger.info(
        "pipeline gather trace_id=%s review_id=%s base_len=%s remote_attachments=%s local_paths=%s parse_mode=%s",
        trace_id,
        review_id,
        len(base_text or ""),
        len(remote_atts),
        len(local_paths),
        input_parse_mode,
    )

    paragraphs = build_paragraphs(
        review_id,
        base_text,
        local_paths,
        extra_attachment_texts=remote_atts,
    )
    if not paragraphs:
        raise RuntimeError("No readable contract content is found from input sources.")

    review_rules = load_review_rules(payload.ruleset_ids)
    pending_object_field_library = build_pending_object_field_library(review_rules)
    field_extraction_tasks = build_field_extraction_task_split(pending_object_field_library)
    coarse = extract_field_candidates_coarse(paragraphs)
    merged_fields, refine_warnings = refine_field_candidates(
        coarse,
        review_rules,
        contract_type_override=payload.contract_type,
        contract_text=base_text,
        source_library=source_library,
    )

    attachment_count = len(payload.attachment_paths) + len(payload.resolved_attachment_document_ids())

    return {
        "base_text": base_text,
        "paragraphs": paragraphs,
        "coarse": coarse,
        "merged_fields": merged_fields,
        "refine_warnings": refine_warnings,
        "review_rules": review_rules,
        "gather_warnings": gather_warnings,
        "input_parse_mode": input_parse_mode,
        "markdown_line_count": markdown_line_count,
        "attachment_count": attachment_count,
        "source_library": source_library,
        "pending_object_field_library": pending_object_field_library,
        "field_extraction_tasks": field_extraction_tasks,
    }


def _source_library_meta(source_library: list[dict]) -> list[dict]:
    out: list[dict] = []
    for item in source_library or []:
        if not isinstance(item, dict):
            continue
        raw_src = item.get("src", 0)
        try:
            src_n = int(raw_src)
        except (TypeError, ValueError):
            src_n = 0
        out.append({"src": src_n, "content_len": len(str(item.get("content", "") or ""))})
    return out


def run_review_pipeline(payload: ReviewCreateRequest) -> ReviewResponse:
    start = time.time()
    ensure_request_valid(payload)
    review_id = str(uuid.uuid4())
    trace_id = _trace_id_for(payload)

    input_type = (
        "text"
        if (payload.text and payload.text.strip())
        else ("remote_id" if payload.resolved_main_document_id() else "file")
    )
    request_meta = ReviewRequest(
        review_id=review_id,
        input_type=input_type,
        source=payload.file_path or payload.resolved_main_document_id() or "inline_text",
        ruleset_ids=payload.ruleset_ids,
    )

    st = _prepare_contract_state(payload, review_id, trace_id)
    coarse: list = st["coarse"]
    merged_fields: list = st["merged_fields"]
    refine_warnings: list = st["refine_warnings"]
    review_rules: list = st["review_rules"]
    gather_warnings: list = st["gather_warnings"]

    review_tasks = build_review_tasks(merged_fields, review_rules, limit=7000)
    review_tasks = chunk_tasks(review_tasks, limit=8000)
    chunk_count = len(review_tasks)

    bootstrap_issues: list[ReviewIssue] = []
    if "coarse_field_extraction_empty" in refine_warnings:
        bootstrap_issues.append(
            ReviewIssue(
                title="字段粗提降级提示",
                comment="粗提阶段未匹配到字段片段；已使用精提占位与规则字段继续。",
                degree="低",
                category=0,
                evidence=[],
            )
        )

    rule_issues = [*bootstrap_issues, *run_rule_review(merged_fields)]

    llm_issues: list = []
    success_count = 0
    error_count = 0
    llm_call_count = 0

    def _field_keys_from_task(task: dict) -> list[str]:
        pending_text = str(task.get("待审文本", "") or "")
        keys: list[str] = []
        for line in pending_text.splitlines():
            if not line.strip():
                continue
            if "：" in line:
                left = line.split("：", 1)[0].strip()
                if left:
                    keys.append(left)
        return list(dict.fromkeys(keys))

    def _run_one_task(task: dict) -> list:
        nonlocal llm_call_count
        try:
            task_field_keys = set(_field_keys_from_task(task))
            sub_fields = [f for f in merged_fields if f.field_key in task_field_keys]
            if not sub_fields:
                return []
            llm_call_count += 1
            res = run_llm_review_with_debug(sub_fields, payload.user_position)
            return list(res.get("issues") or [])
        except Exception as exc:
            logger.warning("review task recoverable failure: %s", type(exc).__name__)
            return degraded_llm_issues("LLM sub-task failed")

    if not review_tasks:
        llm_call_count += 1
        llm_issues = run_llm_review(merged_fields, payload.user_position)
        success_count = 1
    elif len(review_tasks) <= 1:
        llm_call_count += 1
        llm_issues = run_llm_review(merged_fields, payload.user_position)
        success_count = 1
    else:
        max_workers = _review_task_max_workers()
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_run_one_task, task) for task in review_tasks]
            for fut in concurrent.futures.as_completed(futures):
                try:
                    res = fut.result()
                    llm_issues.extend(res or [])
                    success_count += 1
                except Exception:
                    llm_issues.extend(degraded_llm_issues("Unexpected executor failure"))
                    error_count += 1

    merged_issues = merge_issues(rule_issues or [], llm_issues or [])
    good_for_final, degraded_for_agg = partition_issues_for_final_output(merged_issues)
    final_output = build_final_output(merged_fields, good_for_final)

    elapsed_ms = int((time.time() - start) * 1000)
    degraded_count = sum(1 for i in merged_issues if i.title == DEGRADED_ISSUE_TITLE)

    summary = build_summary(
        merged_fields,
        merged_issues,
        elapsed_ms,
        review_task_count=len(review_tasks),
        rules_loaded_count=len(review_rules),
    )
    summary["trace_id"] = trace_id
    summary["success_count"] = success_count
    summary["error_count"] = error_count
    summary["llm_call_count"] = llm_call_count
    summary["degraded_count"] = degraded_count
    summary["chunk_count"] = chunk_count
    summary["attachment_count"] = st["attachment_count"]
    summary["input_parse_mode"] = st["input_parse_mode"]
    summary["markdown_line_count"] = st["markdown_line_count"]
    summary["coarse_field_count"] = len(coarse)
    summary["refined_field_count"] = len(merged_fields)
    summary["input_warnings"] = [*gather_warnings, *refine_warnings]
    summary["review_max_workers"] = _review_task_max_workers()
    summary["aggregation_success_count"] = len(good_for_final)
    summary["aggregation_error_count"] = len(degraded_for_agg)
    summary["error_collection"] = issues_for_error_collection(degraded_for_agg)
    summary["pending_object_field_library"] = st.get("pending_object_field_library") or []
    summary["source_library_meta"] = _source_library_meta(st.get("source_library") or [])
    fet = st.get("field_extraction_tasks") or {"mode_1": [], "mode_23": []}
    summary["field_extraction_task_counts"] = {
        "mode_1": len(fet.get("mode_1") or []),
        "mode_23": len(fet.get("mode_23") or []),
    }
    summary["source_slot_lens"] = {
        "src1_contract_subject": len(str(payload.contract_subject or "").strip()),
        "src4_business_slot": len(payload.resolved_src4_business_slot()),
    }
    if _should_include_field_extraction_tasks(payload):
        raw_tasks = st.get("field_extraction_tasks") or {"mode_1": [], "mode_23": []}
        summary["field_extraction_tasks"] = enrich_field_extraction_tasks_with_sources(
            raw_tasks,
            st.get("source_library") or [],
        )

    logger.info(
        "pipeline done trace_id=%s review_id=%s elapsed_ms=%s issues=%s comments=%s extracted=%s llm_calls=%s degraded=%s",
        trace_id,
        review_id,
        elapsed_ms,
        len(merged_issues),
        len(final_output.comment_list),
        len(final_output.extracted_info),
        llm_call_count,
        degraded_count,
    )

    markdown = render_markdown(
        merged_fields,
        merged_issues,
        review_id,
        final_comment_count=len(final_output.comment_list),
        extracted_info_count=len(final_output.extracted_info),
        trace_id=trace_id,
        elapsed_ms=elapsed_ms,
        error_collection=summary.get("error_collection") or [],
        review_task_count=len(review_tasks),
        chunk_count=chunk_count,
    )

    return ReviewResponse(
        review_id=request_meta.review_id,
        status="completed",
        summary=summary,
        fields=[
            FieldOutput(
                field_key=item.field_key,
                value=item.value,
                confidence=item.confidence,
                evidence_paragraphs=item.evidence_paragraphs,
            )
            for item in merged_fields
        ],
        issues=[
            IssueOutput(
                title=item.title,
                comment=item.comment,
                degree=item.degree,
                category=item.category,
                change_type=item.change_type,
                revised_text=item.revised_text,
                evidence=item.evidence,
            )
            for item in merged_issues
        ],
        markdown_report=markdown,
        final_output=final_output,
    )


def run_review_dry_run(payload: ReviewCreateRequest) -> ReviewDryRunResponse:
    ensure_request_valid(payload)
    review_id = str(uuid.uuid4())
    trace_id = _trace_id_for(payload)

    st = _prepare_contract_state(payload, review_id, trace_id)
    merged_fields: list = st["merged_fields"]
    coarse: list = st["coarse"]
    review_rules: list = st["review_rules"]
    gather_warnings: list = st["gather_warnings"]
    refine_warnings: list = st["refine_warnings"]

    review_tasks = build_review_tasks(merged_fields, review_rules, limit=7000)
    review_tasks = chunk_tasks(review_tasks, limit=8000)

    dry_summary: dict = {
        "trace_id": trace_id,
        "field_count": len(merged_fields),
        "rules_loaded_count": len(review_rules),
        "review_task_count": len(review_tasks),
        "chunk_count": len(review_tasks),
        "coarse_field_count": len(coarse),
        "refined_field_count": len(merged_fields),
        "input_parse_mode": st["input_parse_mode"],
        "markdown_line_count": st["markdown_line_count"],
        "attachment_count": st["attachment_count"],
        "input_warnings": [*gather_warnings, *refine_warnings],
        "llm_call_count": 0,
        "success_count": 0,
        "error_count": 0,
        "degraded_count": 0,
        "review_max_workers": _review_task_max_workers(),
    }
    if st["input_parse_mode"] == "markdown_lines":
        dry_summary["markdown_line_records"] = [
            {"pid": r.pid, "category": r.category, "text_len": len(r.text)}
            for r in parse_markdown_lines(str(st.get("base_text") or ""))
        ][:40]

    dry_summary["pending_object_field_library"] = st.get("pending_object_field_library") or []
    dry_summary["source_library"] = st.get("source_library") or []
    dry_summary["source_library_meta"] = _source_library_meta(st.get("source_library") or [])
    raw_tasks = st.get("field_extraction_tasks") or {"mode_1": [], "mode_23": []}
    dry_summary["field_extraction_tasks"] = enrich_field_extraction_tasks_with_sources(
        raw_tasks,
        st.get("source_library") or [],
    )
    fet = dry_summary["field_extraction_tasks"]
    dry_summary["field_extraction_task_counts"] = {
        "mode_1": len(fet.get("mode_1") or []),
        "mode_23": len(fet.get("mode_23") or []),
    }
    dry_summary["source_slot_lens"] = {
        "src1_contract_subject": len(str(payload.contract_subject or "").strip()),
        "src4_business_slot": len(payload.resolved_src4_business_slot()),
    }

    return ReviewDryRunResponse(
        summary=dry_summary,
        review_tasks=review_tasks,
    )
