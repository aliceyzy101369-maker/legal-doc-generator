from __future__ import annotations

import os
from typing import Protocol


class DocumentNotFoundError(ValueError):
    """Document id cannot be resolved."""


class DocumentProviderConfigError(ValueError):
    """Invalid provider configuration."""


# Built-in stub registry for tests / local dev (no external service).
DEFAULT_STUB_REGISTRY: dict[str, str] = {
    "main-contract-stub": "甲方：北京甲公司\n\n乙方：上海乙公司\n\n项目名称：stub主合同项目\n\n合同类型：服务合同\n\n自2026年1月1日至2026年12月31日",
    "att-stub-1": "附件条款：付款细节以双方补充协议为准。",
    "att-stub-2": "附件条款：交付物包含安装与培训。",
    "missing-attachment-stub": "",
}


class DocumentProvider(Protocol):
    def fetch_text(self, doc_id: str) -> str:
        """Return UTF-8 contract text; may be empty for an intentionally blank attachment."""


class StubDocumentProvider:
    def __init__(self, registry: dict[str, str] | None = None) -> None:
        self._registry = dict(registry or DEFAULT_STUB_REGISTRY)

    def fetch_text(self, doc_id: str) -> str:
        key = str(doc_id or "").strip()
        if key not in self._registry:
            raise DocumentNotFoundError(f"document id not found (stub provider): {key}")
        return str(self._registry[key] or "")


class NullDocumentProvider:
    """Explicitly disables remote id resolution (production guard)."""

    def fetch_text(self, doc_id: str) -> str:
        raise DocumentProviderConfigError(
            "Remote document ids are not configured. Set CONTRACT_DOCUMENT_PROVIDER=stub for local simulation, "
            "or implement a real provider."
        )


def get_document_provider() -> DocumentProvider:
    mode = str(os.getenv("CONTRACT_DOCUMENT_PROVIDER", "stub") or "stub").strip().lower()
    if mode in ("stub", "local", "test"):
        return StubDocumentProvider()
    if mode in ("none", "off", "disabled"):
        return NullDocumentProvider()
    raise DocumentProviderConfigError(f"Unknown CONTRACT_DOCUMENT_PROVIDER mode: {mode}")
