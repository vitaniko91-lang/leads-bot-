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


@pytest.fixture(autouse=True)
def _patch_get_peer_id(monkeypatch):
    """Stub Telethon's get_peer_id (it rejects MagicMock entities) with a
    faithful channel-marking: bare id N -> marked -100N. Mirrors what the
    real impl returns for a Channel entity."""
    monkeypatch.setattr(
        "leads_bot.discovery.searcher.get_peer_id",
        lambda chat: int(f"-100{chat.id}"),
    )


async def test_candidates_use_marked_peer_id_not_bare_chat_id():
    """Regression: discovery must persist the Telethon *marked* id (-100...)
    via get_peer_id, never the bare chat.id. A bare positive id can never
    equal event.chat_id in the listener, so it yields a silently-dead source.
    See the 2026-05-27 source-table cleanup."""
    fake_client = AsyncMock(return_value=_result([
        _channel(1444340242, "Design Jobs UA", 5000, "Ukraine"),
    ]))

    searcher = DiscoverySearcher(fake_client, sleep_seconds=0)
    out = await searcher.search_query("designer", "ua", "uk")

    assert len(out) == 1
    assert out[0].tg_id == -1001444340242, (
        "searcher must route chat through get_peer_id (marked id), "
        "not store the bare chat.id"
    )


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
