"""Bestand ansehen: Menge je Variante × Lagerort (Phase C, Teilaufgabe C2).

Hier wird nur **gelesen**. Entstehen tut der Bestand ausschliesslich über
`lagerbewegungen` (Regel 2) - Import, bestätigte Ankunft und manuelle
Erfassung buchen ihn, später auch Ausbuchen und Umlagerung.

Lesen darf jede Anmeldung **alle** Filialen (bestätigt am 22.09.2026): was
gezeigt wird, entscheidet die Auswahl auf der Seite, nicht das Recht. Ware an
einem Standort ohne Verkauf (GEWA, VEBO, Dietikon) hat kein Eingangsdatum
(Regel 6/D13) - die Liste zeigt das offen an, damit sichtbar bleibt, was noch
nicht in einer Filiale steht.
"""

from decimal import Decimal

from sqlalchemy import func, or_, select

from ..core.models import Artikel, Bestand, Kategorie, Lagerort, Variante

# Obergrenze je Abfrage, damit eine Seite im Ladennetz nicht am Datenvolumen
# erstickt. Der Rest kommt über `offset` nach.
MAX_LIMIT = 500
STANDARD_LIMIT = 200


def _zahl(wert) -> str:
    """Menge als Text - nie als float (CLAUDE.md, Technik & Konventionen)."""
    return f"{Decimal(wert or 0):.2f}"


def _mit_filtern(abfrage, lagerort_id, suche, nur_vorhanden, nur_negativ=False, varianten_ids=None):
    """Die gemeinsamen Joins und Filter für Liste, Anzahl und Summe."""
    abfrage = (
        abfrage.select_from(Bestand)
        .join(Variante, Variante.id == Bestand.varianten_id)
        .join(Artikel, Artikel.id == Variante.artikel_id)
        .join(Lagerort, Lagerort.id == Bestand.lagerort_id)
        # Kategorie ist optional (FEDAS unbekannt, noch nicht von Hand gewählt).
        .outerjoin(Kategorie, Kategorie.id == Artikel.kategorie_id)
    )
    if lagerort_id is not None:
        abfrage = abfrage.where(Bestand.lagerort_id == lagerort_id)
    if nur_vorhanden:
        # Nicht `> 0`: ein negativer Bestand ist möglich (bestätigt am
        # 22.09.2026) und muss gerade dann sichtbar sein.
        abfrage = abfrage.where(Bestand.menge != 0)
    if nur_negativ:
        abfrage = abfrage.where(Bestand.menge < 0)
    if varianten_ids is not None:
        abfrage = abfrage.where(Bestand.varianten_id.in_(varianten_ids))
    if suche:
        muster = f"%{suche.strip()}%"
        abfrage = abfrage.where(
            or_(
                Artikel.marke.ilike(muster),
                Artikel.bezeichnung.ilike(muster),
                Artikel.lieferanten_artikelnr.ilike(muster),
                Variante.ean.ilike(muster),
            )
        )
    return abfrage


def liste_bestand(
    session,
    lagerort_id: int | None = None,
    suche: str | None = None,
    nur_vorhanden: bool = True,
    limit: int = STANDARD_LIMIT,
    offset: int = 0,
    nur_negativ: bool = False,
    varianten_ids: list[int] | None = None,
) -> dict:
    """Bestandszeilen samt Anzahl und Gesamtmenge der ganzen Auswahl.

    `lagerort_id = None` heisst filialübergreifend. `nur_vorhanden` blendet
    Zeilen mit Menge 0 aus - die entstehen, sobald Ware wieder ausgebucht wird.
    """
    limit = max(1, min(int(limit), MAX_LIMIT))
    offset = max(0, int(offset))

    kennzahlen = session.execute(
        _mit_filtern(
            select(func.count(), func.coalesce(func.sum(Bestand.menge), 0)),
            lagerort_id,
            suche,
            nur_vorhanden,
            nur_negativ,
            varianten_ids,
        )
    ).one()
    gesamt, summe = int(kennzahlen[0]), kennzahlen[1]

    zeilen = session.execute(
        _mit_filtern(
            select(Bestand, Variante, Artikel, Lagerort, Kategorie),
            lagerort_id,
            suche,
            nur_vorhanden,
            nur_negativ,
            varianten_ids,
        )
        .order_by(Artikel.marke, Artikel.bezeichnung, Variante.id, Lagerort.id)
        .limit(limit)
        .offset(offset)
    ).all()

    return {
        "zeilen": [
            {
                "varianten_id": variante.id,
                "marke": artikel.marke,
                "bezeichnung": artikel.bezeichnung,
                "lieferanten_artikelnr": artikel.lieferanten_artikelnr,
                "farbe": variante.farbe,
                "groesse": variante.groesse,
                "ean": variante.ean,
                "ean_intern": bool(variante.ean_intern),
                # Hauptgruppe der Kassenkategorie (Textil, Hartware, Schuhe,
                # Velo, Food) - gewünscht am 23.09.2026.
                "hauptgruppe": kategorie.hauptgruppe if kategorie else None,
                "lagerort": {
                    "id": lagerort.id,
                    "code": lagerort.code,
                    "name": lagerort.name,
                    "verkauf": bool(lagerort.verkauf),
                },
                "menge": _zahl(bestand.menge),
                # Ohne Verkauf gibt es kein Eingangsdatum (Regel 6) - die
                # Oberfläche zeigt dort einen Hinweis statt eines Datums.
                "aeltestes_eingangsdatum": bestand.aeltestes_eingangsdatum.isoformat()
                if bestand.aeltestes_eingangsdatum
                else None,
            }
            for bestand, variante, artikel, lagerort, kategorie in zeilen
        ],
        "total": gesamt,
        "summe": _zahl(summe),
        "limit": limit,
        "offset": offset,
        "hat_mehr": offset + len(zeilen) < gesamt,
    }
