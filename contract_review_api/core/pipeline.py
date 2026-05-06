from __future__ import annotations

import concurrent.futures
import time
import uuid

from contract_review_api.api.schemas import (
    FieldOutput,
    IssueOutput,
    ReviewCreateRequest,
    ReviewDryRunResponse,
    ReviewResponse,
)
from contract_review_api.core.models import ReviewRequest
from contract_review_api.services.field_extraction import extract_field_candidates
from contract_review_api.services.input_ingest import ensure_request_valid, resolve_input_sources
from contract_review_api.services.llm_engine import run_llm_review
from contract_review_api.services.output_transform import build_final_output
from contract_review_api.services.report_render import build_summary, render_markdown
from contract_review_api.services.review_task_builder import build_review_tasks
from contract_review_api.services.ruleset_loader import load_review_rules
from contract_review_api.services.result_merge import merge_fields, merge_issues
from contract_review_api.services.rule_engine import run_rule_review
from contract_review_api.services.text_processing import build_paragraphs


def run_review_pipeline(payload: ReviewCreateRequest) -> ReviewResponse:
    start = time.time()
    ensure_request_valid(payload)
    review_id = str(uuid.uuid4())

    request_meta = ReviewRequest(
        review_id=review_id,
        input_type="text" if payload.text else "file",
        source=payload.file_path or "inline_text",
        ruleset_ids=payload.ruleset_ids,
    )

    file_sources = resolve_input_sources(payload)
    paragraphs = build_paragraphs(review_id, payload.text or "", file_sources)
    if not paragraphs:
        raise RuntimeError("No readable contract content is found from input sources.")

    field_candidates = extract_field_candidates(paragraphs)
    merged_fields = merge_fields(field_candidates or [])

    review_rules = load_review_rules(payload.ruleset_ids)
    review_tasks = build_review_tasks(merged_fields, review_rules, limit=7000)

    rule_issues = run_rule_review(merged_fields)

    # Execute LLM review tasks concurrently (ignore individual failures).
    # Each "review_task" contains a subset of field content; we derive the related
    # field_keys and call the existing `run_llm_review` on that subset.
    llm_issues: list = []
    success_count = 0
    error_count = 0

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
        return list(dict.fromkeys(keys))  # preserve order + unique

    def _run_one_task(task: dict) -> list:
        task_field_keys = set(_field_keys_from_task(task))
        sub_fields = [f for f in merged_fields if f.field_key in task_field_keys]
        if not sub_fields:
            return []
        return run_llm_review(sub_fields, payload.user_position)

    if len(review_tasks) <= 1:
        llm_issues = run_llm_review(merged_fields, payload.user_position)
        success_count = 1 if llm_issues is not None else 0
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(_run_one_task, task) for task in review_tasks]
            for fut in concurrent.futures.as_completed(futures):
                try:
                    res = fut.result()
                    llm_issues.extend(res or [])
                    success_count += 1
                except Exception:
                    error_count += 1

    merged_issues = merge_issues(rule_issues or [], llm_issues or [])
    final_output = build_final_output(merged_fields, merged_issues)

    elapsed_ms = int((time.time() - start) * 1000)
    summary = build_summary(
        merged_fields,
        merged_issues,
        elapsed_ms,
        review_task_count=len(review_tasks),
        rules_loaded_count=len(review_rules),
    )
    summary["success_count"] = success_count
    summary["error_count"] = error_count
    markdown = render_markdown(merged_fields, merged_issues, review_id)

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
    file_sources = resolve_input_sources(payload)
    paragraphs = build_paragraphs(review_id, payload.text or "", file_sources)
    if not paragraphs:
        raise RuntimeError("No readable contract content is found from input sources.")

    field_candidates = extract_field_candidates(paragraphs)
    merged_fields = merge_fields(field_candidates or [])
    review_rules = load_review_rules(payload.ruleset_ids)
    review_tasks = build_review_tasks(merged_fields, review_rules, limit=7000)

    return ReviewDryRunResponse(
        summary={
            "field_count": len(merged_fields),
            "rules_loaded_count": len(review_rules),
            "review_task_count": len(review_tasks),
        },
        review_tasks=review_tasks,
    )
