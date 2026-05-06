from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional


class ReviewRepository:
    def __init__(self, store_path: str = "output/review_reports.jsonl") -> None:
        self._cache: Dict[str, dict] = {}
        self._path = Path(store_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, review_id: str, payload: dict) -> None:
        self._cache[review_id] = payload
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def get(self, review_id: str) -> Optional[dict]:
        if review_id in self._cache:
            return self._cache[review_id]
        if not self._path.exists():
            return None
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                item = json.loads(line)
                if item.get("review_id") == review_id:
                    self._cache[review_id] = item
                    return item
        return None
