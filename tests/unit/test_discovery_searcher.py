from unittest.mock import AsyncMock, MagicMock

import pytest
from telethon.errors.rpcerrorlist import FloodWaitError

from leads_bot.discovery.searcher import DiscoverySearcher


def _channel(id, title, participants=1000, about=""):
    c = MagicMock()
    c.id = id
    c.title = title
    c.participants_count = participants
    c.megagroup = False
    c.broadcast = True
    c.about = about
    return c


def _result(channels):
    r = MagicMock()
    r.chats = channels
    return r


async def test_search_returns_raw_candidates_dropping_ru():
    fake_client = AsyncMock(return_value=_result([
        _channel(101, "Design Jobs UA", 5000, "Ukraine"),
        _channel(102, "Дизайнер Москва", 3000, "Москва"),
        _channel(103, "Freelance Designers Berlin", 4000, "EU"),
    ]))

    searcher = DiscoverySearcher(fake_client, sleep_seconds=0)
    out = await searcher.search_query("designer", "eu", "en")

    titles = [c.title for c in out]
    assert "Design Jobs UA" in titles
    assert "Freelance Designers Berlin" in titles
    assert "Дизайнер Москва" not in titles


def _floodwait(seconds):
    err = FloodWaitError(request=None)
    err.seconds = seconds
    return err


async def test_floodwait_is_respected_and_propagated():
    fake_client = AsyncMock(side_effect=_floodwait(2))

    searcher = DiscoverySearcher(fake_client, sleep_seconds=0)
    with pytest.raises(FloodWaitError):
        await searcher.search_query("designer", "eu", "en")


async def test_run_all_iterates_queries_and_sleeps_between(monkeypatch):
    fake_client = AsyncMock(return_value=_result([_channel(1, "X")]))

    sleeps = []

    async def fake_sleep(s):
        sleeps.append(s)

    monkeypatch.setattr("leads_bot.discovery.searcher.asyncio.sleep", fake_sleep)

    searcher = DiscoverySearcher(fake_client, sleep_seconds=2)
    queries = [("a", "ua", "uk"), ("b", "eu", "en"), ("c", "en_global", "en")]
    out = await searcher.run_all(queries)

    assert len(out) == 3
    assert sleeps == [2, 2]
