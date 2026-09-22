"""Ware von Hand erfassen - ohne Beleg, direkt eingebucht (Phase B,
Teilaufgabe B6).

Der zweite Weg, auf dem Ware ins System kommt: kein PDF, kein Parser, sondern
Scanner oder Tastatur. Gedacht für Ware ohne Dokument und für Lieferanten,
deren Layout (noch) kein Parser kennt.

Die Regeln dahinter:

* **Kein Beleg** (D27): Ware ohne Dokument ist ein direkter Wareneingang -
  es entsteht kein Eintrag in `dokumente`, `wareneingaenge.dokument_id` bleibt
  leer (Migration `a7b8c9d0e1f2`).
* **Wenig Pflichtfelder** (D23): Marke, Bezeichnung, Menge und UVP. Alles
  andere - EAN, Farbe, Grösse, Einheit, Lieferant, Artikelnummer, EK und
  Kategorie - ist freiwillig (Regel 5 und Regel 10).
* **Ware ist da** (Regel 3): Von Hand erfasst wird nur, was man in den Händen
  hält. Der Wareneingang ist deshalb sofort `eingetroffen` und wird gebucht;
  ein *erwarteter* Eingang entsteht hier nie.
* **Eingangsdatum** (Regel 6/D13): heute oder rückwirkend; ein Standort ohne
  Verkauf (GEWA, VEBO, Dietikon) bekommt keines.
* **Bestand** (Regel 2): nie direkt schreiben, sondern über dieselbe
  `buche_zugang()` wie Import und Ankunftsbestätigung.
* **Rechte** (Regel 9/D21): Erfassen ist Lagerarbeit und kein
  Dokumenten-Upload - das dürfen auch Mitarbeiter.

Artikel und Varianten werden über `app/services/artikel.py` gefunden, also
nach genau derselben Regel wie beim Import: bekannte EAN → bekannte Variante,
sonst Lieferant + Artikelnummer + Farbe + Grösse.

Ohne Beleg gibt es auch keinen FEDAS-Code, der die Kassenkategorie
vorschlagen könnte (Regel 8). Sie lässt sich deshalb gleich hier mitgeben -
freiwillig und nach derselben Regel wie überall: eine schon gesetzte
Kategorie wird nie überschrieben (`app/services/kategorien.py`).
"""

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from ..core.i18n import DEFAULT_LANGUAGE, translate
from ..core.models import (
    Artikel,
    Kategorie,
    Lagerort,
    Lieferant,
    Preis,
    Variante,
    Wareneingang,
    WareneingangPosition,
    WareneingangPositionQuelle,
)
from .artikel import (
    EAN_MUSTER,
    artikel_group_key,
    finde_artikel,
    finde_variante_ohne_ean,
    finde_variante_per_ean,
)
from .kategorien import kategorie_daten, merke_kategorie
from .wareneingang import ADVISORY_LOCK_ID, buche_zugang

# Grund der Lagerbewegung: ein fester Schlüssel, kein UI-Text - übersetzt wird
# erst bei der Anzeige (Regel 7).
GRUND = "manuelle-erfassung"

MAX_POSITIONEN = 200
MAX_BETRAG = Decimal("100000000")

# Textfelder mit ihrer Spaltenlänge; `True` = Pflichtfeld (D23).
TEXTFELDER = {
    "marke": (100, True),
    "bezeichnung": (500, True),
    "lieferanten_artikelnr": (100, False),
    "farbe": (250, False),
    "groesse": (100, False),
    "einheit": (30, False),
    "ean": (30, False),
}

# Feldnamen für Fehlermeldungen: dieselben Übersetzungen wie in der Vorschau.
FELD_KEYS = {
    "marke": "brand",
    "bezeichnung": "description",
    "lieferanten_artikelnr": "supplier_article_no",
    "farbe": "color",
    "groesse": "size",
    "einheit": "unit",
    "ean": "ean",
    "menge": "quantity",
    "uvp": "uvp",
    "ek": "ek",
    "kategorie_id": "kategorie",
}


class ErfassungRejected(ValueError):
    """Die Erfassung ist nicht plausibel - nichts wurde gebucht."""


def _feld(name: str, language: str) -> str:
    return translate(f"fields.{FELD_KEYS.get(name, name)}", language)


def _fehler(key: str, language: str, zeile: int, **kwargs) -> ErfassungRejected:
    return ErfassungRejected(
        translate(f"errors.erfassung.{key}", language, row=zeile, **kwargs)
    )


def _text_wert(rohwert, name: str, zeile: int, language: str) -> str | None:
    laenge, pflicht = TEXTFELDER[name]
    if rohwert is None:
        wert = ""
    elif isinstance(rohwert, str):
        wert = rohwert.strip()
    else:
        raise _fehler("invalid_field", language, zeile, field=_feld(name, language))
    if not wert:
        if pflicht:
            raise _fehler("field_required", language, zeile, field=_feld(name, language))
        return None
    if len(wert) > laenge:
        raise _fehler(
            "field_too_long",
            language,
            zeile,
            field=_feld(name, language),
            limit=laenge,
        )
    return wert


def _kategorie_id(rohwert, zeile: int, language: str) -> int | None:
    """Kassenkategorie ist auch hier freiwillig (D23) - die meiste von Hand
    erfasste Ware hat keinen FEDAS-Code, deshalb lässt sie sich gleich beim
    Erfassen mitgeben (Teilaufgabe B8). Ob die Id wirklich existiert, prüft
    `erfasse_wareneingang()` in der Transaktion."""
    if rohwert is None or (isinstance(rohwert, str) and not rohwert.strip()):
        return None
    # `bool` ist in Python ein `int` - als Kategorie-Id ist es Unsinn.
    if isinstance(rohwert, bool):
        raise _fehler("invalid_field", language, zeile, field=_feld("kategorie_id", language))
    if isinstance(rohwert, int):
        wert = rohwert
    elif isinstance(rohwert, str) and rohwert.strip().isdigit():
        wert = int(rohwert.strip())
    else:
        raise _fehler("invalid_field", language, zeile, field=_feld("kategorie_id", language))
    if wert <= 0:
        raise _fehler("invalid_field", language, zeile, field=_feld("kategorie_id", language))
    return wert


def _betrag(rohwert, name: str, zeile: int, language: str) -> Decimal:
    """Menge/Preis als Decimal - nie über float (CLAUDE.md „Technik")."""
    if isinstance(rohwert, float):
        raise _fehler("invalid_number", language, zeile, field=_feld(name, language))
    try:
        # Komma wie im Laden getippt ("39,90") ist erlaubt.
        wert = Decimal(str(rohwert).strip().replace(",", "."))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise _fehler(
            "invalid_number", language, zeile, field=_feld(name, language)
        ) from exc
    if not wert.is_finite() or abs(wert) >= MAX_BETRAG or wert != wert.quantize(Decimal(".01")):
        raise _fehler("invalid_number", language, zeile, field=_feld(name, language))
    return wert


def pruefe_positionen(positionen, language: str = DEFAULT_LANGUAGE) -> list[dict]:
    """Eingaben prüfen und normalisieren, bevor irgendetwas gebucht wird -
    serverseitig, Client-Werten wird nie vertraut (CLAUDE.md „Technik")."""
    if not isinstance(positionen, list) or not positionen:
        raise ErfassungRejected(translate("errors.erfassung.no_positions", language))
    if len(positionen) > MAX_POSITIONEN:
        raise ErfassungRejected(
            translate("errors.erfassung.too_many_positions", language, limit=MAX_POSITIONEN)
        )
    geprueft = []
    for index, position in enumerate(positionen, start=1):
        if not isinstance(position, dict):
            raise _fehler("invalid_position", language, index)
        unbekannt = set(position) - set(TEXTFELDER) - {
            "menge",
            "uvp",
            "ek",
            "kategorie_id",
        }
        if unbekannt:
            raise _fehler("invalid_position", language, index)
        werte = {
            name: _text_wert(position.get(name), name, index, language)
            for name in TEXTFELDER
        }
        # Regel 5: EAN darf fehlen. Steht eine da, muss sie das Format einer
        # EAN haben - dieselbe Prüfung wie bei den Korrekturen der Vorschau.
        if werte["ean"] and not EAN_MUSTER.fullmatch(werte["ean"]):
            raise _fehler("invalid_ean", language, index)
        menge = _betrag(position.get("menge"), "menge", index, language)
        if menge <= 0:
            raise _fehler("quantity_not_positive", language, index)
        uvp = _betrag(position.get("uvp"), "uvp", index, language)
        if uvp < 0:
            raise _fehler("price_negative", language, index, field=_feld("uvp", language))
        # Regel 10: EK ist optional und wird nur gespeichert, wenn er da ist.
        ek = None
        if str(position.get("ek") or "").strip():
            ek = _betrag(position.get("ek"), "ek", index, language)
            if ek < 0:
                raise _fehler("price_negative", language, index, field=_feld("ek", language))
        geprueft.append(
            {
                **werte,
                "menge": menge,
                "uvp": uvp,
                "ek": ek,
                "kategorie_id": _kategorie_id(position.get("kategorie_id"), index, language),
                "zeile": index,
            }
        )
    return geprueft


def variante_per_ean(session, ean: str | None, language: str = DEFAULT_LANGUAGE) -> dict | None:
    """Bekannte Variante zu einer gescannten EAN - füllt das Formular vor.

    `None` heisst „unbekannte EAN": dann wird ein neuer Artikel erfasst, die
    EAN aber übernommen. Keine Prüfung auf Rechte nötig, es sind
    Artikelstamm-Daten (filialübergreifend, Regel 4).
    """
    ean = (ean or "").strip()
    if not ean:
        raise ErfassungRejected(translate("errors.erfassung.ean_missing", language))
    if not EAN_MUSTER.fullmatch(ean):
        raise ErfassungRejected(translate("errors.erfassung.ean_format", language))
    variante = finde_variante_per_ean(session, ean)
    if variante is None:
        return None
    artikel = session.get(Artikel, variante.artikel_id)
    kategorie = (
        session.get(Kategorie, artikel.kategorie_id)
        if artikel.kategorie_id is not None
        else None
    )
    lieferant = (
        session.get(Lieferant, artikel.lieferant_id) if artikel.lieferant_id else None
    )
    # Letzter bekannter UVP/EK (Preisverlauf, neuester Eintrag zuerst) und die
    # zuletzt verwendete Einheit - als Vorschlag, nicht als Vorgabe.
    preis = session.scalars(
        select(Preis)
        .where(Preis.varianten_id == variante.id)
        .order_by(Preis.datum.desc().nullslast(), Preis.id.desc())
        .limit(1)
    ).first()
    einheit = session.scalars(
        select(WareneingangPosition.einheit)
        .where(
            WareneingangPosition.varianten_id == variante.id,
            WareneingangPosition.einheit.is_not(None),
        )
        .order_by(WareneingangPosition.id.desc())
        .limit(1)
    ).first()
    return {
        "varianten_id": variante.id,
        "artikel_id": artikel.id,
        "ean": variante.ean,
        "ean_intern": bool(variante.ean_intern),
        "marke": artikel.marke,
        "bezeichnung": artikel.bezeichnung,
        "lieferanten_artikelnr": artikel.lieferanten_artikelnr,
        "farbe": variante.farbe,
        "groesse": variante.groesse,
        "einheit": einheit,
        "uvp": str(preis.uvp) if preis and preis.uvp is not None else None,
        "ek": str(preis.ek) if preis and preis.ek is not None else None,
        "lieferant": None if lieferant is None else {"id": lieferant.id, "name": lieferant.name},
        # Nur zur Anzeige: eine bestehende Kategorie wird beim Erfassen nie
        # überschrieben (Teilaufgabe B8).
        "kategorie": kategorie_daten(kategorie),
    }


def erfasse_wareneingang(
    positionen,
    session_factory,
    *,
    lagerort_id: int,
    benutzer: dict | None = None,
    eingangsdatum: date | None = None,
    lieferant_id: int | None = None,
    language: str = DEFAULT_LANGUAGE,
) -> dict:
    """Von Hand erfasste Ware als Wareneingang ohne Beleg buchen (D27).

    Ein Aufruf = ein Wareneingang mit allen übergebenen Positionen, in einer
    Transaktion: entweder ist alles gebucht oder nichts.
    """
    geprueft = pruefe_positionen(positionen, language)
    heute = date.today()
    if eingangsdatum and eingangsdatum > heute:
        raise ErfassungRejected(translate("errors.erfassung.date_in_future", language))
    try:
        with session_factory() as session, session.begin():
            # Dieselbe Sperre wie Import und Ankunftsbestätigung: zwei
            # Arbeitsplätze dürfen sich bei Varianten und Bestand nicht
            # überholen.
            if session.bind.dialect.name == "postgresql":
                session.execute(text(f"SELECT pg_advisory_xact_lock({ADVISORY_LOCK_ID})"))
            lagerort = session.get(Lagerort, lagerort_id)
            if lagerort is None:
                raise ErfassungRejected(
                    translate("errors.erfassung.lagerort_unknown", language)
                )
            if lieferant_id is not None and session.get(Lieferant, lieferant_id) is None:
                raise ErfassungRejected(
                    translate("errors.erfassung.supplier_unknown", language)
                )
            kategorie_ids = {
                eintrag["kategorie_id"]
                for eintrag in geprueft
                if eintrag["kategorie_id"] is not None
            }
            if kategorie_ids:
                bekannt = set(
                    session.scalars(
                        select(Kategorie.id).where(Kategorie.id.in_(kategorie_ids))
                    )
                )
                if bekannt != kategorie_ids:
                    raise ErfassungRejected(
                        translate("errors.erfassung.kategorie_unknown", language)
                    )

            gesehen = eingangsdatum or heute
            # Regel 6/D13: An einem Standort ohne Verkauf (GEWA, VEBO,
            # Dietikon) startet die Reduktionsuhr nicht - also kein
            # Eingangsdatum.
            datum = gesehen if lagerort.verkauf else None
            jetzt = datetime.now(timezone.utc)

            wareneingang = Wareneingang(
                dokument_id=None,
                lagerort_id=lagerort.id,
                status="eingetroffen",
                eingangsdatum=datum,
            )
            session.add(wareneingang)
            session.flush()

            neue_varianten, bekannte_varianten = 0, set()
            artikel_cache, variante_cache = {}, {}
            for eintrag in geprueft:
                ean = eintrag["ean"]
                variante = variante_cache.get(ean) if ean else None
                if variante is None and ean:
                    variante = finde_variante_per_ean(session, ean)
                    if variante is not None:
                        bekannte_varianten.add(variante.id)

                if variante is None:
                    group_key = artikel_group_key(
                        eintrag["marke"], eintrag["lieferanten_artikelnr"]
                    )
                    artikel = artikel_cache.get(group_key) if group_key else None
                    if artikel is None:
                        artikel = finde_artikel(session, lieferant_id, group_key)
                    if artikel is None:
                        artikel = Artikel(
                            lieferant_id=lieferant_id,
                            marke=eintrag["marke"],
                            lieferanten_artikelnr=eintrag["lieferanten_artikelnr"],
                            bezeichnung=eintrag["bezeichnung"],
                        )
                        session.add(artikel)
                        session.flush()
                    if group_key:
                        artikel_cache[group_key] = artikel

                    if not ean:
                        variante = finde_variante_ohne_ean(
                            session, artikel.id, eintrag["farbe"], eintrag["groesse"]
                        )
                    if variante is None:
                        variante = Variante(
                            artikel_id=artikel.id,
                            farbe=eintrag["farbe"],
                            groesse=eintrag["groesse"],
                            ean=ean,
                            ean_intern=False,
                        )
                        session.add(variante)
                        session.flush()
                        neue_varianten += 1
                    else:
                        bekannte_varianten.add(variante.id)
                if ean:
                    variante_cache[ean] = variante

                # Kategorie von Hand (Teilaufgabe B8): füllt nur eine noch
                # leere Kategorie - auch bei einem über die EAN gefundenen
                # Altartikel. Eine bestehende bleibt, wie sie ist.
                merke_kategorie(
                    session.get(Artikel, variante.artikel_id), eintrag["kategorie_id"]
                )

                # Von Hand erfasste Ware ist da - sie zählt wie eine Lieferung.
                variante.first_seen = (
                    min(variante.first_seen, gesehen) if variante.first_seen else gesehen
                )
                variante.last_seen = (
                    max(variante.last_seen, gesehen) if variante.last_seen else gesehen
                )

                position = WareneingangPosition(
                    wareneingang_id=wareneingang.id,
                    varianten_id=variante.id,
                    menge=eintrag["menge"],
                    menge_eingetroffen=eintrag["menge"],
                    einheit=eintrag["einheit"],
                    uvp=eintrag["uvp"],
                    ek=eintrag["ek"],
                )
                session.add(position)
                session.flush()
                # Audit wie beim Import: was wurde eingetippt (Original,
                # unverändert), von wem und wann.
                session.add(
                    WareneingangPositionQuelle(
                        position_id=position.id,
                        data={
                            "quelle": GRUND,
                            "zeile": eintrag["zeile"],
                            "erfasst_am": jetzt.isoformat(),
                            "erfasst_von": benutzer or {},
                            "eingabe": {
                                name: (
                                    str(wert) if isinstance(wert, Decimal) else wert
                                )
                                for name, wert in eintrag.items()
                                if name != "zeile"
                            },
                        },
                    )
                )
                session.add(
                    Preis(
                        varianten_id=variante.id,
                        uvp=eintrag["uvp"],
                        ek=eintrag["ek"],
                        datum=gesehen,
                        dokument_id=None,
                    )
                )
                buche_zugang(
                    session,
                    lagerort_id=lagerort.id,
                    varianten_id=variante.id,
                    position_id=position.id,
                    menge=eintrag["menge"],
                    eingangsdatum=datum,
                    benutzer=benutzer,
                    zeitpunkt=jetzt,
                    grund=GRUND,
                )

            ergebnis = {
                "wareneingang_id": wareneingang.id,
                "lagerort": {
                    "id": lagerort.id,
                    "code": lagerort.code,
                    "name": lagerort.name,
                },
                "positionen": len(geprueft),
                "neue_varianten": neue_varianten,
                "bekannte_varianten": len(bekannte_varianten),
                "eingangsdatum": datum.isoformat() if datum else None,
            }
        return ergebnis
    except IntegrityError as exc:
        # Praktisch nur die EAN-Eindeutigkeit: zwei Arbeitsplätze erfassen
        # gleichzeitig dieselbe neue EAN.
        raise ErfassungRejected(
            translate("errors.erfassung.integrity_conflict", language)
        ) from exc
