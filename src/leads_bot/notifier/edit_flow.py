"""Edit-response state machine. See spec §6.4 + iter2 brief.

Flow:
  ✏️ tap   → start_edit       (sets EditStates.awaiting_text)
  text msg → receive_edit_text (sets EditStates.confirming, shows preview)
  ✅ tap   → confirm_edit      (writes final_text, calls sender)
  ↩ tap   → cancel_edit        (clears state)
"""
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from leads_bot.db.models import Response
from leads_bot.notifier.states import EditStates


def _confirm_keyboard(response_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Send this version",
                callback_data=f"confirm_edit:{response_id}",
            ),
            InlineKeyboardButton(
                text="↩ Back to draft",
                callback_data=f"cancel_edit:{response_id}",
            ),
        ],
    ])


async def start_edit(callback, state: FSMContext) -> None:
    """Triggered by callback 'edit:<resp_id>'."""
    try:
        _, rid_s = (callback.data or "").split(":", 1)
        response_id = int(rid_s)
    except ValueError:
        await callback.answer("Bad callback")
        return

    await state.set_state(EditStates.awaiting_text)
    await state.update_data(response_id=response_id)
    await callback.answer()
    await callback.message.answer(
        "✏️ Пришли новую версию ответа одним сообщением.\n"
        "Чтобы отменить — /cancel"
    )


async def receive_edit_text(message, state: FSMContext) -> None:
    """Triggered when owner sends a text while EditStates.awaiting_text."""
    text = (message.text or "").strip()
    if not text:
        await message.answer("Пустое сообщение. Пришли текст или /cancel.")
        return
    if text == "/cancel":
        await state.clear()
        await message.answer("Отменено. Карточка с драфтом всё ещё выше.")
        return

    await state.update_data(edited_text=text)
    await state.set_state(EditStates.confirming)
    data = await state.get_data()
    response_id = int(data["response_id"])

    preview = (
        f"▎НОВАЯ ВЕРСИЯ\n{text}\n\n"
        "Отправить эту версию?"
    )
    await message.answer(preview, reply_markup=_confirm_keyboard(response_id))


async def confirm_edit(
    callback, state: FSMContext,
    factory: async_sessionmaker, sender,
) -> None:
    """Triggered by callback 'confirm_edit:<resp_id>'."""
    data = await state.get_data()
    edited_text = data.get("edited_text")
    response_id = data.get("response_id")
    if not edited_text or not response_id:
        await callback.answer("Состояние утеряно. Нажми ✏️ заново.", show_alert=True)
        await state.clear()
        return

    async with factory() as session:
        resp = (await session.execute(
            select(Response).where(Response.id == int(response_id))
        )).scalar_one_or_none()
        if resp is None:
            await callback.answer("Response not found", show_alert=True)
            await state.clear()
            return
        resp.final_text = edited_text
        resp.status = "approved"
        await session.commit()

        try:
            await sender.send(session, int(response_id))
        except Exception as e:
            logger.exception(f"Sender failed for edited response {response_id}: {e}")

    await callback.answer("✅ Отправлено")
    try:
        await callback.message.delete()
    except Exception:
        pass
    await state.clear()


async def cancel_edit(
    callback, state: FSMContext,
    factory: async_sessionmaker, sender,
) -> None:
    """Triggered by callback 'cancel_edit:<resp_id>'.

    `factory` and `sender` are accepted for parity with confirm_edit (so the
    dispatcher can register both with the same signature).
    """
    await callback.answer("↩ Возврат к драфту")
    try:
        await callback.message.delete()
    except Exception:
        pass
    await state.clear()
