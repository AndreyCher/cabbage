from __future__ import annotations

import secrets
from typing import Any


NAMES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "de": (("Anna", "Emma", "Hannah", "Leon", "Lukas", "Felix"), ("Mueller", "Schmidt", "Schneider", "Fischer", "Weber", "Wagner")),
    "fr": (("Camille", "Chloe", "Lea", "Louis", "Hugo", "Jules"), ("Martin", "Bernard", "Dubois", "Thomas", "Robert", "Richard")),
    "es": (("Lucia", "Sofia", "Carmen", "Hugo", "Mateo", "Diego"), ("Garcia", "Rodriguez", "Gonzalez", "Fernandez", "Lopez", "Martinez")),
    "it": (("Giulia", "Sofia", "Aurora", "Leonardo", "Lorenzo", "Matteo"), ("Rossi", "Russo", "Ferrari", "Esposito", "Bianchi", "Romano")),
    "pl": (("Zofia", "Julia", "Maja", "Jakub", "Jan", "Szymon"), ("Nowak", "Kowalski", "Wisniewski", "Wojcik", "Kowalczyk", "Kaminski")),
    "uk": (("Olena", "Sofiia", "Anna", "Oleksandr", "Maksym", "Dmytro"), ("Shevchenko", "Kovalenko", "Bondarenko", "Tkachenko", "Kovalchuk", "Kravchenko")),
    "pt": (("Maria", "Beatriz", "Ines", "Joao", "Miguel", "Tiago"), ("Silva", "Santos", "Ferreira", "Pereira", "Oliveira", "Costa")),
    "nl": (("Emma", "Sophie", "Julia", "Daan", "Sem", "Lucas"), ("DeVries", "Jansen", "VanDijk", "Bakker", "Visser", "Smit")),
    "tr": (("Zeynep", "Elif", "Defne", "Yusuf", "Emir", "Mehmet"), ("Yilmaz", "Kaya", "Demir", "Sahin", "Celik", "Yildiz")),
    "en": (("Olivia", "Emma", "Amelia", "Liam", "Noah", "Oliver"), ("Smith", "Johnson", "Williams", "Brown", "Jones", "Taylor")),
}

COUNTRY_LANGUAGE = {
    "AT": "de", "CH": "de", "DE": "de", "FR": "fr", "BE": "fr", "ES": "es", "MX": "es",
    "AR": "es", "IT": "it", "PL": "pl", "UA": "uk", "PT": "pt", "BR": "pt", "NL": "nl",
    "TR": "tr", "GB": "en", "US": "en", "CA": "en", "AU": "en", "IE": "en", "NZ": "en",
}


def country_from_config(config: dict[str, Any]) -> str | None:
    locale = config.get("fingerprint", {}).get("locale")
    if isinstance(locale, list):
        locale = locale[0] if locale else None
    if not isinstance(locale, str) or locale == "default":
        return None
    parts = locale.replace("_", "-").split("-")
    return next((part.upper() for part in reversed(parts[1:]) if len(part) == 2 and part.isalpha()), None)


def random_identity_name(country_code: str | None, existing: set[str]) -> str:
    language = COUNTRY_LANGUAGE.get((country_code or "").upper(), "en")
    first_names, last_names = NAMES[language]
    while True:
        candidate = f"{secrets.choice(first_names).lower()}-{secrets.choice(last_names).lower()}-{secrets.token_hex(2)}"
        if candidate not in existing:
            existing.add(candidate)
            return candidate


def numbered_identity_names(prefix: str, count: int) -> list[str]:
    return [f"{prefix}-{number}" for number in range(1, count + 1)]
