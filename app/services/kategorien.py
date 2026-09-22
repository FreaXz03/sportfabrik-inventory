"""Kassenkategorie von Hand wählen (Phase B, Teilaufgabe B8).

Normalerweise schlägt der FEDAS-Code der Lieferantenrechnung die Kategorie
vor (`app/core/fedas.py`). Zwei Fälle bleiben übrig, und für die ist dieses
Modul da:

* Der Beleg bringt **keinen** FEDAS-Code mit (die meisten Lieferanten), oder
  die Ware wurde von Hand erfasst - dort gibt es gar keinen Beleg (D23/D27).
* Der Code steht auf dem Beleg, ist aber (noch) keiner Kassenkategorie
  zugeordnet: die Zuordnungstabelle kennt erst die aus echten Rechnungen
  bestätigten Codes.

Dann wählt jemand im Laden die Kategorie von Hand. Diese Wahl ist
verbindlich - `artikel.kategorie_manuell` merkt sie sich, und weder ein
späterer Import noch ein erweitertes FEDAS-Mapping überschreibt sie
(„einmal pro Artikel, danach gemerkt", Roadmap Abschnitt 6).

Die Kategorie hängt am **Artikel**, nicht an der Variante: sie gilt
filialübergreifend für alle Farben und Grössen desselben Modells (Regel 4).

Rechte (Regel 9/D21): Kategorie pflegen ist Artikelstamm-Arbeit und kein
Dokumenten-Upload - auch Mitarbeiter dürfen das.

Die Namen der Kategorien werden nicht übersetzt (Regel 7): sie stehen exakt
so in der Kasse (Regel 8).
"""

from sqlalchemy import select

from ..core.fedas import suggest_kategorie
from ..core.i18n import DEFAULT_LANGUAGE, translate
from ..core.kategorien import (
    HAUPTGRUPPEN_MIT_SPORTBEREICH,
    HAUPTGRUPPEN_OHNE_SPORTBEREICH,
    SPORTBEREICHE,
)
from ..core.models import Artikel, Kategorie, Variante

# Reihenfolge wie in der Kasse (Regel 8), nicht alphabetisch - wer im Laden
# auswählt, sucht die Kategorie dort, wo sie auf der Kasse steht.
_HAUPTGRUPPEN = HAUPTGRUPPEN_MIT_SPORTBEREICH + HAUPTGRUPPEN_OHNE_SPORTBEREICH


class KategorieNichtGefunden(LookupError):
    """Artikelvariante gibt es nicht - nichts wurde geändert."""


class KategorieError(ValueError):
    """Die gewählte Kategorie ist nicht brauchbar - nichts wurde geändert."""


def _sortierschluessel(kategorie: Kategorie):
    """Kassenreihenfolge; Unbekanntes (sollte es nicht geben) hinten dran."""
    hauptgruppe = (
        _HAUPTGRUPPEN.index(kategorie.hauptgruppe)
        if kategorie.hauptgruppe in _HAUPTGRUPPEN
        else len(_HAUPTGRUPPEN)
    )
    if kategorie.sportbereich is None:
        sportbereich = -1  # Velo und Food haben keinen - sie stehen zuerst.
    elif kategorie.sportbereich in SPORTBEREICHE:
        sportbereich = SPORTBEREICHE.index(kategorie.sportbereich)
    else:
        sportbereich = len(SPORTBEREICHE)
    return (hauptgruppe, sportbereich, kategorie.hauptgruppe or "", kategorie.sportbereich or "")


def kategorie_daten(kategorie: Kategorie | None) -> dict | None:
    if kategorie is None:
        return None
    return {
        "id": kategorie.id,
        "hauptgruppe": kategorie.hauptgruppe,
        "sportbereich": kategorie.sportbereich,
    }


def liste_kategorien(session) -> list[dict]:
    """Alle Kassenkategorien in der Reihenfolge der Kasse (Regel 8)."""
    kategorien = session.scalars(select(Kategorie)).all()
    return [kategorie_daten(eintrag) for eintrag in sorted(kategorien, key=_sortierschluessel)]


def kategorie_vorschlag(session, fedas_code: str | None) -> Kategorie | None:
    """Was der FEDAS-Code vorschlägt - oder None, wenn er fehlt bzw. (noch)
    nicht zugeordnet ist. Genau dann muss von Hand gewählt werden."""
    vorschlag = suggest_kategorie(fedas_code)
    if vorschlag is None:
        return None
    hauptgruppe, sportbereich = vorschlag
    return session.scalar(
        select(Kategorie).where(
            Kategorie.hauptgruppe == hauptgruppe,
            Kategorie.sportbereich == sportbereich,
        )
    )


def merke_kategorie(artikel: Artikel, kategorie_id: int | None) -> bool:
    """Kategorie an einem Artikel nachtragen, ohne je eine bestehende zu
    überschreiben („einmal pro Artikel, danach gemerkt").

    Für den Weg über die Erfassung gedacht, wo Artikel nebenbei entstehen;
    die Auswahl auf der Artikelseite geht über `setze_kategorie()` und darf
    korrigieren. Gibt zurück, ob etwas gesetzt wurde.
    """
    if kategorie_id is None or artikel.kategorie_id is not None:
        return False
    artikel.kategorie_id = kategorie_id
    artikel.kategorie_manuell = True
    return True


def _artikel_zur_variante(session, varianten_id: int, language: str):
    variante = session.get(Variante, varianten_id)
    if variante is None:
        raise KategorieNichtGefunden(
            translate("errors.article_details.product_not_found", language)
        )
    return variante, session.get(Artikel, variante.artikel_id)


def _stand(session, variante: Variante, artikel: Artikel) -> dict:
    kategorie = (
        session.get(Kategorie, artikel.kategorie_id)
        if artikel.kategorie_id is not None
        else None
    )
    return {
        "varianten_id": variante.id,
        "artikel_id": artikel.id,
        "kategorie": kategorie_daten(kategorie),
        # Woher sie kommt: von Hand gewählt oder aus dem FEDAS-Code
        # vorgeschlagen - die Oberfläche sagt es dazu, denn die
        # Zuordnungstabelle ist noch nicht vollständig bestätigt.
        "manuell": bool(artikel.kategorie_manuell),
        "fedas_code": artikel.fedas_code,
        "vorschlag": kategorie_daten(kategorie_vorschlag(session, artikel.fedas_code)),
    }


def artikel_kategorie(
    session, varianten_id: int, language: str = DEFAULT_LANGUAGE
) -> dict:
    """Aktuelle Kategorie eines Artikels samt Herkunft und FEDAS-Vorschlag."""
    variante, artikel = _artikel_zur_variante(session, varianten_id, language)
    return _stand(session, variante, artikel)


def setze_kategorie(
    session,
    varianten_id: int,
    kategorie_id: int | None,
    language: str = DEFAULT_LANGUAGE,
) -> dict:
    """Kategorie von Hand setzen oder wieder leeren.

    Gesetzt gilt sie als von Hand gewählt und wird von keinem Import mehr
    angerührt. Leeren stellt den Ausgangszustand wieder her: der Artikel ist
    wieder offen, ein späterer Beleg mit bekanntem FEDAS-Code darf also
    wieder vorschlagen.
    """
    variante, artikel = _artikel_zur_variante(session, varianten_id, language)
    kategorie = None
    if kategorie_id is not None:
        kategorie = session.get(Kategorie, kategorie_id)
        if kategorie is None:
            raise KategorieError(translate("errors.kategorie.unknown", language))
    artikel.kategorie_id = None if kategorie is None else kategorie.id
    artikel.kategorie_manuell = kategorie is not None
    session.commit()
    return _stand(session, variante, artikel)
