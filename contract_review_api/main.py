from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv

# Ensure environment variables (including SSL_CERT_FILE) are available early.
load_dotenv()

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from starlette.middleware.cors import CORSMiddleware

from contract_review_api.api.schemas import ReviewCreateRequest, ReviewDryRunResponse, ReviewResponse
from contract_review_api.core.pipeline import run_review_dry_run, run_review_pipeline
from contract_review_api.services.document_provider import DocumentProviderConfigError
from contract_review_api.services.input_ingest import InputIngestError
from contract_review_api.services.ruleset_loader import RulesetLoadError, list_available_ruleset_ids
from contract_review_api.storage.repository import ReviewRepository

app = FastAPI(title="Contract Review API", version="0.1.0")
repo = ReviewRepository()
logger = logging.getLogger(__name__)


def _cors_allow_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS")
    if raw is None:
        return ["http://localhost:5173", "http://127.0.0.1:5173"]
    return [o.strip() for o in raw.split(",") if o.strip()]


_allow = _cors_allow_origins()
if _allow:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allow,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _parse_ruleset_ids_field(raw: str | None) -> list[str]:
    s = (raw or "").strip()
    if not s:
        return []
    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        return [p.strip() for p in re.split(r"[\s,]+", s) if p.strip()]
    if isinstance(data, list):
        return [str(x).strip() for x in data if str(x).strip()]
    if isinstance(data, str) and data.strip():
        return [data.strip()]
    return []


def _safe_upload_basename(name: str | None, fallback: str) -> str:
    base = Path(name or "").name
    if not base or base in {".", ".."}:
        base = fallback
    base = re.sub(r"[^\w.\-]", "_", base)
    return base or fallback


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/rulesets")
def list_rulesets() -> dict:
    return {"ruleset_ids": list_available_ruleset_ids()}


@app.post("/reviews/upload", response_model=ReviewResponse, response_model_exclude_none=True)
async def create_review_upload(
    main_file: UploadFile | None = File(None),
    attachments: Annotated[list[UploadFile], File()] = [],
    text: str | None = Form(None),
    ruleset_ids: str = Form("[]"),
    user_position: str | None = Form(None),
    contract_type: str | None = Form(None),
    trace_id: str | None = Form(None),
    main_contract_id: str | None = Form(None),
    contract_id: str | None = Form(None),
    file_id: str | None = Form(None),
    contract_subject: str | None = Form(None),
    business_info: str | None = Form(None),
    enterprise_list: str | None = Form(None),
    include_field_extraction_tasks: bool | None = Form(
        None,
        description="If true, summary includes field_extraction_tasks (§5.1) like dry-run; null uses env default",
    ),
) -> ReviewResponse:
    """
    Browser-friendly multipart ingest: main file and/or pasted text and/or remote main id.
    Files are written to a temporary directory for the duration of the request.
    """
    rules = _parse_ruleset_ids_field(ruleset_ids)

    def _nz(v: str | None) -> str | None:
        s = (v or "").strip()
        return s or None

    cid = _nz(contract_id)
    mid = _nz(main_contract_id)
    fid = _nz(file_id)
    has_text = bool(text and text.strip())
    has_main_file = main_file is not None and bool((main_file.filename or "").strip())
    has_remote_main = bool(cid or mid or fid)

    if not (has_text or has_main_file or has_remote_main):
        raise HTTPException(
            status_code=400,
            detail="Provide main contract file, non-empty text, or a main document id.",
        )

    try:
        with tempfile.TemporaryDirectory(prefix="contract_review_upload_") as td:
            tdir = Path(td)
            file_path: str | None = None
            attachment_paths: list[str] = []

            if has_main_file and main_file is not None:
                body = await main_file.read()
                dest = tdir / _safe_upload_basename(main_file.filename, "main_contract")
                dest.write_bytes(body)
                file_path = str(dest)

            for i, up in enumerate(attachments or []):
                if not up or not (up.filename or "").strip():
                    continue
                body = await up.read()
                dest = tdir / f"att_{i}_{_safe_upload_basename(up.filename, f'attachment{i}')}"
                dest.write_bytes(body)
                attachment_paths.append(str(dest))

            payload = ReviewCreateRequest(
                text=text,
                file_path=file_path,
                attachment_paths=attachment_paths,
                ruleset_ids=rules,
                user_position=user_position,
                contract_type=contract_type,
                trace_id=trace_id,
                contract_id=cid,
                main_contract_id=mid,
                file_id=fid,
                contract_subject=contract_subject,
                business_info=business_info,
                enterprise_list=enterprise_list,
                include_field_extraction_tasks=include_field_extraction_tasks,
            )
            result = run_review_pipeline(payload)
    except InputIngestError as exc:
        logger.warning("review upload validation failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DocumentProviderConfigError as exc:
        logger.warning("document provider configuration invalid: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RulesetLoadError as exc:
        logger.warning("review ruleset validation failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("review pipeline runtime error")
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    repo.save(result.review_id, result.model_dump())
    logger.info("review completed (upload): %s", result.review_id)
    return result


@app.post("/reviews", response_model=ReviewResponse, response_model_exclude_none=True)
def create_review(payload: ReviewCreateRequest) -> ReviewResponse:
    try:
        result = run_review_pipeline(payload)
    except InputIngestError as exc:
        logger.warning("review request validation failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DocumentProviderConfigError as exc:
        logger.warning("document provider configuration invalid: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RulesetLoadError as exc:
        logger.warning("review ruleset validation failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("review pipeline runtime error")
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    repo.save(result.review_id, result.model_dump())
    logger.info("review completed: %s", result.review_id)
    return result


@app.post("/reviews/dry-run", response_model=ReviewDryRunResponse)
def create_review_dry_run(payload: ReviewCreateRequest) -> ReviewDryRunResponse:
    try:
        result = run_review_dry_run(payload)
    except InputIngestError as exc:
        logger.warning("review dry-run validation failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DocumentProviderConfigError as exc:
        logger.warning("document provider configuration invalid: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RulesetLoadError as exc:
        logger.warning("review dry-run ruleset validation failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("review dry-run runtime error")
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result


@app.get("/reviews/{review_id}", response_model=ReviewResponse, response_model_exclude_none=True)
def get_review(review_id: str) -> ReviewResponse:
    item = repo.get(review_id)
    if not item:
        raise HTTPException(status_code=404, detail="review not found")
    return ReviewResponse(**item)
