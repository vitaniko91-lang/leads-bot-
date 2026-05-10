import pytest

from leads_bot.analyzer.geo_filter import has_ru_markers


@pytest.mark.parametrize("text", [
    "Оплата на карту Сбера, 50000 рублей",
    "Ищу дизайнера, ИП РФ оформит",
    "Связь по +7 999 123 45 67",
    "Пишите в телеграм, оплата через Тинькофф",
    "Срочно нужен UI, оплата на Wildberries-аккаунт",
    "Приходите в офис на Тверскую 15, Москва",
    "Yandex.Praktikum looking for designer",
    "Оплата через юmoney",
])
def test_ru_markers_detected(text):
    assert has_ru_markers(text) is True


@pytest.mark.parametrize("text", [
    "Шукаю дизайнера для лендінгу, оплата через Wise",
    "Looking for UI/UX designer, payment via Payoneer",
    "Нужен дизайнер, оплата через крипту USDT",
    "Hi, designer for SaaS in Berlin, IBAN payment",
    "Ищем UI дизайнера для стартапа в Алматы",
    "Need a Figma expert, $1500, weekly payouts via Wise",
])
def test_no_ru_markers(text):
    assert has_ru_markers(text) is False


def test_case_insensitive():
    assert has_ru_markers("оплата СБЕРбанк") is True
    assert has_ru_markers("ОПЛАТА ТИНЬКОФФ") is True


def test_phone_pattern_strict_ru_codes():
    # +7 9XX → RU mobile
    assert has_ru_markers("+7 999 1234567") is True
    assert has_ru_markers("+7 925 1234567") is True
    # +7 7XX → KZ mobile/city — NOT a RU marker
    assert has_ru_markers("+7 701 1234567") is False
    assert has_ru_markers("+7 7172 123456") is False
    # UA
    assert has_ru_markers("+380 50 1234567") is False
