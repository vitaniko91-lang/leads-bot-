import pytest

from leads_bot.listener.filters import looks_like_lead


@pytest.mark.parametrize("text", [
    "Ищу дизайнера на лендинг, бюджет 800$",
    "Looking for a UI/UX designer for SaaS dashboard",
    "Шукаю дизайнера для мобільного застосунку",
    "Нужен дизайн интерфейса для стартапа",
    "Need UI design for crypto landing project",
    "Hiring senior product designer, full-time role",
    "Ищем дизайнера на проект, есть бюджет",
    "Подбираем UX дизайнера в команду",
])
def test_lead_keywords_detected(text):
    assert looks_like_lead(text) is True


@pytest.mark.parametrize("text", [
    "Привет всем, как дела сегодня?",
    "Опубликовала новый кейс в портфолио, посмотрите",
    "Нашёл крутую ссылку про typography сегодня",
    "Кто-нибудь знает курс по Figma актуальный?",
    "Just shipped my new portfolio site!",
    "",
    "👋",
])
def test_non_lead_messages_filtered(text):
    assert looks_like_lead(text) is False


def test_short_text_rejected():
    assert looks_like_lead("ищу") is False
    assert looks_like_lead("UI") is False
