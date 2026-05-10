"""Cheap keyword pre-filter to reduce Claude API calls. See spec §6.1.

Heuristic: a message looks like a lead if it contains both a HIRING TRIGGER
(verb/phrase signalling someone is looking to hire) AND a ROLE WORD
(designer/UI/UX/etc.). False positives are acceptable; false negatives are
expensive (we miss real leads).
"""

# Verbs / phrases meaning "we want to hire"
HIRING_TRIGGERS = [
    # RU
    "ищу", "ищем", "нужен", "нужна", "нужно",
    "требуется", "подбираю", "подбираем",
    "вакансия", "вакансии",
    # UA
    "шукаю", "шукаємо", "потрібен", "потрібна", "потрібно",
    "вакансія",
    # EN
    "looking for", "need a", "need an", "need ",
    "hiring", "seeking", "wanted",
    "freelance",
]

# Role / specialty words
ROLE_WORDS = [
    # RU/UA
    "дизайн",
    # EN
    "designer", "ui", "ux", "figma",
]

MIN_TEXT_LENGTH = 30  # symbols


def looks_like_lead(text: str) -> bool:
    """Cheap keyword check — used before calling Claude.

    Returns True iff text has both a hiring trigger and a role word
    (case-insensitive). False positives are fine; false negatives lose money.
    """
    if not text or len(text) < MIN_TEXT_LENGTH:
        return False
    lower = text.lower()
    has_trigger = any(t in lower for t in HIRING_TRIGGERS)
    has_role = any(r in lower for r in ROLE_WORDS)
    return has_trigger and has_role
