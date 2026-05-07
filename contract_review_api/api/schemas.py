from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ReviewCreateRequest(BaseModel):
    text: Optional[str] = Field(default=None, description="Raw contract text")
    file_path: Optional[str] = Field(default=None, description="Local file path (main contract file)")
    attachment_paths: List[str] = Field(default_factory=list, description="Local attachment paths")
    ruleset_ids: List[str] = Field(default_factory=list)
    user_position: Optional[str] = None
    contract_type: Optional[str] = Field(
        default=None,
        description="Optional contract type from caller; when set, overrides merged contract_type field",
    )
    trace_id: Optional[str] = Field(default=None, description="Optional trace id for logs / summary")

    # Dify workflow §2.2: optional slots for 构建字段取值来源库 (src_1 / src_4)
    contract_subject: Optional[str] = Field(
        default=None,
        description="Optional text for source slot src=1 (合同主体等)，与主合同正文分离",
    )
    business_info: Optional[str] = Field(
        default=None,
        description="Optional text for source slot src=4 (工商信息等)",
    )
    enterprise_list: Optional[str] = Field(
        default=None,
        description="Optional JSON string or plain text (企业列表等)，与 business_info 一并写入 src=4",
    )

    # Dify-style remote ids (resolved via DocumentProvider; default stub in dev/tests)
    contract_id: Optional[str] = None
    main_contract_id: Optional[str] = None
    file_id: Optional[str] = None
    attachment_ids: List[str] = Field(default_factory=list)
    file_ids: List[str] = Field(default_factory=list)
    files: Optional[List[str]] = Field(default=None, description="Alias list for attachment document ids")

    def resolved_main_document_id(self) -> Optional[str]:
        for key in (self.contract_id, self.main_contract_id, self.file_id):
            if key and str(key).strip():
                return str(key).strip()
        return None

    def resolved_attachment_document_ids(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        chunks: list[str] = list(self.attachment_ids) + list(self.file_ids)
        if self.files:
            chunks.extend(str(x) for x in self.files if x)
        for item in chunks:
            t = str(item or "").strip()
            if not t or t in seen:
                continue
            seen.add(t)
            out.append(t)
        return out

    def resolved_src4_business_slot(self) -> str:
        """Merge business_info + enterprise_list for source_library src=4."""
        parts: list[str] = []
        b = str(self.business_info or "").strip()
        if b:
            parts.append(b)
        e = str(self.enterprise_list or "").strip()
        if e:
            parts.append(e)
        return "\n\n".join(parts)


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
