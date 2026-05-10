from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.db.models import Base, Lead, Response, Source
from leads_bot.db.session import ensure_bot_state
from leads_bot.notifier.edit_flow import (
    cancel_edit,
    confirm_edit,
    receive_edit_text,
    start_edit,
)
from leads_bot.notifier.states import EditStates


@pytest.fixture
async def factory(monkeypatch):
    for k, v in [
        ("TELEGRAM_API_ID", "1"), ("TELEGRAM_API_HASH", "x"),
        ("TELEGRAM_PHONE", "+1"), ("BOT_TOKEN", "x"),
        ("OWNER_TG_ID", "1"), ("ANTHROPIC_API_KEY", "x"),
    ]:
        monkeypatch.setenv(k, v)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    f = async_sessionmaker(engine, expire_on_commit=False)
    await ensure_bot_state(f)
    yield f
    await engine.dispose()


def _state(user_id=1, chat_id=1):
    storage = MemoryStorage()
    key = StorageKey(bot_id=42, user_id=user_id, chat_id=chat_id)
    return FSMContext(storage=storage, key=key)


async def _make_response(factory):
    async with factory() as s:
        src = Source(tg_id=-100, title="x", type="channel",
                     language="ru", region="ua", status="active")
        s.add(src); await s.commit()
        lead = Lead(source_id=src.id, tg_message_id=1,
                    raw_text="hi", status="drafted")
        s.add(lead); await s.commit()
        resp = Response(lead_id=lead.id, draft_text="original draft",
                        status="drafted", sent_to="dm")
        s.add(resp); await s.commit()
        return resp.id


async def test_start_edit_sets_state_and_prompts(factory):
    resp_id = await _make_response(factory)
    state = _state()
    callback = MagicMock()
    callback.data = f"edit:{resp_id}"
    callback.answer = AsyncMock()
    callback.message = MagicMock()
    callback.message.answer = AsyncMock()

    await start_edit(callback, state)

    cur = await state.get_state()
    assert cur == EditStates.awaiting_text.state
    data = await state.get_data()
    assert data["response_id"] == resp_id
    callback.message.answer.assert_awaited_once()
    msg = callback.message.answer.call_args.args[0]
    assert "новую версию" in msg.lower()


async def test_receive_edit_text_shows_confirm(factory):
    resp_id = await _make_response(factory)
    state = _state()
    await state.set_state(EditStates.awaiting_text)
    await state.update_data(response_id=resp_id)

    msg = MagicMock()
    msg.text = "edited reply with more detail"
    msg.answer = AsyncMock()

    await receive_edit_text(msg, state)

    cur = await state.get_state()
    assert cur == EditStates.confirming.state
    data = await state.get_data()
    assert data["edited_text"] == "edited reply with more detail"
    msg.answer.assert_awaited_once()
    call = msg.answer.call_args
    keyboard = call.kwargs["reply_markup"]
    flat = [b for row in keyboard.inline_keyboard for b in row]
    cbs = [b.callback_data for b in flat]
    assert any(c == f"confirm_edit:{resp_id}" for c in cbs)
    assert any(c == f"cancel_edit:{resp_id}" for c in cbs)


async def test_confirm_edit_persists_and_sends(factory):
    resp_id = await _make_response(factory)
    state = _state()
    await state.set_state(EditStates.confirming)
    await state.update_data(response_id=resp_id, edited_text="final edited text")

    callback = MagicMock()
    callback.data = f"confirm_edit:{resp_id}"
    callback.answer = AsyncMock()
    callback.message = MagicMock()
    callback.message.delete = AsyncMock()

    sender = MagicMock()
    sender.send = AsyncMock()

    await confirm_edit(callback, state, factory, sender)

    async with factory() as s:
        r = (await s.execute(select(Response).where(Response.id == resp_id))).scalar_one()
        assert r.final_text == "final edited text"
        assert r.status == "approved"

    sender.send.assert_awaited_once()
    cur = await state.get_state()
    assert cur is None


async def test_cancel_edit_clears_state_no_send(factory):
    resp_id = await _make_response(factory)
    state = _state()
    await state.set_state(EditStates.confirming)
    await state.update_data(response_id=resp_id, edited_text="abandoned")

    callback = MagicMock()
    callback.data = f"cancel_edit:{resp_id}"
    callback.answer = AsyncMock()
    callback.message = MagicMock()
    callback.message.delete = AsyncMock()

    sender = MagicMock()
    sender.send = AsyncMock()

    await cancel_edit(callback, state, factory, sender)

    sender.send.assert_not_awaited()
    cur = await state.get_state()
    assert cur is None
    async with factory() as s:
        r = (await s.execute(select(Response).where(Response.id == resp_id))).scalar_one()
        assert r.final_text is None
        assert r.status == "drafted"


async def test_receive_edit_text_ignored_when_no_state(factory):
    resp_id = await _make_response(factory)
    state = _state()
    msg = MagicMock(); msg.text = "hi"; msg.answer = AsyncMock()
    cur = await state.get_state()
    assert cur is None
