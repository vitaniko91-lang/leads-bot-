"""Channel-level RU blocklist for discovery.

Differs from `analyzer.geo_filter`:
- Operates on channel TITLE + DESCRIPTION (not message bodies).
- Stricter: any RU-locale signal rejects the entire channel.
- Used at discovery time; matched channels are never inserted into
  discovery_candidates.
"""

RU_CHANNEL_BLOCKLIST = [
    # Cities
    "москв", "moscow", "питер", "санкт-петер", "спб",
    "новосибирск", "novosibirsk", "екатеринбург", "ekaterinburg",
    "ростов-на-дону", "rostov", "казань", "kazan",
    "нижний новгород", "самара", "челябинск",

    # Country / state
    "россия", " рф ", " рф,", " рф.", "(рф)", "дизайнер рф",
    "russia", "russian designers",

    # Banks / payment / orgs
    "сбер", "тинькофф", "tinkoff", "альфа-банк",
    "вайлдберр", "wildberries", "yandex", "яндекс",
    "озон", "ozon",

    # Legal entity (RU-flavor)
    "ип рф", "ооо рф",
]


def is_ru_channel(title: str, description: str | None = None) -> bool:
    """Return True if title+description signal a RU-locale channel."""
    blob = f"{title or ''} {description or ''}".lower()
    if any(kw in blob for kw in RU_CHANNEL_BLOCKLIST):
        return True
    if blob.startswith("рф ") or blob.endswith(" рф") or blob == "рф":
        return True
    return False
