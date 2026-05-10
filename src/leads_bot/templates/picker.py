"""Weighted random selection over active templates."""
import random
from typing import Sequence

from leads_bot.db.models import Template


class NoActiveTemplatesError(RuntimeError):
    """Raised when no template with active=True and traffic_share>0 exists."""


def pick_template(
    templates: Sequence[Template],
    rng: random.Random | None = None,
) -> Template:
    """Pick one template weighted by traffic_share.

    - Filters to active + traffic_share > 0.
    - Uses random.choices with weights.
    - Pass `rng` for deterministic tests.
    """
    candidates = [t for t in templates if t.active and t.traffic_share > 0]
    if not candidates:
        raise NoActiveTemplatesError("No active templates with traffic_share > 0")
    weights = [t.traffic_share for t in candidates]
    r = rng or random
    return r.choices(candidates, weights=weights, k=1)[0]
