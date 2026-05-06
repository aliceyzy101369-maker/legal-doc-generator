from __future__ import annotations

import json
import logging
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Protocol

logger = logging.getLogger(__name__)


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
            "or configure http provider."
        )


def _ssl_context_for_documents() -> ssl.SSLContext:
    verify = os.environ.get("SSL_CERT_FILE", True)
    if verify is True or verify == "":
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=str(verify))


def _extract_text_from_json_payload(data: Any) -> str | None:
    """Best-effort extract contract text from typical API JSON envelopes."""
    if isinstance(data, str) and data.strip():
        return data.strip()
    if not isinstance(data, dict):
        return None
    for key in ("text", "textContent", "content", "body", "markdown", "markdownContent", "contract_content"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    for nest in ("data", "result", "payload", "document"):
        if nest in data:
            inner = _extract_text_from_json_payload(data[nest])
            if inner:
                return inner
    return None


class HttpDocumentProvider:
    """
    Generic HTTP fetcher for contract text by id.
    Does not assume a specific vendor — configure base URL + path template.
    """

    def __init__(
        self,
        *,
        base_url: str,
        path_template: str,
        timeout: float = 30.0,
        bearer_token: str | None = None,
    ) -> None:
        self._base = str(base_url or "").strip().rstrip("/")
        self._path_template = str(path_template or "").strip()
        self._timeout = float(timeout)
        self._bearer = (bearer_token or "").strip() or None
        if not self._base:
            raise DocumentProviderConfigError("CONTRACT_DOCUMENT_HTTP_BASE_URL is required for http provider.")
        if "{doc_id}" not in self._path_template and "{document_id}" not in self._path_template:
            raise DocumentProviderConfigError(
                "CONTRACT_DOCUMENT_HTTP_PATH_TEMPLATE must contain {doc_id} or {document_id} placeholder."
            )

    @classmethod
    def from_env(cls) -> HttpDocumentProvider:
        base = str(os.getenv("CONTRACT_DOCUMENT_HTTP_BASE_URL", "") or "").strip()
        path = str(
            os.getenv("CONTRACT_DOCUMENT_HTTP_PATH_TEMPLATE", "/documents/{doc_id}")
            or "/documents/{doc_id}"
        ).strip()
        timeout = float(os.getenv("CONTRACT_DOCUMENT_HTTP_TIMEOUT", "30") or "30")
        bearer = str(os.getenv("CONTRACT_DOCUMENT_HTTP_BEARER_TOKEN", "") or "").strip() or None
        return cls(base_url=base, path_template=path, timeout=timeout, bearer_token=bearer)

    def _build_url(self, doc_id: str) -> str:
        safe_id = urllib.parse.quote(str(doc_id or "").strip(), safe="")
        rel = self._path_template.format(doc_id=safe_id, document_id=safe_id)
        if rel.startswith("http://") or rel.startswith("https://"):
            return rel
        if not rel.startswith("/"):
            rel = "/" + rel
        return f"{self._base}{rel}"

    def fetch_text(self, doc_id: str) -> str:
        url = self._build_url(doc_id)
        req = urllib.request.Request(url=url, method="GET")
        if self._bearer:
            req.add_header("Authorization", f"Bearer {self._bearer}")
        req.add_header("Accept", "application/json, text/plain, */*")

        ctx = _ssl_context_for_documents()
        try:
            with urllib.request.urlopen(req, timeout=self._timeout, context=ctx) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise DocumentNotFoundError(f"document id not found (HTTP 404): {doc_id}") from exc
            logger.warning("document http error status=%s doc_id=%s", exc.code, doc_id)
            raise DocumentProviderConfigError(f"document HTTP error {exc.code} for id={doc_id}") from exc
        except urllib.error.URLError as exc:
            logger.warning("document fetch failed doc_id=%s err=%s", doc_id, type(exc.reason).__name__)
            raise DocumentProviderConfigError(f"document fetch failed: {exc.reason}") from exc

        raw_stripped = raw.strip()
        if not raw_stripped:
            return ""

        try:
            parsed = json.loads(raw_stripped)
        except json.JSONDecodeError:
            return raw_stripped

        extracted = _extract_text_from_json_payload(parsed)
        if extracted:
            return extracted
        return raw_stripped


def get_document_provider() -> DocumentProvider:
    mode = str(os.getenv("CONTRACT_DOCUMENT_PROVIDER", "stub") or "stub").strip().lower()
    if mode in ("stub", "local", "test"):
        return StubDocumentProvider()
    if mode in ("none", "off", "disabled"):
        return NullDocumentProvider()
    if mode in ("http", "https", "remote"):
        return HttpDocumentProvider.from_env()
    raise DocumentProviderConfigError(f"Unknown CONTRACT_DOCUMENT_PROVIDER mode: {mode}")
