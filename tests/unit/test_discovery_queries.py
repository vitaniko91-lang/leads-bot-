"""Discovery queries shape + intent.

Background (2026-05-30): the original 15 queries were RU/UA/CIS-heavy and
auto-discovery returned KZ/Tbilisi vacancy boards that the analyzer
correctly threw away as 100% noise. The profile is EN freelance web design
for AI/SaaS startups, so the query mix is shifted to EN with explicit
AI/SaaS/startup niche keywords.
"""
from leads_bot.discovery.queries import DISCOVERY_QUERIES, all_queries
from leads_bot.sources.service import ALLOWED_REGIONS

_ALLOWED_LANGS = {"uk", "ru", "en"}


def test_structure_well_formed():
    assert len(DISCOVERY_QUERIES) >= 10
    assert list(all_queries()) == DISCOVERY_QUERIES
    for q, region, lang in DISCOVERY_QUERIES:
        assert isinstance(q, str) and q.strip(), f"empty query: {q!r}"
        assert region in ALLOWED_REGIONS, f"bad region {region!r}"
        assert lang in _ALLOWED_LANGS, f"bad lang {lang!r}"
    assert len(set(DISCOVERY_QUERIES)) == len(DISCOVERY_QUERIES), "duplicates"


def test_majority_english():
    """Profile is EN — at least 60% of queries must be in English."""
    en = sum(1 for _, _, lang in DISCOVERY_QUERIES if lang == "en")
    ratio = en / len(DISCOVERY_QUERIES)
    assert ratio >= 0.6, f"only {en}/{len(DISCOVERY_QUERIES)} EN ({ratio:.0%})"


def test_explicit_saas_or_ai_or_startup_niche():
    """At least 3 queries explicitly target the AI/SaaS/startup niche."""
    keywords = ("saas", "ai", "startup", "founder", "indie")
    hits = sum(
        1 for q, _, _ in DISCOVERY_QUERIES
        if any(k in q.lower() for k in keywords)
    )
    assert hits >= 3, f"only {hits} queries mention SaaS/AI/startup/founder/indie"


def test_no_cis_ex_ru_vacancy_keywords():
    """Past KZ/Tbilisi/Алматы/Ереван queries produced 100% noise — banned."""
    banned = ("казахстан", "алматы", "тбилиси", "ереван")
    bad = [q for q, _, _ in DISCOVERY_QUERIES
           if any(b in q.lower() for b in banned)]
    assert not bad, f"queries hit banned CIS-ex-RU vacancy keywords: {bad}"
