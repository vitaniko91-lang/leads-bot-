from collections import Counter

import pytest

from leads_bot.db.models import Template
from leads_bot.templates.picker import NoActiveTemplatesError, pick_template


def _t(name, share, active=True):
    return Template(
        name=name, variant=name[:1].upper(), prompt=f"prompt-{name}",
        active=active, traffic_share=share,
    )


def test_single_active_template_always_picked():
    only = _t("only", 100)
    for _ in range(50):
        chosen = pick_template([only])
        assert chosen is only


def test_inactive_templates_excluded():
    a = _t("a", 100, active=True)
    b = _t("b", 0, active=False)
    for _ in range(50):
        assert pick_template([a, b]) is a


def test_distribution_matches_traffic_share_within_tolerance():
    a = _t("a", 80)
    b = _t("b", 20)
    counts = Counter()
    for _ in range(5000):
        counts[pick_template([a, b]).name] += 1
    a_pct = counts["a"] / 5000 * 100
    assert 77 <= a_pct <= 83, f"Expected ~80%, got {a_pct}"


def test_zero_share_template_never_picked():
    a = _t("a", 100)
    b = _t("b", 0, active=True)
    for _ in range(200):
        assert pick_template([a, b]) is a


def test_no_active_raises():
    a = _t("a", 100, active=False)
    with pytest.raises(NoActiveTemplatesError):
        pick_template([a])


def test_empty_list_raises():
    with pytest.raises(NoActiveTemplatesError):
        pick_template([])


def test_seeded_rng_is_reproducible():
    import random
    a = _t("a", 50)
    b = _t("b", 50)
    rng = random.Random(42)
    seq1 = [pick_template([a, b], rng=rng).name for _ in range(20)]
    rng = random.Random(42)
    seq2 = [pick_template([a, b], rng=rng).name for _ in range(20)]
    assert seq1 == seq2
