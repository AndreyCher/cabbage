from __future__ import annotations

from copy import deepcopy
from typing import Any

from babel.languages import get_official_languages, get_territory_language_info


DEFAULT = "default"


def primary_language(country_code: str) -> str:
    country = country_code.upper()
    official = get_official_languages(country, de_facto=True)
    if official:
        return official[0]
    languages = get_territory_language_info(country)
    if languages:
        return max(languages, key=lambda code: float(languages[code].get("population_percent") or 0))
    return "en"


def location_defaults(country_code: str, timezone: str | None) -> dict[str, Any]:
    country = country_code.upper()
    language_tag = primary_language(country).replace("_", "-")
    language = language_tag.split("-", 1)[0]
    locale = f"{language_tag}-{country}"
    languages = list(dict.fromkeys([locale, language_tag, language]))
    if language != "en":
        languages.extend(["en-US", "en"])
    return {"locale": locale, "languages": languages, "timezone": timezone or DEFAULT}


def apply_location_defaults(config: dict[str, Any], country_code: str, timezone: str | None) -> dict[str, Any]:
    result = deepcopy(config)
    fingerprint = result.setdefault("fingerprint", {})
    for key, value in location_defaults(country_code, timezone).items():
        if fingerprint.get(key) in (None, DEFAULT):
            fingerprint[key] = value
    return result
