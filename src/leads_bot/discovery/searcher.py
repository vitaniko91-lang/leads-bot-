"""Wraps Telethon's contacts.SearchRequest with rate-limit safety + RU drop."""
import asyncio
from dataclasses import dataclass

from loguru import logger
from telethon.errors.rpcerrorlist import FloodWaitError
from telethon.tl.functions.contacts import SearchRequest
from telethon.utils import get_peer_id

from leads_bot.discovery.blocklist import is_ru_channel


@dataclass(frozen=True)
class RawCandidate:
    tg_id: int
    title: str
    description: str
    member_count: int
    predicted_region: str
    predicted_language: str
    matched_query: str


class DiscoverySearcher:
    def __init__(
        self, telethon_client, sleep_seconds: int = 2, limit_per_query: int = 20,
    ):
        self._client = telethon_client
        self._sleep = sleep_seconds
        self._limit = limit_per_query

    async def search_query(
        self, query: str, predicted_region: str, predicted_language: str,
    ) -> list[RawCandidate]:
        try:
            res = await self._client(SearchRequest(q=query, limit=self._limit))
        except FloodWaitError as e:
            logger.warning(f"Discovery FloodWait {e.seconds}s on '{query}'")
            raise

        out: list[RawCandidate] = []
        for chat in getattr(res, "chats", []) or []:
            title = getattr(chat, "title", "") or ""
            about = getattr(chat, "about", "") or ""
            if is_ru_channel(title, about):
                logger.debug(f"Discovery: RU-rejected '{title}'")
                continue
            members = getattr(chat, "participants_count", None) or 0
            if members <= 0:
                continue
            out.append(RawCandidate(
                # Telethon-marked id (-100...) so it matches event.chat_id in
                # the listener; bare chat.id yields a silently-dead source.
                tg_id=get_peer_id(chat),
                title=title,
                description=about,
                member_count=int(members),
                predicted_region=predicted_region,
                predicted_language=predicted_language,
                matched_query=query,
            ))
        logger.info(f"Discovery: '{query}' → {len(out)} clean candidates")
        return out

    async def run_all(
        self, queries: list[tuple[str, str, str]],
    ) -> list[RawCandidate]:
        out: list[RawCandidate] = []
        for i, (q, region, lang) in enumerate(queries):
            try:
                out.extend(await self.search_query(q, region, lang))
            except FloodWaitError as e:
                logger.warning(f"Discovery: sleeping {e.seconds}s due to FloodWait")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.exception(f"Discovery: query '{q}' failed: {e}")
            if i < len(queries) - 1:
                await asyncio.sleep(self._sleep)
        return out
