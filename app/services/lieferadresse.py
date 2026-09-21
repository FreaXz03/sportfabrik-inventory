"""Lagerort aus der Lieferadresse eines Dokuments erkennen (Phase B,
Teilaufgabe B4 — D19).

Reine Textlogik, ohne Datenbank und ohne Layout-Wissen: die Adressen der
Lagerorte kommen als Parameter herein (`LagerortAdresse`), gesucht wird im
gesamten Dokumenttext. Damit funktioniert die Erkennung bei jedem Lieferanten
gleich, unabhängig davon, wo auf dem Beleg die Adresse steht.

**Das Ergebnis ist ein Vorschlag, keine Vorgabe** (D19): beim Import bleibt der
Lagerort änderbar. Entsprechend wird hier nie geraten — sind mehrere Lagerorte
gleich plausibel (typisch: Rechnungsadresse Volketswil, Lieferadresse Conthey,
ohne dass der Beleg das eine als Lieferadresse kennzeichnet), liefert die
Erkennung `None`, und es bleibt bei der aktiven Filiale.

Erkannt wird in zwei Durchgängen:

1. **Im Umfeld eines Lieferadress-Ankers** („Lieferadresse", „Lieferung an",
   „Adresse de livraison" …). Das ist das starke Signal - was dort steht, ist
   die Adresse, an die die Ware geht.
2. **Im ganzen Dokument**, falls kein Anker vorkommt. Dann zählt nur ein
   eindeutiger Treffer.
"""

from dataclasses import dataclass
import re
import unicodedata

# Textanker, hinter denen eine Lieferadresse steht (DE/FR/EN, wie sie auf
# Schweizer Lieferantenbelegen vorkommen). Bewusst ganze Wörter, damit
# „Lieferschein" nicht als „Liefer…"-Anker durchgeht.
ANKER = (
    "lieferadresse",
    "lieferanschrift",
    "lieferort",
    "lieferung an",
    "liefern an",
    "warenempfanger",  # ohne Umlaut, siehe _normalisiert()
    "versandadresse",
    "versand an",
    "adresse de livraison",
    "livraison a",
    "delivery address",
    "deliver to",
    "ship to",
    "shipping address",
)

# Wie weit hinter dem Anker noch zur Adresse gehört. Grosszügig, weil zwischen
# Anker und Ort oft Firmenname, Zusatz und Strasse stehen - aber klein genug,
# dass nicht der halbe Beleg mitgelesen wird.
ANKER_FENSTER = 200

# Punkte je Merkmal: die Postleitzahl ist das schärfste Signal (eindeutig je
# Ort), Ortsname und ein eigener Lagerort-Name („GEWA", „VEBO") sind fast so gut, der
# Strassenname ist nur eine Bestätigung. MINDESTPUNKTE sorgt dafür, dass eine
# Strasse allein nie genügt: „Industriestrasse" steht bei SF1 *und* SF3 im
# Adressfeld - und auf dem Briefkopf vieler Lieferanten.
PUNKTE = {"plz": 3, "ort": 2, "name": 2, "strasse": 1}
MINDESTPUNKTE = 2

# Umlaute werden auf Belegen mal als „ä", mal als „ae" geschrieben (die
# Sportfabrik selbst schreibt „haegendorf@sportfabrik.ch"). Beim Suchen sind
# darum beide Schreibweisen erlaubt.
_UMLAUTE = {"ä": "(?:a|ae)", "ö": "(?:o|oe)", "ü": "(?:u|ue)"}


@dataclass(frozen=True)
class LagerortAdresse:
    """Die Felder eines Lagerorts, die für die Erkennung gebraucht werden -
    absichtlich keine ORM-Instanz, damit die Logik ohne Datenbank testbar
    bleibt (siehe `app/services/lagerorte.py`, `lade_adressen()`)."""

    id: int
    code: str
    name: str
    strasse: str | None = None
    plz: str | None = None
    ort: str | None = None


@dataclass(frozen=True)
class Treffer:
    lagerort: LagerortAdresse
    merkmale: tuple[str, ...]
    aus_lieferadresse: bool


def _normalisiert(text: str) -> str:
    """Kleinschreibung, Umlaute/Akzente weg, Mehrfach-Leerzeichen zu einem.

    Damit greifen Vergleiche auch dann, wenn ein Beleg „Haegendorf" statt
    „Hägendorf" schreibt oder die Texterkennung einen Akzent verliert - beides
    kommt auf Lieferantendokumenten vor.
    """
    ohne_akzente = "".join(
        zeichen
        for zeichen in unicodedata.normalize("NFKD", text.replace("ß", "ss"))
        if not unicodedata.combining(zeichen)
    )
    return re.sub(r"\s+", " ", ohne_akzente.lower())


def _muster(wort: str) -> str:
    """Suchmuster für ein Wort: Bindestriche und Leerzeichen sind
    austauschbar, Umlaute auch als „ae"/„oe"/„ue" erlaubt. So findet
    „Urtenen-Schönbühl" auch „Urtenen Schoenbuehl"."""
    zeichen = []
    for buchstabe in wort.lower():
        if buchstabe in _UMLAUTE:
            zeichen.append(_UMLAUTE[buchstabe])
        elif buchstabe in " -":
            zeichen.append(r"[\s-]+")
        else:
            zeichen.append(re.escape(_normalisiert(buchstabe)))
    # Mehrere Trennzeichen hintereinander zu einem zusammenfassen.
    muster = re.sub(r"(?:\[\\s-\]\+)+", r"[\\s-]+", "".join(zeichen))
    return r"(?<![0-9a-z])" + muster.strip() + r"(?![0-9a-z])"


def _enthaelt_wort(text: str, wort: str) -> bool:
    """`wort` als eigenständiges Wort im (normalisierten) `text`."""
    if not wort or not wort.strip():
        return False
    return re.search(_muster(wort.strip()), text) is not None


def _strassenname(strasse: str) -> str:
    """Nur der Name ohne Hausnummer und Zusatz: „Industriestrasse West 40/42"
    → „industriestrasse west". Die Hausnummer bleibt weg, weil sie auf Belegen
    oft abweichend geschrieben wird (40/42, 40-42, 40)."""
    ohne_nummer = re.split(r"\b\d", _normalisiert(strasse), maxsplit=1)[0]
    return ohne_nummer.strip(" ,.-")


# Wörter, die im Namen eines Lagerorts stehen können, ihn aber nicht
# unterscheiden - „Lager Dietikon" darf nicht dazu führen, dass jeder Beleg mit
# dem Wort „Lager" dort landet.
_ALLERWELTSWOERTER = frozenset(
    {"lager", "filiale", "externes", "externe", "extern", "verarbeitung", "sportfabrik"}
)


def _kennwort(lagerort: LagerortAdresse) -> str:
    """Das erste unterscheidende Wort des Lagerort-Namens, sonst „".

    Bei GEWA und VEBO steht auf Belegen oft nur der Name ohne Adresse - der ist
    dann das einzige Signal. Bei den Filialen ist der Name gleich dem Ort und
    bringt nichts Neues, bei „Lager Dietikon" ebenso (nur eben ein Wort
    später). Allerweltswörter zählen nie, sonst erzeugen sie Fehltreffer."""
    if not lagerort.name:
        return ""
    ort = _normalisiert(lagerort.ort or "")
    for wort in re.split(r"[\s(,/]+", lagerort.name.strip()):
        normalisiert = _normalisiert(wort)
        if len(wort) < 3 or normalisiert == ort or normalisiert in _ALLERWELTSWOERTER:
            continue
        return wort
    return ""


def _merkmale(text: str, lagerort: LagerortAdresse) -> tuple[str, ...]:
    treffer = []
    if lagerort.plz and _enthaelt_wort(text, lagerort.plz):
        treffer.append("plz")
    if lagerort.ort and _enthaelt_wort(text, lagerort.ort):
        treffer.append("ort")
    if lagerort.strasse and _enthaelt_wort(text, _strassenname(lagerort.strasse)):
        treffer.append("strasse")
    if _enthaelt_wort(text, _kennwort(lagerort)):
        treffer.append("name")
    return tuple(treffer)


def _bewertet(text: str, lagerorte) -> list[tuple[int, tuple[str, ...], LagerortAdresse]]:
    """Alle Lagerorte mit mindestens einem Merkmal, bestbewertete zuerst."""
    bewertet = []
    for lagerort in lagerorte:
        merkmale = _merkmale(text, lagerort)
        if merkmale:
            bewertet.append((sum(PUNKTE[m] for m in merkmale), merkmale, lagerort))
    return sorted(bewertet, key=lambda eintrag: -eintrag[0])


def _eindeutig(text: str, lagerorte, aus_lieferadresse: bool) -> Treffer | None:
    bewertet = _bewertet(text, lagerorte)
    if not bewertet or bewertet[0][0] < MINDESTPUNKTE:
        return None
    if len(bewertet) > 1 and bewertet[0][0] == bewertet[1][0]:
        # Gleichstand: nicht raten (siehe Modul-Docstring).
        return None
    punkte, merkmale, lagerort = bewertet[0]
    return Treffer(
        lagerort=lagerort, merkmale=merkmale, aus_lieferadresse=aus_lieferadresse
    )


def lieferadress_abschnitte(text: str) -> list[str]:
    """Textstücke hinter den Lieferadress-Ankern (bereits normalisiert)."""
    normalisiert = _normalisiert(text)
    abschnitte = []
    for anker in ANKER:
        for fund in re.finditer(re.escape(anker), normalisiert):
            abschnitte.append(normalisiert[fund.end() : fund.end() + ANKER_FENSTER])
    return abschnitte


def erkenne_lagerort(text: str, lagerorte) -> Treffer | None:
    """Vorgeschlagener Lagerort für ein Dokument, oder `None`.

    `lagerorte` ist eine Folge von `LagerortAdresse`. Zuerst wird im Umfeld
    eines Lieferadress-Ankers gesucht, danach im ganzen Text; in beiden Fällen
    muss das Ergebnis eindeutig sein.
    """
    if not text or not lagerorte:
        return None
    abschnitte = lieferadress_abschnitte(text)
    if abschnitte:
        treffer = _eindeutig(" ".join(abschnitte), lagerorte, aus_lieferadresse=True)
        if treffer is not None:
            return treffer
    return _eindeutig(_normalisiert(text), lagerorte, aus_lieferadresse=False)
