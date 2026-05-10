from leads_bot.db.models import Template
from leads_bot.templates.winner import find_winner


def _t(name, sent, replies, traffic=50):
    return Template(
        name=name, variant=name, prompt="p", active=True,
        traffic_share=traffic, sent_count=sent, reply_count=replies,
    )


def test_winner_requires_min_30_sends_per_variant():
    a = _t("A", sent=29, replies=10)
    b = _t("B", sent=100, replies=20)
    assert find_winner([a, b]) is None


def test_winner_must_be_at_least_1_5x_runner_up_rate():
    a = _t("A", sent=100, replies=30)
    b = _t("B", sent=100, replies=25)
    assert find_winner([a, b]) is None


def test_winner_when_clearly_better():
    a = _t("A", sent=100, replies=40)
    b = _t("B", sent=100, replies=20)
    winner = find_winner([a, b])
    assert winner is a


def test_no_winner_with_only_one_template():
    a = _t("A", sent=100, replies=40)
    assert find_winner([a]) is None


def test_no_winner_when_no_replies():
    a = _t("A", sent=100, replies=0)
    b = _t("B", sent=100, replies=0)
    assert find_winner([a, b]) is None


def test_zero_runner_up_rate_doesnt_divide_by_zero():
    a = _t("A", sent=100, replies=10)
    b = _t("B", sent=100, replies=0)
    assert find_winner([a, b]) is a


def test_inactive_templates_excluded_from_consideration():
    a = _t("A", sent=100, replies=40); a.active = False
    b = _t("B", sent=100, replies=10)
    assert find_winner([a, b]) is None
