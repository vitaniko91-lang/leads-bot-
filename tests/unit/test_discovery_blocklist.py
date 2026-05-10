import pytest

from leads_bot.discovery.blocklist import RU_CHANNEL_BLOCKLIST, is_ru_channel


@pytest.mark.parametrize("title,desc", [
    ("Дизайнеры Москвы", ""),
    ("Design Russia", "Channel for designers in Russia"),
    ("Дизайнер РФ", "вакансии"),
    ("Веб-дизайн СПб", ""),
    ("Дизайн Питер", ""),
    ("ИП дизайн рф", ""),
    ("Сбер дизайн", ""),
    ("Yandex Design", ""),
    ("Тинькофф вакансии дизайн", ""),
    ("", "Designers from Moscow"),
])
def test_ru_channel_rejected(title, desc):
    assert is_ru_channel(title, desc) is True


@pytest.mark.parametrize("title,desc", [
    ("Design Jobs UA", ""),
    ("UX Berlin", ""),
    ("Freelance Designers Worldwide", ""),
    ("Дизайн Алматы", ""),
    ("Designers in Tbilisi", ""),
    ("Web Design Europe", ""),
])
def test_clean_channel_passes(title, desc):
    assert is_ru_channel(title, desc) is False


def test_blocklist_is_lowercase():
    for kw in RU_CHANNEL_BLOCKLIST:
        assert kw == kw.lower()
