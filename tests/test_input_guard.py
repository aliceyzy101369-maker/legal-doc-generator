import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_review_api.api.schemas import ReviewCreateRequest
from contract_review_api.services.input_ingest import InputIngestError, check_contract_input_size


def test_check_contract_input_size_rejects_over_limit(monkeypatch):
    monkeypatch.setattr("contract_review_api.services.input_ingest.MAX_CONTRACT_INPUT_CHARS", 5)
    payload = ReviewCreateRequest(text="123456", ruleset_ids=[])
    with pytest.raises(InputIngestError):
        check_contract_input_size(payload, [])
