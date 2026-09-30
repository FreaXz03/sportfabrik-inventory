"""Seitenleiste (Redesign 2026-09-29): Reihenfolge, Ziele und Übersetzungen.

Die Navigation wird im Browser aus der Liste EINTRAEGE in nav.js gezeichnet.
Dieser Test liest die Liste direkt aus der Datei: Reihenfolge wie bestellt,
jedes sichtbare Ziel ist eine echte Seite, jeder Text in DE/FR/EN vorhanden
(Regel 7). Rechte prüft weiterhin der Server je Seite (Regel 9).
"""

import json
import re
from pathlib import Path

from conftest import ANNA, ZENTRALE

APP = Path(__file__).resolve().parents[1] / "app"
NAV_JS = (APP / "static" / "js" / "nav.js").read_text(encoding="utf-8")

# Reihenfolge laut docs/redesign-2026-09-29.md (Gruppen und ihre Seiten).
ERWARTET = [
    "nav.overview",
    "nav.articles",
    "nav.group_bestand",
    "nav.bestand",
    "nav.runterschreiben",
    "nav.group_wareneingang",
    "nav.wareneingaenge",
    "nav.erfassen",
    "nav.group_warenausgang",
    "nav.ausbuchen",
    "nav.umlagern",
    "nav.group_belege",
    "nav.invoices",
    "nav.upload",
    "nav.statistiken",
    "nav.anstehend",
    "nav.group_verwaltung",
    "nav.konten",
    "nav.empfehlungen",
]


def eintraege():
    """(Schlüssel, Ziel oder None, noch nicht verfügbar) in Dateireihenfolge."""
    gefunden = []
    for zeile in NAV_JS.splitlines():
        seite = re.search(r"href: '([^']+)', key: '([^']+)'", zeile)
        gruppe = re.search(r"gruppe: '([^']+)'", zeile)
        if seite:
            gefunden.append((seite.group(2), seite.group(1), "bald: true" in zeile))
        elif gruppe:
            gefunden.append((gruppe.group(1), None, False))
    return gefunden


def test_reihenfolge_wie_bestellt():
    assert [schluessel for schluessel, _, _ in eintraege()] == ERWARTET


def test_texte_in_allen_sprachen():
    schluessel = {s for s, _, _ in eintraege()} | {"nav.main_aria", "nav.menu"}
    for sprache in ("de", "fr", "en"):
        katalog = json.loads((APP / "static" / "i18n" / f"{sprache}.json").read_text(encoding="utf-8"))
        fehlend = sorted(k for k in schluessel if not katalog.get(k))
        assert not fehlend, (sprache, fehlend)


def test_suche_texte_und_beschreibungen_in_allen_sprachen():
    """Phase 5: die Suche findet über Beschriftung und Beschreibung (`info`).
    Jede Seite braucht eine Beschreibung; alle Suchtexte gibt es in DE/FR/EN."""
    seiten = [z for z in NAV_JS.splitlines() if "href: '" in z and "key: '" in z]
    ohne_info = [z.strip() for z in seiten if "info: '" not in z]
    assert not ohne_info, ohne_info
    schluessel = set(re.findall(r"info: '([^']+)'", NAV_JS))
    schluessel |= {"nav.search_label", "nav.search_placeholder", "nav.search_none", "nav.search_results"}
    for sprache in ("de", "fr", "en"):
        katalog = json.loads((APP / "static" / "i18n" / f"{sprache}.json").read_text(encoding="utf-8"))
        fehlend = sorted(k for k in schluessel if not katalog.get(k))
        assert not fehlend, (sprache, fehlend)


def test_einstellungen_nicht_mehr_im_menue_aber_texte_da():
    """2026-09-30: „Einstellungen" ist kein Menüpunkt mehr; das Fenster öffnet
    über Konto-Symbol und Filiale (session.js). Neue Texte in DE/FR/EN."""
    assert "einstellungen: true" not in NAV_JS
    assert "sportfabrik:settings-open" not in NAV_JS
    schluessel = {
        "nav.settings", "settings.close", "settings.language", "settings.theme",
        "settings.branch", "nav.sidebar_collapse", "nav.sidebar_expand",
        "dashboard.shortcuts_edit",
    }
    for sprache in ("de", "fr", "en"):
        katalog = json.loads((APP / "static" / "i18n" / f"{sprache}.json").read_text(encoding="utf-8"))
        fehlend = sorted(k for k in schluessel if not katalog.get(k))
        assert not fehlend, (sprache, fehlend)


def test_anstehend_seite_fuer_alle_angemeldeten(welt):
    """Phase 4: /anstehend ist eine echte Seite, im Menü nicht mehr verborgen."""
    assert ("nav.anstehend", "/anstehend", False) in eintraege()
    assert welt.client.get("/anstehend", follow_redirects=False).status_code in (302, 303, 307)
    for konto in (ZENTRALE, ANNA):
        welt.anmelden(konto)
        antwort = welt.client.get("/anstehend", follow_redirects=False)
        assert antwort.status_code == 200
        assert 'id="anstehend"' in antwort.text


def test_ziele_sind_echte_seiten(welt):
    ziele = [ziel for _, ziel, bald in eintraege() if ziel and not bald]
    welt.anmelden(ZENTRALE)
    for ziel in ziele:
        assert welt.client.get(ziel, follow_redirects=False).status_code == 200, ziel
    # Mitarbeiter: Ziele ohne Recht leitet der Server um, nie ein 200.
    welt.anmelden(ANNA)
    assert welt.client.get("/konten", follow_redirects=False).status_code != 200
