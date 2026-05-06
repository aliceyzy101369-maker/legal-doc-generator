"""HTTP document provider — network mocked, no real I/O."""

from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_review_api.services.document_provider import (
    DocumentNotFoundError,
    DocumentProviderConfigError,
    HttpDocumentProvider,
    get_document_provider,
)


def _mock_urlopen_response(body: bytes) -> MagicMock:
    cm = MagicMock()
    inner = MagicMock()
    inner.read.return_value = body
    cm.__enter__.return_value = inner
    cm.__exit__.return_value = False
    return cm


def test_http_provider_extracts_text_json_key() -> None:
    provider = HttpDocumentProvider(
        base_url="https://example.com",
        path_template="/api/docs/{doc_id}",
    )
    body = '{"text":"甲方：A"}'.encode("utf-8")
    with patch(
        "contract_review_api.services.document_provider.urllib.request.urlopen",
        return_value=_mock_urlopen_response(body),
    ):
        out = provider.fetch_text("doc-1")
    assert "甲方" in out


def test_http_provider_plain_body() -> None:
    provider = HttpDocumentProvider(base_url="https://x.test", path_template="/raw/{doc_id}")
    with patch(
        "contract_review_api.services.document_provider.urllib.request.urlopen",
        return_value=_mock_urlopen_response(b"hello contract"),
    ):
        assert provider.fetch_text("1") == "hello contract"


def test_http_provider_404() -> None:
    import urllib.error

    provider = HttpDocumentProvider(base_url="https://x.test", path_template="/d/{doc_id}")
    err = urllib.error.HTTPError("url", 404, "nf", hdrs=None, fp=BytesIO(b""))
    with patch(
        "contract_review_api.services.document_provider.urllib.request.urlopen",
        side_effect=err,
    ):
        with pytest.raises(DocumentNotFoundError):
            provider.fetch_text("missing")


def test_http_provider_requires_placeholder() -> None:
    with pytest.raises(DocumentProviderConfigError):
        HttpDocumentProvider(base_url="https://x.test", path_template="/bad/no/id/here")


def test_get_document_provider_http_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTRACT_DOCUMENT_PROVIDER", "http")
    monkeypatch.setenv("CONTRACT_DOCUMENT_HTTP_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("CONTRACT_DOCUMENT_HTTP_PATH_TEMPLATE", "/v1/files/{doc_id}")
    with patch(
        "contract_review_api.services.document_provider.urllib.request.urlopen",
        return_value=_mock_urlopen_response(b'{"content":"ok"}'),
    ):
        prov = get_document_provider()
        assert prov.fetch_text("abc") == "ok"
