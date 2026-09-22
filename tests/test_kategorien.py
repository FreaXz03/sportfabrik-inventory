"""Kassenkategorie von Hand wählen (Phase B, Teilaufgabe B8 — Regel 4, 7, 8,
9/D21).

Geprüft wird der ganze Weg: der Dienst selbst (Auswahlliste in
Kassenreihenfolge, setzen, leeren, nie überschreiben), die API, die die
Oberfläche geht, die Kategorie bei der manuellen Erfassung (dort gibt es
keinen FEDAS-Code) und die Artikelsuche, über die man die Artikel *ohne*
Kategorie überhaupt erst findet.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.core.database as database
from app.core.database import Base, get_session
from app.core.i18n import translate
from app.core.kategorien import (
    HAUPTGRUPPEN_MIT_SPORTBEREICH,
    HAUPTGRUPPEN_OHNE_SPORTBEREICH,
    KATEGORIEN_SEED,
    SPORTBEREICHE,
    seed_kategorien,
)
from app.core.lagerorte import seed_lagerorte
from app.core.lieferanten import seed_lieferanten
from app.core.models import (
    Artikel,
    BenutzerLagerort,
    Kategorie,
    Lagerort,
    User,
    Variante,
)
from app.main import app
from app.services.kategorien import (
    KategorieError,
    KategorieNichtGefunden,
    artikel_kategorie,
    kategorie_vorschlag,
    liste_kategorien,
    merke_kategorie,
    setze_kategorie,
)
from app.services.manuelle_erfassung import ErfassungRejected, erfasse_wareneingang

BENUTZER = {"kassennummer": "910141", "name": "Anna"}

# Aus echten Rechnungen bestätigt (app/core/fedas.py): 2 = Textil, 24 = Tennis.
FEDAS_BEKANNT = "224100"
FEDAS_UNBEKANNT = "999999"


def _kategorie_id(session, hauptgruppe, sportbereich):
    return session.scalar(
        select(Kategorie.id).where(
            Kategorie.hauptgruppe == hauptgruppe,
            Kategorie.sportbereich == sportbereich,
        )
    )


@pytest.fixture
def daten():
    """Drei Artikel, wie sie im Betrieb vorkommen: mit Vorschlag aus dem
    FEDAS-Code, ganz ohne Code (manuell erfasst) und mit unbekanntem Code."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    with sessions.begin() as session:
        seed_lagerorte(session)
        seed_lieferanten(session)
        seed_kategorien(session)
        session.flush()
        sf1 = session.scalar(select(Lagerort.id).where(Lagerort.code == "SF1"))
        benutzer = User(
            kassennummer="910141", name="Anna", role="mitarbeiter", password_hash=None
        )
        session.add(benutzer)
        session.flush()
        session.add(
            BenutzerLagerort(user_id=benutzer.id, lagerort_id=sf1, ist_primaer=True)
        )

        mit_vorschlag = Artikel(
            marke="Nike",
            lieferanten_artikelnr="ABC123",
            bezeichnung="Poloshirt Court",
            fedas_code=FEDAS_BEKANNT,
            kategorie_id=_kategorie_id(session, "Textil", "Tennis"),
        )
        ohne_code = Artikel(
            marke="Puma", lieferanten_artikelnr="OHNE-1", bezeichnung="Trainerjacke"
        )
        unbekannter_code = Artikel(
            marke="Head",
            lieferanten_artikelnr="XYZ999",
            bezeichnung="Tennisschläger",
            fedas_code=FEDAS_UNBEKANNT,
        )
        session.add_all([mit_vorschlag, ohne_code, unbekannter_code])
        session.flush()
        session.add_all(
            [
                Variante(artikel_id=mit_vorschlag.id, groesse="M", ean="4006381333931"),
                Variante(artikel_id=mit_vorschlag.id, groesse="L"),
                Variante(artikel_id=ohne_code.id, ean="5901234123457"),
                Variante(artikel_id=unbekannter_code.id),
            ]
        )
    yield sessions
    engine.dispose()


@pytest.fixture
def varianten(daten):
    """Varianten-Ids je Artikel - die Oberfläche spricht Artikel über ihre
    Variante an (wie Notizen und Preise)."""
    with daten() as session:
        ids = {}
        for marke, groesse in (("Nike", "M"), ("Nike", "L"), ("Puma", None), ("Head", None)):
            artikel = session.scalar(select(Artikel).where(Artikel.marke == marke))
            variante = session.scalar(
                select(Variante).where(
                    Variante.artikel_id == artikel.id, Variante.groesse.is_(groesse)
                    if groesse is None
                    else Variante.groesse == groesse
                )
            )
            ids[(marke, groesse)] = variante.id
    return ids


@pytest.fixture
def client(daten, monkeypatch):
    def override_get_session():
        with daten() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    monkeypatch.setattr(database, "SessionLocal", daten)
    with TestClient(app) as test_client:
        test_client.post("/login", data={"kassennummer": "910141"})
        yield test_client
    app.dependency_overrides.clear()


# --- Auswahlliste (Regel 8) ------------------------------------------------


def test_liste_enthaelt_alle_kassenkategorien(daten):
    with daten() as session:
        eintraege = liste_kategorien(session)
    assert len(eintraege) == len(KATEGORIEN_SEED) == 35


def test_liste_folgt_der_kassenreihenfolge(daten):
    """Nicht alphabetisch: wer im Laden auswählt, sucht die Kategorie dort, wo
    sie auf der Kasse steht (Regel 8)."""
    with daten() as session:
        eintraege = liste_kategorien(session)
    hauptgruppen = list(dict.fromkeys(eintrag["hauptgruppe"] for eintrag in eintraege))
    assert hauptgruppen == HAUPTGRUPPEN_MIT_SPORTBEREICH + HAUPTGRUPPEN_OHNE_SPORTBEREICH
    textil = [e["sportbereich"] for e in eintraege if e["hauptgruppe"] == "Textil"]
    assert textil == SPORTBEREICHE


def test_velo_und_food_haben_keinen_sportbereich(daten):
    with daten() as session:
        eintraege = liste_kategorien(session)
    ohne = [e for e in eintraege if e["sportbereich"] is None]
    assert [e["hauptgruppe"] for e in ohne] == HAUPTGRUPPEN_OHNE_SPORTBEREICH


# --- FEDAS-Vorschlag -------------------------------------------------------


def test_vorschlag_aus_bekanntem_fedas_code(daten):
    with daten() as session:
        kategorie = kategorie_vorschlag(session, FEDAS_BEKANNT)
    assert (kategorie.hauptgruppe, kategorie.sportbereich) == ("Textil", "Tennis")


@pytest.mark.parametrize("code", [None, "", FEDAS_UNBEKANNT, "12"])
def test_kein_vorschlag_ohne_zuordnung(daten, code):
    """Genau diese Fälle sind der Grund für B8: hier muss von Hand gewählt
    werden."""
    with daten() as session:
        assert kategorie_vorschlag(session, code) is None


# --- Stand eines Artikels --------------------------------------------------


def test_stand_zeigt_vorschlag_als_nicht_manuell(daten, varianten):
    with daten() as session:
        stand = artikel_kategorie(session, varianten[("Nike", "M")])
    assert stand["kategorie"]["hauptgruppe"] == "Textil"
    assert stand["kategorie"]["sportbereich"] == "Tennis"
    assert stand["manuell"] is False
    assert stand["fedas_code"] == FEDAS_BEKANNT
    assert stand["vorschlag"]["id"] == stand["kategorie"]["id"]


def test_stand_ohne_kategorie_und_ohne_code(daten, varianten):
    with daten() as session:
        stand = artikel_kategorie(session, varianten[("Puma", None)])
    assert stand["kategorie"] is None
    assert stand["manuell"] is False
    assert stand["fedas_code"] is None
    assert stand["vorschlag"] is None


def test_stand_bei_unbekanntem_code(daten, varianten):
    with daten() as session:
        stand = artikel_kategorie(session, varianten[("Head", None)])
    assert stand["kategorie"] is None
    assert stand["fedas_code"] == FEDAS_UNBEKANNT
    assert stand["vorschlag"] is None


def test_unbekannte_variante_wird_gemeldet(daten):
    with daten() as session:
        with pytest.raises(KategorieNichtGefunden):
            artikel_kategorie(session, 999999)


# --- Von Hand setzen -------------------------------------------------------


def test_setzen_merkt_die_wahl(daten, varianten):
    with daten() as session:
        ziel = _kategorie_id(session, "Hartware", "Winter")
        stand = setze_kategorie(session, varianten[("Puma", None)], ziel)
    assert stand["kategorie"]["id"] == ziel
    assert stand["manuell"] is True
    with daten() as session:
        artikel = session.scalar(select(Artikel).where(Artikel.marke == "Puma"))
        assert artikel.kategorie_id == ziel
        assert artikel.kategorie_manuell is True


def test_wahl_von_hand_korrigiert_einen_falschen_vorschlag(daten, varianten):
    """Die FEDAS-Tabelle ist noch nicht vollständig bestätigt - ein Vorschlag
    muss sich von Hand überschreiben lassen."""
    with daten() as session:
        ziel = _kategorie_id(session, "Schuhe", "Running")
        stand = setze_kategorie(session, varianten[("Nike", "M")], ziel)
    assert stand["kategorie"]["id"] == ziel
    assert stand["manuell"] is True
    # Der FEDAS-Code selbst bleibt unangetastet - er steht so auf dem Beleg.
    assert stand["fedas_code"] == FEDAS_BEKANNT
    assert stand["vorschlag"]["sportbereich"] == "Tennis"


def test_kategorie_gilt_fuer_alle_varianten_des_artikels(daten, varianten):
    """Regel 4: der Artikelstamm ist filialübergreifend - und die Kategorie
    hängt am Modell, nicht an Farbe oder Grösse."""
    with daten() as session:
        ziel = _kategorie_id(session, "Textil", "Kids")
        setze_kategorie(session, varianten[("Nike", "M")], ziel)
    with daten() as session:
        stand = artikel_kategorie(session, varianten[("Nike", "L")])
    assert stand["kategorie"]["id"] == ziel


def test_leeren_macht_den_artikel_wieder_offen(daten, varianten):
    with daten() as session:
        setze_kategorie(session, varianten[("Nike", "M")], None)
    with daten() as session:
        artikel = session.scalar(select(Artikel).where(Artikel.marke == "Nike"))
        assert artikel.kategorie_id is None
        assert artikel.kategorie_manuell is False


def test_unbekannte_kategorie_aendert_nichts(daten, varianten):
    with daten() as session:
        with pytest.raises(KategorieError):
            setze_kategorie(session, varianten[("Puma", None)], 999999)
    with daten() as session:
        artikel = session.scalar(select(Artikel).where(Artikel.marke == "Puma"))
        assert artikel.kategorie_id is None


def test_setzen_an_unbekannter_variante(daten):
    with daten() as session:
        with pytest.raises(KategorieNichtGefunden):
            setze_kategorie(session, 999999, 1)


def test_merke_kategorie_ueberschreibt_nie(daten):
    """Der Baustein für nebenbei entstehende Artikel (Import/Erfassung):
    füllt nur, was leer ist."""
    with daten() as session:
        nike = session.scalar(select(Artikel).where(Artikel.marke == "Nike"))
        puma = session.scalar(select(Artikel).where(Artikel.marke == "Puma"))
        vorher = nike.kategorie_id
        anders = _kategorie_id(session, "Schuhe", "Outdoor")
        assert merke_kategorie(nike, anders) is False
        assert nike.kategorie_id == vorher
        assert nike.kategorie_manuell is False
        assert merke_kategorie(puma, anders) is True
        assert puma.kategorie_id == anders
        assert puma.kategorie_manuell is True
        assert merke_kategorie(puma, None) is False


# --- API -------------------------------------------------------------------


def test_api_liefert_die_auswahlliste(client):
    antwort = client.get("/api/kategorien")
    assert antwort.status_code == 200
    eintraege = antwort.json()["items"]
    assert len(eintraege) == 35
    assert eintraege[0]["hauptgruppe"] == "Textil"
    assert eintraege[0]["sportbereich"] == SPORTBEREICHE[0]


def test_api_liefert_den_stand(client, varianten):
    antwort = client.get(f"/api/articles/{varianten[('Nike', 'M')]}/kategorie")
    assert antwort.status_code == 200
    assert antwort.json()["kategorie"]["sportbereich"] == "Tennis"
    assert antwort.json()["manuell"] is False


def test_api_setzt_und_leert(client, varianten, daten):
    with daten() as session:
        ziel = _kategorie_id(session, "Velo", None)
    ziel_variante = varianten[("Puma", None)]
    antwort = client.put(
        f"/api/articles/{ziel_variante}/kategorie", json={"kategorie_id": ziel}
    )
    assert antwort.status_code == 200
    assert antwort.json()["kategorie"] == {
        "id": ziel,
        "hauptgruppe": "Velo",
        "sportbereich": None,
    }
    assert antwort.json()["manuell"] is True

    antwort = client.put(
        f"/api/articles/{ziel_variante}/kategorie", json={"kategorie_id": None}
    )
    assert antwort.status_code == 200
    assert antwort.json()["kategorie"] is None
    assert antwort.json()["manuell"] is False


def test_api_mitarbeiter_darf_kategorie_pflegen(client, varianten, daten):
    """Regel 9/D21: Artikelstamm pflegen ist kein Dokumenten-Upload."""
    assert client.get("/api/me").json()["role"] == "mitarbeiter"
    with daten() as session:
        ziel = _kategorie_id(session, "Hartware", "Baden")
    antwort = client.put(
        f"/api/articles/{varianten[('Head', None)]}/kategorie", json={"kategorie_id": ziel}
    )
    assert antwort.status_code == 200


def test_api_unbekannte_kategorie(client, varianten):
    antwort = client.put(
        f"/api/articles/{varianten[('Puma', None)]}/kategorie",
        json={"kategorie_id": 999999},
    )
    assert antwort.status_code == 422
    assert antwort.json()["detail"] == translate("errors.kategorie.unknown", "de")


def test_api_unbekannte_variante(client):
    assert client.get("/api/articles/999999/kategorie").status_code == 404
    antwort = client.put("/api/articles/999999/kategorie", json={"kategorie_id": 1})
    assert antwort.status_code == 404


def test_api_fremde_felder_werden_abgelehnt(client, varianten):
    antwort = client.put(
        f"/api/articles/{varianten[('Puma', None)]}/kategorie",
        json={"kategorie_id": 1, "manuell": False},
    )
    assert antwort.status_code == 422


def test_api_braucht_login(daten, monkeypatch):
    def override_get_session():
        with daten() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    monkeypatch.setattr(database, "SessionLocal", daten)
    with TestClient(app) as anonym:
        assert anonym.get("/api/kategorien").status_code == 401
        assert anonym.put("/api/articles/1/kategorie", json={}).status_code == 401
    app.dependency_overrides.clear()


# --- Manuelle Erfassung (ohne Beleg gibt es keinen FEDAS-Code) -------------


def _position(**overrides):
    return {
        "marke": "Salomon",
        "bezeichnung": "Wanderschuh",
        "menge": "2",
        "uvp": "189.00",
        **overrides,
    }


def _erfasse(daten, positionen):
    with daten() as session:
        sf1 = session.scalar(select(Lagerort.id).where(Lagerort.code == "SF1"))
    return erfasse_wareneingang(
        positionen, daten, lagerort_id=sf1, benutzer=BENUTZER
    )


def test_erfassung_setzt_die_kategorie_am_neuen_artikel(daten):
    with daten() as session:
        ziel = _kategorie_id(session, "Schuhe", "Outdoor")
    _erfasse(daten, [_position(kategorie_id=ziel)])
    with daten() as session:
        artikel = session.scalar(select(Artikel).where(Artikel.marke == "Salomon"))
        assert artikel.kategorie_id == ziel
        assert artikel.kategorie_manuell is True


def test_erfassung_ohne_kategorie_bleibt_offen(daten):
    """D23: Pflicht sind nur Marke, Bezeichnung, Menge und UVP."""
    _erfasse(daten, [_position()])
    with daten() as session:
        artikel = session.scalar(select(Artikel).where(Artikel.marke == "Salomon"))
        assert artikel.kategorie_id is None
        assert artikel.kategorie_manuell is False


def test_erfassung_traegt_kategorie_an_bekanntem_artikel_nach(daten):
    """Der Altbestand ohne Kategorie: einmal scannen, Kategorie wählen,
    fertig."""
    with daten() as session:
        ziel = _kategorie_id(session, "Textil", "Freizeit")
    _erfasse(
        daten,
        [_position(marke="Puma", bezeichnung="Trainerjacke", ean="5901234123457", kategorie_id=ziel)],
    )
    with daten() as session:
        artikel = session.scalar(select(Artikel).where(Artikel.marke == "Puma"))
        assert artikel.kategorie_id == ziel
        assert artikel.kategorie_manuell is True


def test_erfassung_ueberschreibt_bestehende_kategorie_nicht(daten):
    with daten() as session:
        vorher = session.scalar(
            select(Artikel.kategorie_id).where(Artikel.marke == "Nike")
        )
        anders = _kategorie_id(session, "Food", None)
    _erfasse(
        daten,
        [_position(marke="Nike", bezeichnung="Poloshirt Court", ean="4006381333931", kategorie_id=anders)],
    )
    with daten() as session:
        artikel = session.scalar(select(Artikel).where(Artikel.marke == "Nike"))
        assert artikel.kategorie_id == vorher
        assert artikel.kategorie_manuell is False


def test_erfassung_lehnt_unbekannte_kategorie_ab(daten):
    with pytest.raises(ErfassungRejected) as fehler:
        _erfasse(daten, [_position(kategorie_id=999999)])
    assert str(fehler.value) == translate("errors.erfassung.kategorie_unknown", "de")
    with daten() as session:
        assert session.scalar(select(Artikel).where(Artikel.marke == "Salomon")) is None


@pytest.mark.parametrize("wert", ["abc", 0, -1, True, 1.5, {"id": 1}])
def test_erfassung_lehnt_unsinnige_kategorie_ids_ab(daten, wert):
    with pytest.raises(ErfassungRejected):
        _erfasse(daten, [_position(kategorie_id=wert)])


def test_erfassung_stammdaten_enthalten_die_kategorien(client):
    stammdaten = client.get("/api/erfassen/stammdaten").json()
    assert len(stammdaten["kategorien"]) == 35
    assert stammdaten["kategorien"][0]["hauptgruppe"] == "Textil"


def test_erfassung_scan_zeigt_die_bestehende_kategorie(client):
    antwort = client.get("/api/erfassen/variante?ean=4006381333931")
    assert antwort.status_code == 200
    assert antwort.json()["variante"]["kategorie"]["sportbereich"] == "Tennis"


def test_erfassung_ueber_die_api_mit_kategorie(client, daten):
    with daten() as session:
        ziel = _kategorie_id(session, "Hartware", "Rollsport")
    antwort = client.post(
        "/api/erfassen",
        json={"positionen": [_position(kategorie_id=ziel)], "lagerort_id": None},
    )
    assert antwort.status_code == 200, antwort.text
    with daten() as session:
        artikel = session.scalar(select(Artikel).where(Artikel.marke == "Salomon"))
        assert artikel.kategorie_id == ziel


# --- Artikelsuche: die Artikel ohne Kategorie überhaupt finden -------------


def test_artikelliste_zeigt_die_kategorie(client, varianten):
    antwort = client.get("/api/articles?brand=Nike")
    eintraege = {eintrag["id"]: eintrag for eintrag in antwort.json()["items"]}
    kategorie = eintraege[varianten[("Nike", "M")]]["kategorie"]
    assert (kategorie["hauptgruppe"], kategorie["sportbereich"]) == ("Textil", "Tennis")
    assert eintraege[varianten[("Nike", "L")]]["kategorie"] is not None


def test_filter_ohne_kategorie(client, varianten):
    antwort = client.get("/api/articles?kategorie_fehlt=true")
    ids = {eintrag["id"] for eintrag in antwort.json()["items"]}
    assert ids == {varianten[("Puma", None)], varianten[("Head", None)]}
    assert all(eintrag["kategorie"] is None for eintrag in antwort.json()["items"])


def test_filter_nach_einer_kategorie(client, varianten, daten):
    with daten() as session:
        ziel = _kategorie_id(session, "Textil", "Tennis")
    antwort = client.get(f"/api/articles?kategorie_id={ziel}")
    ids = {eintrag["id"] for eintrag in antwort.json()["items"]}
    assert ids == {varianten[("Nike", "M")], varianten[("Nike", "L")]}


def test_filter_ohne_kategorie_sticht_die_einzelne_kategorie(client, varianten, daten):
    """Beides gesetzt: „ohne Kategorie" gewinnt - sonst käme eine leere Liste
    zurück, und niemand wüsste warum."""
    with daten() as session:
        ziel = _kategorie_id(session, "Textil", "Tennis")
    antwort = client.get(f"/api/articles?kategorie_fehlt=true&kategorie_id={ziel}")
    ids = {eintrag["id"] for eintrag in antwort.json()["items"]}
    assert ids == {varianten[("Puma", None)], varianten[("Head", None)]}


def test_kategorie_taucht_nach_dem_setzen_in_der_suche_auf(client, varianten, daten):
    with daten() as session:
        ziel = _kategorie_id(session, "Schuhe", "Winter")
    client.put(
        f"/api/articles/{varianten[('Puma', None)]}/kategorie", json={"kategorie_id": ziel}
    )
    ids = {
        eintrag["id"] for eintrag in client.get("/api/articles?kategorie_fehlt=true").json()["items"]
    }
    assert ids == {varianten[("Head", None)]}
