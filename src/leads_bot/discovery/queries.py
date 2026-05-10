"""Hardcoded geo-targeted search queries for weekly channel discovery.

Each query produces up to ~10 candidates from Telethon's contacts.SearchRequest.
Tuples (query_string, predicted_region, predicted_language).
"""
from typing import Iterable

DISCOVERY_QUERIES: list[tuple[str, str, str]] = [
    # Ukraine
    ("дизайнер вакансії", "ua", "uk"),
    ("UI/UX вакансії", "ua", "uk"),
    ("шукаю дизайнера", "ua", "uk"),
    ("веб-дизайн робота Україна", "ua", "uk"),

    # CIS ex RU (Kazakhstan, Georgia, Armenia)
    ("дизайнер Казахстан", "cis_ex_ru", "ru"),
    ("дизайнер Алматы", "cis_ex_ru", "ru"),
    ("дизайнер Тбилиси", "cis_ex_ru", "ru"),
    ("дизайнер Ереван", "cis_ex_ru", "ru"),

    # EU
    ("freelance designer Berlin", "eu", "en"),
    ("UI designer Europe", "eu", "en"),
    ("UX designer remote EU", "eu", "en"),
    ("design jobs Lisbon", "eu", "en"),

    # EN global
    ("freelance UI designer", "en_global", "en"),
    ("hire web designer", "en_global", "en"),
    ("designer wanted SaaS", "en_global", "en"),
]


def all_queries() -> Iterable[tuple[str, str, str]]:
    return list(DISCOVERY_QUERIES)
