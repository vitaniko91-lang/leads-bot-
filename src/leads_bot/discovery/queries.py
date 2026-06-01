"""Hardcoded geo-targeted search queries for weekly channel discovery.

Each query produces up to ~10 candidates from Telethon's contacts.SearchRequest.
Tuples (query_string, predicted_region, predicted_language).

Profile target (2026-05-30 refactor): EN freelance web design for AI/SaaS
startups. The original 15 queries were RU/UA/CIS-heavy and returned KZ/Tbilisi
vacancy boards that the analyzer threw away as 100% noise. The mix is now
EN-majority with explicit AI/SaaS/startup-niche keywords. Regression in
tests/unit/test_discovery_queries.py guards the structure and intent.
"""
from typing import Iterable

DISCOVERY_QUERIES: list[tuple[str, str, str]] = [
    # EN core — AI/SaaS startup briefs
    ("looking for designer SaaS startup", "en_global", "en"),
    ("hire web designer AI startup", "en_global", "en"),
    ("freelance landing page designer", "en_global", "en"),
    ("need designer for startup", "en_global", "en"),
    ("startup design brief", "en_global", "en"),
    ("AI SaaS landing page", "en_global", "en"),
    ("indie hackers designer", "en_global", "en"),
    ("SaaS founders community", "en_global", "en"),
    ("startup founder Telegram", "en_global", "en"),
    ("UX UI designer freelance project", "en_global", "en"),

    # EU EN — geo-adjacent EN clients (Berlin/EU/Lisbon hubs)
    ("startup designer Berlin", "eu", "en"),
    ("freelance designer Europe", "eu", "en"),
    ("design project Lisbon", "eu", "en"),

    # Ukraine — minimal exposure (one EN, one UK)
    ("Ukraine startup designer", "ua", "en"),
    ("дизайнер стартап Україна", "ua", "uk"),
]


def all_queries() -> Iterable[tuple[str, str, str]]:
    return list(DISCOVERY_QUERIES)
