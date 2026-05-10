"""Winner-detection heuristic for A/B template comparison.

Rules:
1. Only consider active templates.
2. Each candidate must have sent_count >= MIN_SAMPLES (default 30).
3. The leading variant's conversion rate must be at least WIN_MULTIPLIER (1.5×)
   the next-best variant's rate.
4. A leader with replies > 0 vs. a runner-up with rate=0 wins automatically.
"""
from typing import Sequence

from leads_bot.db.models import Template

MIN_SAMPLES = 30
WIN_MULTIPLIER = 1.5


def _rate(t: Template) -> float:
    if t.sent_count <= 0:
        return 0.0
    return t.reply_count / t.sent_count


def find_winner(templates: Sequence[Template]) -> Template | None:
    """Return the winning Template, or None if no clear winner."""
    eligible = [t for t in templates if t.active and t.sent_count >= MIN_SAMPLES]
    if len(eligible) < 2:
        return None

    ranked = sorted(eligible, key=_rate, reverse=True)
    leader, runner_up = ranked[0], ranked[1]
    leader_rate = _rate(leader)
    runner_rate = _rate(runner_up)

    if leader_rate <= 0:
        return None

    if runner_rate == 0.0:
        return leader

    if leader_rate / runner_rate >= WIN_MULTIPLIER:
        return leader
    return None
