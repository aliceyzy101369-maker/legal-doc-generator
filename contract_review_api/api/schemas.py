from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ReviewCreateRequest(BaseModel):
    text: Optional[str] = Field(default=None, description="Raw contract text")
    file_path: Optional[str] = Field(default=None, description="Local file path")
    attachment_paths: List[str] = Field(default_factory=list)
    ruleset_ids: List[str] = Field(default_factory=list)
    user_position: Optional[str] = None


class FieldOutput(BaseModel):
    field_key: str
    value: str
    confidence: float
    evidence_paragraphs: List[int] = Field(default_factory=list)


class IssueOutput(BaseModel):
    title: str
    comment: str
    degree: str
    category: int
    change_type: Optional[str] = None
    revised_text: Optional[str] = None
    evidence: List[int] = Field(default_factory=list)


class FinalCommentItem(BaseModel):
    title: str
    comment: str
    degree: str
    category: int
    change_type: Optional[str] = None
    original_id: Optional[List[int]] = None
    revised_text: Optional[str] = None


class ExtractedInfoItem(BaseModel):
    title: str
    comment: str


class FinalOutput(BaseModel):
    comment_list: List[FinalCommentItem] = Field(default_factory=list)
    extracted_info: List[ExtractedInfoItem] = Field(default_factory=list)


class ReviewResponse(BaseModel):
    review_id: str
    status: str
    summary: dict
    fields: List[FieldOutput]
    issues: List[IssueOutput]
    markdown_report: str
    final_output: FinalOutput = Field(default_factory=FinalOutput)


class ReviewDryRunResponse(BaseModel):
    summary: dict
    review_tasks: List[dict] = Field(default_factory=list)
