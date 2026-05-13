from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import List, Optional


@dataclass
class ReviewRequest:
    review_id: str
    input_type: str
    source: str
    ruleset_ids: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class Paragraph:
    review_id: str
    doc_type: str
    paragraph_no: int
    text: str


@dataclass
class FieldCandidate:
    field_key: str
    value: str
    confidence: float
    evidence_paragraphs: List[int] = field(default_factory=list)


@dataclass
class ReviewIssue:
    title: str
    comment: str
    degree: str
    category: int
    change_type: Optional[str] = None
    revised_text: Optional[str] = None
    evidence: List[int] = field(default_factory=list)
    # error_collection / infrastructure: llm_subtask | document_fetch | field_refine
    error_source: Optional[str] = None


@dataclass
class ReviewReport:
    review_id: str
    fields: dict
    issues: List[ReviewIssue]
    summary: dict
    status: str
    elapsed_ms: int
