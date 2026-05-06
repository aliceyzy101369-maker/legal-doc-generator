from __future__ import annotations

from typing import Dict, List

from contract_review_api.core.models import FieldCandidate


def build_review_tasks(fields: List[FieldCandidate], rules: List[dict], limit: int = 7000) -> List[dict]:
    field_map: Dict[str, str] = {f.field_key: f.value for f in fields}
    prepared_rules = _prepare_rules(rules, field_map)
    clusters = _cluster_rules(prepared_rules, limit=max(1, int(limit)))
    return [_cluster_to_task(cluster) for cluster in clusters if cluster]


def _prepare_rules(rules: List[dict], field_map: Dict[str, str]) -> List[dict]:
    prepared_rules: List[dict] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        copied = dict(rule)
        target_fields = []
        for tf in rule.get("target_fields", []):
            if not isinstance(tf, dict):
                continue
            tf_copy = dict(tf)
            name = str(tf_copy.get("name", "")).strip()
            content = field_map.get(name, "")
            if tf_copy.get("src") == 0 or tf_copy.get("mode") == 0:
                content = str(tf_copy.get("desc", ""))
            tf_copy["content"] = content
            target_fields.append(tf_copy)
        copied["target_fields"] = target_fields

        if copied.get("empty_policy") == 1:
            if all(not str(tf.get("content", "")).strip() for tf in target_fields):
                continue
        prepared_rules.append(copied)
    return prepared_rules


def _rule_length(rule: dict) -> int:
    total = len(str(rule.get("title", ""))) + len(str(rule.get("instruction", "")))
    for tf in rule.get("target_fields", []):
        total += len(str(tf.get("name", ""))) + len(str(tf.get("desc", ""))) + len(str(tf.get("content", "")))
    return total


def _cluster_rules(prepared_rules: List[dict], limit: int) -> List[List[dict]]:
    anchor_names = set()
    for rule in prepared_rules:
        for tf in rule.get("target_fields", []):
            if tf.get("src") == 0:
                name = str(tf.get("name", "")).strip()
                if name:
                    anchor_names.add(name)

    grouped_by_anchor = {name: [] for name in anchor_names}
    ungrouped_rules: List[dict] = []

    for rule in prepared_rules:
        title = str(rule.get("title", "")).strip()
        if title in grouped_by_anchor:
            grouped_by_anchor[title].append(rule)
        else:
            ungrouped_rules.append(rule)

    pre_groups: List[List[dict]] = [grouped_by_anchor[name] for name in anchor_names if grouped_by_anchor[name]]

    def group_length(group_rules: List[dict]) -> int:
        return sum(_rule_length(r) for r in group_rules)

    clusters: List[List[dict]] = []
    remaining_index = 0

    for pre_group in pre_groups:
        current_cluster = list(pre_group)
        current_len = group_length(pre_group)
        while remaining_index < len(ungrouped_rules):
            rule = ungrouped_rules[remaining_index]
            rl = _rule_length(rule)
            if current_cluster and current_len + rl > limit:
                break
            current_cluster.append(rule)
            current_len += rl
            remaining_index += 1
        clusters.append(current_cluster)

    tail_rules = ungrouped_rules[remaining_index:]
    current_cluster: List[dict] = []
    current_len = 0
    for rule in tail_rules:
        rl = _rule_length(rule)
        if current_cluster and current_len + rl > limit:
            clusters.append(current_cluster)
            current_cluster = [rule]
            current_len = rl
        else:
            current_cluster.append(rule)
            current_len += rl
    if current_cluster:
        clusters.append(current_cluster)

    return clusters


def _cluster_to_task(cluster: List[dict]) -> dict:
    seen_names = set()
    pending_parts: List[str] = []
    review_rules: List[dict] = []
    for rule in cluster:
        for tf in rule.get("target_fields", []):
            name = str(tf.get("name", ""))
            if name in seen_names:
                continue
            seen_names.add(name)
            pending_parts.append(f"{name}：{tf.get('content', '')}")
        review_rules.append(
            {
                "审查项标题": rule.get("title", ""),
                "审查指引": rule.get("instruction", ""),
                "输出类型": rule.get("outputs", []),
                "风险程度": rule.get("risk_level", ""),
            }
        )
    return {"待审文本": "\n\n".join(pending_parts), "审查规则": review_rules}

