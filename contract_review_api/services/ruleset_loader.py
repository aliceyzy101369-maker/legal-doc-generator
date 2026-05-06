from __future__ import annotations

import json
from pathlib import Path
from typing import List

from contract_review_api.services.rule_engine import build_default_review_rules


class RulesetLoadError(ValueError):
    pass


def load_review_rules(ruleset_ids: List[str]) -> List[dict]:
    """
    Load review rules by ids.
    - empty ids: fallback to base-rules
    - unknown id: raise RulesetLoadError
    """
    if not ruleset_ids:
        return build_default_review_rules()

    registry = _build_ruleset_registry()
    merged: List[dict] = []
    seen_titles = set()

    for rid in ruleset_ids:
        key = str(rid or "").strip()
        if not key:
            continue
        if key not in registry:
            raise RulesetLoadError(f"Unknown ruleset id: {key}")
        for rule in registry[key]:
            title = str(rule.get("title", "")).strip()
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)
            merged.append(rule)

    return merged or build_default_review_rules()


def list_available_ruleset_ids() -> List[str]:
    return sorted(_build_ruleset_registry().keys())


def _build_ruleset_registry() -> dict[str, List[dict]]:
    file_registry = _load_rulesets_from_files()
    base_rules = build_default_review_rules()
    strict_rules = base_rules + [
        {
            "title": "contract_type",
            "instruction": "检查合同类型是否明确且与项目上下文一致。",
            "outputs": ["risk"],
            "risk_level": "中",
            "empty_policy": 1,
            "target_fields": [{"name": "contract_type", "desc": "合同类型", "src": 1, "mode": 1}],
        },
        {
            "title": "contact_address",
            "instruction": "检查合同中是否出现明确联系地址，便于通知送达。",
            "outputs": ["risk"],
            "risk_level": "低",
            "empty_policy": 1,
            "target_fields": [{"name": "contact_address", "desc": "地址信息", "src": 1, "mode": 1}],
        },
    ]
    builtin_registry = {
        "base-rules": base_rules,
        "demo": base_rules,
        "strict-rules": strict_rules,
    }
    # External file rulesets override builtin entries with same id.
    return {**builtin_registry, **file_registry}


def _load_rulesets_from_files() -> dict[str, List[dict]]:
    ruleset_dir = Path(__file__).resolve().parents[1] / "rulesets"
    if not ruleset_dir.exists():
        return {}
    loaded: dict[str, List[dict]] = {}
    for path in ruleset_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, list):
            continue
        valid_rules = [item for item in data if isinstance(item, dict)]
        if valid_rules:
            loaded[path.stem] = valid_rules
    return loaded

