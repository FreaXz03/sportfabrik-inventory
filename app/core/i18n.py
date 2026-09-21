"""Übersetzungs-Infrastruktur (Regel 7: DE/FR/EN, keine hartcodierten UI-Texte
oder Fehlermeldungen). Katalog liegt als flache JSON-Dateien unter
app/static/i18n/<sprache>.json - einzige Quelle sowohl fürs Backend
(translate()) als auch fürs Frontend (per Fetch geladen, siehe
app/static/js/i18n.js). Deutsch ist Standard- und Fallback-Sprache.
"""

import json
from functools import lru_cache
from pathlib import Path

LANGUAGES = ("de", "fr", "en")
DEFAULT_LANGUAGE = "de"

_CATALOG_DIR = Path(__file__).resolve().parents[1] / "static" / "i18n"


@lru_cache(maxsize=len(LANGUAGES))
def _catalog(language: str) -> dict[str, str]:
    with open(_CATALOG_DIR / f"{language}.json", encoding="utf-8") as f:
        return json.load(f)


def normalize_language(language: str | None) -> str:
    return language if language in LANGUAGES else DEFAULT_LANGUAGE


def template(key: str, language: str | None = DEFAULT_LANGUAGE) -> str:
    """Ungerenderter Katalog-Text zu `key`, ohne Platzhalter zu ersetzen - für
    Fälle, in denen eine feste (sprachabhängige) Vorsilbe wiedererkannt werden
    muss, siehe app/services/corrections.py (Neuvalidierung alter Warnungen)."""
    language = normalize_language(language)
    text = _catalog(language).get(key)
    if text is None and language != DEFAULT_LANGUAGE:
        text = _catalog(DEFAULT_LANGUAGE).get(key)
    return text if text is not None else key


def translate(key: str, language: str | None = DEFAULT_LANGUAGE, **params) -> str:
    """Übersetzten Text zu `key` in `language`. Fällt auf Deutsch zurück, wenn
    der Key dort fehlt, und auf den Key selbst, wenn er nirgends existiert
    (macht einen vergessenen Katalog-Eintrag sofort sichtbar statt einen
    kryptischen KeyError zu werfen)."""
    language = normalize_language(language)
    text = _catalog(language).get(key)
    if text is None and language != DEFAULT_LANGUAGE:
        text = _catalog(DEFAULT_LANGUAGE).get(key)
    if text is None:
        text = key
    return text.format(**params) if params else text
