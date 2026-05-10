from leads_bot.db.models import Lead, Response, Source
from leads_bot.notifier.card import build_keyboard, format_lead_card


def _make(text="hi", title="Design Jobs UA"):
    src = Source(
        id=1, tg_id=-100, title=title, type="channel",
        language="ru", region="ua", status="active",
    )
    lead = Lead(
        id=128, source_id=1, tg_message_id=42, raw_text=text,
        is_lead=True, project_type="landing", budget_usd=1000,
        language="ru", client_country="ua", urgency="med",
        relevance_score=85, reasoning="good fit", status="drafted",
    )
    lead.source = src
    response = Response(id=999, lead_id=128, draft_text="Привет! Видела ваш пост...", status="drafted")
    return lead, response


def test_card_includes_key_fields():
    lead, response = _make()
    text = format_lead_card(lead, response)
    assert "#128" in text
    assert "85" in text
    assert "Design Jobs UA" in text
    assert "1000" in text
    assert "🇺🇦" in text
    assert "landing" in text
    assert "Привет! Видела ваш пост..." in text


def test_card_includes_original_message():
    lead, response = _make(text="Ищу дизайнера на лендинг для крипты")
    text = format_lead_card(lead, response)
    assert "Ищу дизайнера на лендинг для крипты" in text


def test_card_warns_when_country_unclear():
    lead, response = _make()
    lead.client_country = "unclear"
    text = format_lead_card(lead, response)
    assert "не ясна" in text


def test_card_under_telegram_limit():
    long = "x" * 3000
    lead, response = _make(text=long)
    text = format_lead_card(lead, response)
    assert len(text) <= 4096


def test_keyboard_has_four_buttons():
    kb = build_keyboard(response_id=999, source_id=1)
    flat = [btn for row in kb.inline_keyboard for btn in row]
    assert len(flat) == 4
    callback_data = [b.callback_data for b in flat]
    assert any("approve:999" in c for c in callback_data)
    assert any("edit:999" in c for c in callback_data)
    assert any("skip:999" in c for c in callback_data)
    assert any("mute:1" in c for c in callback_data)
