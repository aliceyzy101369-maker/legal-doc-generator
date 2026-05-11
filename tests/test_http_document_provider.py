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


def test_http_provider_json_dotted_path_nested() -> None:
    provider = HttpDocumentProvider(
        base_url="https://example.com",
        path_template="/d/{doc_id}",
        json_text_path="payload.result.markdown",
    )
    body = '{"payload":{"result":{"markdown":"甲方：nested"}}}'.encode("utf-8")
    with patch(
        "contract_review_api.services.document_provider.urllib.request.urlopen",
        return_value=_mock_urlopen_response(body),
    ):
        assert provider.fetch_text("1") == "甲方：nested"


def test_http_provider_json_path_list_index() -> None:
    provider = HttpDocumentProvider(
        base_url="https://example.com",
        path_template="/d/{doc_id}",
        json_text_path="blocks.0.text",
    )
    body = '{"blocks":[{"text":"段落一"}]}'.encode("utf-8")
    with patch(
        "contract_review_api.services.document_provider.urllib.request.urlopen",
        return_value=_mock_urlopen_response(body),
    ):
        assert provider.fetch_text("x") == "段落一"


def test_http_provider_custom_headers_on_request() -> None:
    provider = HttpDocumentProvider(
        base_url="https://x.test",
        path_template="/d/{doc_id}",
        extra_headers={"X-Tenant-Id": "t1", "X-Api-Key": "secret"},
    )
    with patch(
        "contract_review_api.services.document_provider.urllib.request.urlopen",
        return_value=_mock_urlopen_response(b"plain"),
    ) as m_urlopen:
        provider.fetch_text("1")
    req = m_urlopen.call_args[0][0]
    sent = {k.lower(): v for k, v in req.header_items()}
    assert sent.get("x-tenant-id") == "t1"
    assert sent.get("x-api-key") == "secret"
    assert "application/json" in (sent.get("accept") or "")


def test_http_provider_from_env_json_path_and_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTRACT_DOCUMENT_PROVIDER", "http")
    monkeypatch.setenv("CONTRACT_DOCUMENT_HTTP_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("CONTRACT_DOCUMENT_HTTP_PATH_TEMPLATE", "/v1/{doc_id}")
    monkeypatch.setenv("CONTRACT_DOCUMENT_HTTP_JSON_PATH", "data.body")
    monkeypatch.setenv("CONTRACT_DOCUMENT_HTTP_HEADERS", '{"X-Custom":"yes"}')
    with patch(
        "contract_review_api.services.document_provider.urllib.request.urlopen",
        return_value=_mock_urlopen_response(b'{"data":{"body":"from path"}}'),
    ) as m_urlopen:
        prov = get_document_provider()
        assert prov.fetch_text("z") == "from path"
    req = m_urlopen.call_args[0][0]
    sent = {k.lower(): v for k, v in req.header_items()}
    assert sent.get("x-custom") == "yes"


def test_http_provider_post_json_body() -> None:
    provider = HttpDocumentProvider(
        base_url="https://example.com",
        path_template="/api/docs/{doc_id}",
        http_method="POST",
        body_template='{"fileId":"{doc_id}"}',
    )
    with patch(
        "contract_review_api.services.document_provider.urllib.request.urlopen",
        return_value=_mock_urlopen_response(b'{"text":"POST ok"}'),
    ) as m_urlopen:
        out = provider.fetch_text("doc-99")
    assert out == "POST ok"
    req = m_urlopen.call_args[0][0]
    assert req.get_method() == "POST"
    assert b'"fileId":"doc-99"' in (req.data or b"")


def test_http_provider_post_default_body_json() -> None:
    provider = HttpDocumentProvider(
        base_url="https://x.test",
        path_template="/v/{doc_id}",
        http_method="POST",
    )
    with patch(
        "contract_review_api.services.document_provider.urllib.request.urlopen",
        return_value=_mock_urlopen_response(b'plain'),
    ) as m_urlopen:
        provider.fetch_text("id7")
    req = m_urlopen.call_args[0][0]
    assert req.data == b'{"doc_id": "id7"}'


def test_http_provider_post_includes_signature_when_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTRACT_DOCUMENT_HTTP_SIGN_SECRET", "s3cr3t")
    provider = HttpDocumentProvider(
        base_url="https://example.com",
        path_template="/api/{doc_id}",
        http_method="POST",
        body_template='{"id":"{doc_id}"}',
    )
    with patch(
        "contract_review_api.services.document_provider.urllib.request.urlopen",
        return_value=_mock_urlopen_response(b'{"text":"ok"}'),
    ) as m_urlopen:
        provider.fetch_text("abc")
    req = m_urlopen.call_args[0][0]
    sent = {k.lower(): v for k, v in req.header_items()}
    assert "x-document-signature" in sent
    assert len(sent["x-document-signature"]) == 64


def test_http_provider_invalid_http_method() -> None:
    with pytest.raises(DocumentProviderConfigError, match="GET or POST"):
        HttpDocumentProvider(
            base_url="https://x.test",
            path_template="/d/{doc_id}",
            http_method="PUT",
        )


def test_http_provider_invalid_headers_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTRACT_DOCUMENT_HTTP_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("CONTRACT_DOCUMENT_HTTP_HEADERS", "not-json")
    with pytest.raises(DocumentProviderConfigError):
        HttpDocumentProvider.from_env()
