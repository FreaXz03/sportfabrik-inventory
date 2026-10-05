"""Kundenretouren und gesperrter Bestand (Paket 4a, 05.10.2026).

* **Gesperrt statt verkäuflich.** Eine Retoure bucht in den gesperrten
  Bestand (`bestand.menge_gesperrt`, Bewegung `retoure`, `bestandsart =
  gesperrt`). Der verkäufliche Bestand (`bestand.menge`) ändert sich nicht -
  nichts wird automatisch wieder verkäuflich.
* **Grund** (Entscheid Q8): Passform und Geschmack bucht jede Mitarbeiterin in
  den eigenen Filialen direkt. Jeder andere Grund (Defekt, Reklamation,
  Sonstiges) ist ein Antrag (`beantragt`), der nichts bucht, bis
  Filialleiter/Zentrale genehmigt.
* **Ergebnis** der Prüfung: freigeben (zwei Bewegungen `freigabe`: gesperrt −n,
  verkäuflich +n), Lieferantenretoure oder Abschreiben (`ausbuchung` aus dem
  gesperrten Bestand). Mitarbeitende dürfen nur eine Passform-/Geschmack-
  Retoure freigeben; Lieferantenretoure und Abschreiben sind Filialleiter/
  Zentrale (Regel 9: Ausbuchen ausser Verkauf).
* Die Erstattung läuft an der Kasse; hier steht nur ein Verweis darauf.
* Die Reduktionsuhr startet durch eine Freigabe nicht neu (Regel 6): das
  Eingangsdatum bleibt, wie es ist.
"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select

from ..core.i18n import DEFAULT_LANGUAGE, translate
from ..core.models import Artikel, Bestand, Lagerbewegung, Lagerort, Retoure, Variante
from . import operation
from .ausbuchung import FREITEXT_MAX, buche_bewegung, sperren, zahl

# Passform/Geschmack: direkt buchbar; die übrigen brauchen Genehmigung.
GRUENDE_DIREKT = ("passform", "geschmack")
GRUENDE_ANTRAG = ("defekt", "reklamation", "sonstiges")
GRUENDE = GRUENDE_DIREKT + GRUENDE_ANTRAG
ZUSTAENDE = ("neuwertig", "gebraucht", "beschaedigt")
ERGEBNISSE = ("freigeben", "lieferant", "abschreiben")
ERGEBNIS_STATUS = {"freigeben": "freigegeben", "lieferant": "lieferant", "abschreiben": "abgeschrieben"}
MAX_MENGE = Decimal("999")
REFERENZ_MAX = 100
MAX_LISTE = 200


class RetoureRejected(ValueError):
    """Die Retoure ist nicht plausibel oder im falschen Zustand - nichts wurde gebucht."""


class RetoureForbidden(PermissionError):
    """Keine Berechtigung für diese Retoure - nichts wurde gebucht."""


def _menge(wert, language: str) -> Decimal:
    try:
        menge = Decimal(str(1 if wert is None else wert))
    except InvalidOperation:
        raise RetoureRejected(translate("errors.retoure.quantity_invalid", language)) from None
    if menge <= 0 or menge > MAX_MENGE or menge != menge.to_integral_value():
        raise RetoureRejected(translate("errors.retoure.quantity_invalid", language))
    return menge


def _text(wert, grenze: int, language: str) -> str | None:
    wert = (wert or "").strip()
    if len(wert) > grenze:
        raise RetoureRejected(translate("errors.ausbuchung.text_too_long", language, max=grenze))
    return wert or None


def _benutzer(benutzer: dict | None) -> dict:
    return {
        "kassennummer": (benutzer or {}).get("kassennummer"),
        "name": (benutzer or {}).get("name"),
    }


def _gesperrt_buchen(session, retoure: Retoure, typ: str, menge: Decimal, grund: str, benutzer, jetzt):
    return buche_bewegung(
        session,
        lagerort_id=retoure.lagerort_id,
        varianten_id=retoure.varianten_id,
        typ=typ,
        menge=menge,
        grund=grund,
        benutzer=benutzer,
        zeitpunkt=jetzt,
        bestandsart="gesperrt",
    )


def _einbuchen(session, retoure: Retoure, benutzer, jetzt) -> None:
    _gesperrt_buchen(session, retoure, "retoure", Decimal(retoure.menge), f"retoure:{retoure.id}", benutzer, jetzt)
    retoure.status = "in_pruefung"


def _antwort(session, retoure: Retoure) -> dict:
    variante = session.get(Variante, retoure.varianten_id)
    artikel = session.get(Artikel, variante.artikel_id)
    lagerort = session.get(Lagerort, retoure.lagerort_id)
    return {
        "id": retoure.id,
        "status": retoure.status,
        "ergebnis": retoure.ergebnis,
        "menge": zahl(retoure.menge),
        "grund": retoure.grund,
        "freitext": retoure.freitext,
        "zustand": retoure.zustand,
        "erstattungsreferenz": retoure.erstattungsreferenz,
        "verkauf_bewegung_id": retoure.verkauf_bewegung_id,
        "erfasst_von": retoure.erfasst_von_name,
        "erfasst_am": retoure.erfasst_am.isoformat(),
        "entschieden_von": retoure.entschieden_von_name,
        "entschieden_am": retoure.entschieden_am.isoformat() if retoure.entschieden_am else None,
        "varianten_id": variante.id,
        "marke": artikel.marke,
        "bezeichnung": artikel.bezeichnung,
        "farbe": variante.farbe,
        "groesse": variante.groesse,
        "ean": variante.ean,
        "lagerort": {"id": lagerort.id, "code": lagerort.code, "name": lagerort.name},
    }


def erfasse(
    session_factory,
    *,
    lagerort_id: int,
    varianten_id: int,
    grund: str,
    zustand: str,
    menge=None,
    freitext: str | None = None,
    verkauf_bewegung_id: int | None = None,
    erstattungsreferenz: str | None = None,
    sofort_freigeben: bool = False,
    benutzer: dict | None = None,
    language: str = DEFAULT_LANGUAGE,
    operation_id: str | None = None,
) -> dict:
    """Eine Kundenretoure erfassen. Direktgrund: gesperrt gebucht (oder, mit
    `sofort_freigeben` bei einer neuwertigen Ware, gleich wieder verkäuflich).
    Antragsgrund: nur vorgemerkt."""
    if grund not in GRUENDE:
        raise RetoureRejected(translate("errors.retoure.unknown_reason", language))
    if zustand not in ZUSTAENDE:
        raise RetoureRejected(translate("errors.retoure.unknown_condition", language))
    menge = _menge(menge, language)
    freitext = _text(freitext, FREITEXT_MAX, language)
    if grund == "sonstiges" and not freitext:
        raise RetoureRejected(translate("errors.ausbuchung.text_required", language))
    referenz = _text(erstattungsreferenz, REFERENZ_MAX, language)
    jetzt = datetime.now(timezone.utc)
    with session_factory() as session, session.begin():
        sperren(session)
        op = operation.starte(
            session, operation_id, "retoure", benutzer,
            {"lagerort_id": lagerort_id, "varianten_id": varianten_id, "grund": grund,
             "zustand": zustand, "menge": str(menge), "freitext": freitext,
             "verkauf_bewegung_id": verkauf_bewegung_id, "referenz": referenz,
             "sofort": sofort_freigeben},
            language,
        )
        if op.gespeichert is not None:
            return op.gespeichert
        if session.get(Lagerort, lagerort_id) is None:
            raise RetoureRejected(translate("errors.bestand.unknown_lagerort", language))
        if session.get(Variante, varianten_id) is None:
            raise RetoureRejected(translate("errors.ausbuchung.variant_not_found", language))
        if verkauf_bewegung_id is not None:
            verkauf = session.get(Lagerbewegung, verkauf_bewegung_id)
            if (
                verkauf is None
                or verkauf.typ != "verkauf"
                or verkauf.varianten_id != varianten_id
                or verkauf.lagerort_id != lagerort_id
            ):
                raise RetoureRejected(translate("errors.retoure.sale_not_matching", language))
        retoure = Retoure(
            lagerort_id=lagerort_id,
            varianten_id=varianten_id,
            menge=menge,
            grund=grund,
            freitext=freitext,
            zustand=zustand,
            verkauf_bewegung_id=verkauf_bewegung_id,
            erstattungsreferenz=referenz,
            status="beantragt",
            erfasst_von_kassennummer=_benutzer(benutzer)["kassennummer"],
            erfasst_von_name=_benutzer(benutzer)["name"],
            erfasst_am=jetzt,
        )
        session.add(retoure)
        session.flush()
        if grund in GRUENDE_DIREKT:
            _einbuchen(session, retoure, benutzer, jetzt)
            if sofort_freigeben and zustand == "neuwertig":
                _freigeben(session, retoure, benutzer, jetzt)
        return op.abschliessen(_antwort(session, retoure))


def _laden(session, retoure_id: int, language: str) -> Retoure:
    retoure = session.get(Retoure, retoure_id)
    if retoure is None:
        raise RetoureRejected(translate("errors.retoure.not_found", language))
    return retoure


def _entscheiden(retoure: Retoure, benutzer, jetzt) -> None:
    retoure.entschieden_von_kassennummer = _benutzer(benutzer)["kassennummer"]
    retoure.entschieden_von_name = _benutzer(benutzer)["name"]
    retoure.entschieden_am = jetzt


def genehmige(session_factory, retoure_id: int, benutzer: dict | None = None, language: str = DEFAULT_LANGUAGE) -> dict:
    """Antrag genehmigen: die Ware kommt in den gesperrten Bestand."""
    jetzt = datetime.now(timezone.utc)
    with session_factory() as session, session.begin():
        sperren(session)
        retoure = _laden(session, retoure_id, language)
        if retoure.status != "beantragt":
            raise RetoureRejected(translate("errors.retoure.wrong_state", language))
        _entscheiden(retoure, benutzer, jetzt)
        _einbuchen(session, retoure, benutzer, jetzt)
        return _antwort(session, retoure)


def lehne_ab(session_factory, retoure_id: int, benutzer: dict | None = None, language: str = DEFAULT_LANGUAGE) -> dict:
    """Antrag ablehnen: nichts wird gebucht."""
    jetzt = datetime.now(timezone.utc)
    with session_factory() as session, session.begin():
        sperren(session)
        retoure = _laden(session, retoure_id, language)
        if retoure.status != "beantragt":
            raise RetoureRejected(translate("errors.retoure.wrong_state", language))
        _entscheiden(retoure, benutzer, jetzt)
        retoure.status = "abgelehnt"
        return _antwort(session, retoure)


def _freigeben(session, retoure: Retoure, benutzer, jetzt) -> None:
    menge = Decimal(retoure.menge)
    grund = f"retoure:{retoure.id}"
    _gesperrt_buchen(session, retoure, "freigabe", -menge, grund, benutzer, jetzt)
    buche_bewegung(
        session,
        lagerort_id=retoure.lagerort_id,
        varianten_id=retoure.varianten_id,
        typ="freigabe",
        menge=menge,
        grund=grund,
        benutzer=benutzer,
        zeitpunkt=jetzt,
    )
    retoure.status = "abgeschlossen"
    retoure.ergebnis = "freigegeben"


def ergebnis_buchen(
    session_factory,
    retoure_id: int,
    ergebnis: str,
    *,
    darf_verwalten: bool,
    erlaubte_lagerorte: set[int] | None = None,
    benutzer: dict | None = None,
    language: str = DEFAULT_LANGUAGE,
) -> dict:
    """Prüfergebnis buchen. Mitarbeitende (`darf_verwalten = False`) dürfen
    nur eine Passform-/Geschmack-Retoure in ihren Filialen freigeben;
    Lieferantenretoure und Abschreiben sind Filialleiter/Zentrale."""
    if ergebnis not in ERGEBNISSE:
        raise RetoureRejected(translate("errors.retoure.unknown_outcome", language))
    jetzt = datetime.now(timezone.utc)
    with session_factory() as session, session.begin():
        sperren(session)
        retoure = _laden(session, retoure_id, language)
        if not darf_verwalten and (
            ergebnis != "freigeben"
            or retoure.grund not in GRUENDE_DIREKT
            or erlaubte_lagerorte is None
            or retoure.lagerort_id not in erlaubte_lagerorte
        ):
            raise RetoureForbidden(translate("errors.retoure.outcome_reserved", language))
        if retoure.status != "in_pruefung":
            raise RetoureRejected(translate("errors.retoure.wrong_state", language))
        _entscheiden(retoure, benutzer, jetzt)
        if ergebnis == "freigeben":
            _freigeben(session, retoure, benutzer, jetzt)
        else:
            grund = "retoure_lieferant" if ergebnis == "lieferant" else "retoure_abschreibung"
            _gesperrt_buchen(
                session, retoure, "ausbuchung", -Decimal(retoure.menge),
                f"{grund}:{retoure.id}", benutzer, jetzt,
            )
            retoure.status = "abgeschlossen"
            retoure.ergebnis = ERGEBNIS_STATUS[ergebnis]
        return _antwort(session, retoure)


def liste_retouren(
    session,
    lagerort_id: int | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """Retouren, neueste zuerst; `lagerort_id = None` heisst alle Filialen."""
    limit = max(1, min(int(limit), MAX_LISTE))
    offset = max(0, int(offset))
    filter_ = []
    if lagerort_id is not None:
        filter_.append(Retoure.lagerort_id == lagerort_id)
    if status:
        filter_.append(Retoure.status == status)
    gesamt = session.scalar(select(func.count()).select_from(Retoure).where(*filter_))
    zeilen = session.scalars(
        select(Retoure).where(*filter_).order_by(Retoure.erfasst_am.desc(), Retoure.id.desc()).limit(limit).offset(offset)
    ).all()
    return {
        "zeilen": [_antwort(session, retoure) for retoure in zeilen],
        "total": int(gesamt or 0),
        "hat_mehr": offset + len(zeilen) < (gesamt or 0),
        "offset": offset,
    }


def gesperrte_summe(session, lagerort_id: int | None = None) -> Decimal:
    """Gesamtmenge Rückware in Prüfung (für Kennzahlen und Pending)."""
    abfrage = select(func.coalesce(func.sum(Bestand.menge_gesperrt), 0))
    if lagerort_id is not None:
        abfrage = abfrage.where(Bestand.lagerort_id == lagerort_id)
    return Decimal(session.scalar(abfrage) or 0)
