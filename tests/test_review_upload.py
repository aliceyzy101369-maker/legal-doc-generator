"""Multipart /reviews/upload — no real LLM network when LLM_MODE=stub."""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_review_api.main import app

client = TestClient(app)


def _minimal_docx_bytes() -> bytes:
    """Tiny valid .docx (OOXML) with one paragraph."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""",
        )
        zf.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="r1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
    Target="word/document.xml"/>
</Relationships>""",
        )
        zf.writestr(
            "word/document.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>甲方：北京甲公司</w:t></w:r></w:p>
    <w:p><w:r><w:t>乙方：上海乙公司</w:t></w:r></w:p>
    <w:p><w:r><w:t>项目名称：上传测试</w:t></w:r></w:p>
    <w:p><w:r><w:t>合同类型：买卖合同</w:t></w:r></w:p>
    <w:p><w:r><w:t>自2026年1月1日至2026年12月31日</w:t></w:r></w:p>
  </w:body>
</w:document>""",
        )
    return buf.getvalue()


def test_review_upload_main_docx() -> None:
    docx = _minimal_docx_bytes()
    files = {"main_file": ("contract.docx", docx, "application/octet-stream")}
    data = {"ruleset_ids": '["demo"]'}
    resp = client.post("/reviews/upload", files=files, data=data)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "completed"
    assert body["final_output"]["comment_list"]


def test_review_upload_requires_source() -> None:
    resp = client.post("/reviews/upload", data={"ruleset_ids": '["demo"]'})
    assert resp.status_code == 400
