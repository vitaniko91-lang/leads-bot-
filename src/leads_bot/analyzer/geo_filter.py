"""Detects RU client markers in message text. See spec §6.2."""
import re

RU_MARKERS = [
    # Banks / payment
    "сбер", "сберба", "сбербанк",
    "тиньк", "тинькофф", "tinkoff",
    "альфа-банк", "альфабанк",
    "втб ", "вэбмани", "webmoney",
    "юmoney", "qiwi",
    "wildberries", "вайлдберр",
    "yandex.praktikum", "яндекс.практикум",

    # Legal entity / business form
    "ип рф", "ооо рф", "самозанят",
    "акт выполненных работ",

    # Geography
    "москв", "питер", "санкт-петер", "спб ",
    "ростов-на-дону", "новосибирск", "екатеринбург",
    "тверская", "невский",

    # Bureaucratic phrases
    "ндс ", "усн", "патент рф",
]


# RU mobile: +7 followed by 9XX (RU-only mobile prefix). KZ uses +7 7XX.
_RU_MOBILE_RE = re.compile(
    r"\+7[\s\-\(\)]*9\d{2}[\s\-\(\)]*\d{3}[\s\-\(\)]*\d{2}[\s\-\(\)]*\d{2}"
)


def has_ru_markers(text: str) -> bool:
    """Return True if text contains markers indicating a Russian client."""
    if not text:
        return False
    lower = text.lower()
    if any(marker in lower for marker in RU_MARKERS):
        return True
    if _RU_MOBILE_RE.search(text):
        return True
    return False
