"""Loads owner profile (name, cases, tone) for drafter context."""
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Case:
    title: str
    tags: list[str]
    description: str
    url: str


@dataclass(frozen=True)
class Profile:
    name: str
    portfolio_url: str
    telegram: str
    min_rate_usd_per_hour: int
    tone: str
    payment_methods: list[str]
    cases: list[Case]


def load_profile(path: Path) -> Profile:
    data = json.loads(Path(path).read_text())
    cases = [Case(**c) for c in data.get("cases", [])]
    return Profile(
        name=data["name"],
        portfolio_url=data["portfolio_url"],
        telegram=data["telegram"],
        min_rate_usd_per_hour=data["min_rate_usd_per_hour"],
        tone=data["tone"],
        payment_methods=data["payment_methods"],
        cases=cases,
    )


def find_relevant_cases(profile: Profile, project_type: str, limit: int = 2) -> list[Case]:
    """Find cases tagged with project_type. Falls back to first N if no match."""
    matched = [c for c in profile.cases if project_type in c.tags]
    if matched:
        return matched[:limit]
    return profile.cases[:limit]
