from __future__ import annotations

from dotenv import load_dotenv

# Ensure environment variables (including SSL_CERT_FILE) are available early.
load_dotenv()

import logging

from fastapi import FastAPI, HTTPException

from contract_review_api.api.schemas import ReviewCreateRequest, ReviewDryRunResponse, ReviewResponse
from contract_review_api.core.pipeline import run_review_dry_run, run_review_pipeline
from contract_review_api.services.input_ingest import InputIngestError
from contract_review_api.services.ruleset_loader import RulesetLoadError, list_available_ruleset_ids
from contract_review_api.storage.repository import ReviewRepository

app = FastAPI(title="Contract Review API", version="0.1.0")
repo = ReviewRepository()
logger = logging.getLogger(__name__)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/rulesets")
def list_rulesets() -> dict:
    return {"ruleset_ids": list_available_ruleset_ids()}


@app.post("/reviews", response_model=ReviewResponse, response_model_exclude_none=True)
def create_review(payload: ReviewCreateRequest) -> ReviewResponse:
    try:
        result = run_review_pipeline(payload)
    except InputIngestError as exc:
        logger.warning("review request validation failed: %s", exc)
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
