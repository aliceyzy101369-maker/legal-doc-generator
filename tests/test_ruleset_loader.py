from contract_review_api.services.ruleset_loader import RulesetLoadError, load_review_rules


def test_load_review_rules_default_fallback():
    rules = load_review_rules([])
    assert isinstance(rules, list)
    assert len(rules) >= 1


def test_load_review_rules_can_read_from_ruleset_files():
    rules = load_review_rules(["base-rules"])
    titles = {r.get("title") for r in rules}
    assert {"project_name", "party_info", "effective_period"}.issubset(titles)


def test_load_review_rules_strict_contains_extra_titles():
    rules = load_review_rules(["strict-rules"])
    titles = {r.get("title") for r in rules}
    assert "contract_type" in titles
    assert "contact_address" in titles


def test_load_review_rules_unknown_id_raises():
    try:
        load_review_rules(["unknown-ruleset"])
        assert False, "expected RulesetLoadError"
    except RulesetLoadError:
        assert True
