"""Ablauf „Beleg": hochladen → Vorschau → korrigieren → importieren → Bestand,
und „erwartet → eingetroffen" für Auftragsbestätigungen.

Deckt Regel 1–3, 5, 6, 9 und D6, D19–D22, D26 sowie C1 (Mehrlieferung) über
die echte App mit Anmeldung ab. Die Belege baut tests/testbelege.py selbst.
"""

import hashlib

from conftest import ANNA, CHEF
from sqlalchemy import func, select
from testbelege import LIEFERADRESSE_CONTHEY, hochladen, importieren, kopf, rechnung_pdf

from app.core.models import (
    Artikel,
    Bestand,
    Dokument,
    Kategorie,
    Lagerbewegung,
    Lieferant,
    Preis,
    Variante,
    Wareneingang,
)
from app.services import importer


def _anzahl(sessions, modell):
    with sessions() as session:
        return session.scalar(select(func.count()).select_from(modell))


def _bestand(sessions, lagerort_id):
    with sessions() as session:
        return sorted(
            str(menge)
            for menge in session.scalars(
                select(Bestand.menge).where(Bestand.lagerort_id == lagerort_id)
            )
        )


def test_rechnung_hochladen_korrigieren_importieren_loeschen(welt):
    client, sessions, codes = welt.client, welt.sessions, welt.codes
    pdf = rechnung_pdf(header_lines=kopf() + LIEFERADRESSE_CONTHEY)

    # Regel 9: Mitarbeiter dürfen keine Belege hochladen.
    welt.anmelden(ANNA)
    assert hochladen(client, pdf).status_code == 403
    assert importieren(client, pdf).status_code == 403

    # Vorschau: Lieferant erkannt, Lagerort aus der Lieferadresse vorgeschlagen
    # (D19), alle Lagerorte wählbar (D26), eigene Filiale zuerst.
    welt.anmelden(CHEF)
    vorschau = hochladen(client, pdf)
    assert vorschau.status_code == 200, vorschau.text
    body = vorschau.json()
    assert body["file_hash"] == hashlib.sha256(pdf).hexdigest()
    assert len(body["items"]) == 3
    assert body["lagerort_suggestion"]["code"] == "SF2"
    wahl = [eintrag["code"] for eintrag in body["lagerort_options"]]
    assert wahl[0] == "SF1"
    assert set(wahl) == {"SF1", "SF2", "SF3", "SF4", "GEWA", "VEBO", "DIETIKON"}

    # Korrektur einer Position: der Server rechnet neu, der Client liefert nur
    # Feldwerte (app/services/corrections.py).
    korrektur = '{"1": {"description": "Poloshirt Court"}}'
    geprueft = client.post(
        "/validate-preview",
        files={"file": ("beleg.pdf", pdf, "application/pdf")},
        data={"expected_hash": body["file_hash"], "corrections": korrektur},
    )
    assert geprueft.status_code == 200, geprueft.text
    assert geprueft.json()["items"][0]["description"] == "Poloshirt Court"
    unbekannt = client.post(
        "/validate-preview",
        files={"file": ("beleg.pdf", pdf, "application/pdf")},
        data={"expected_hash": body["file_hash"], "corrections": '{"1": {"preis": "1"}}'},
    )
    assert unbekannt.status_code == 422

    # Ohne Bestätigung kein Import.
    assert importieren(client, pdf, confirmed="false").status_code == 400

    # Import auf den vorgeschlagenen Lagerort SF2.
    antwort = importieren(client, pdf, lagerort_id=str(codes["SF2"]), corrections=korrektur)
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["invoice_number"] == "9001759392"
    assert antwort.json()["item_count"] == 3

    with sessions() as session:
        dokument = session.scalar(select(Dokument))
        assert dokument.typ == "rechnung"
        assert dokument.lagerort_id == codes["SF2"]
        assert str(dokument.dokumentdatum) == "2026-08-05"
        assert session.get(Lieferant, dokument.lieferant_id).name == "INTERSPORT Schweiz AG"
        wareneingang = session.scalar(select(Wareneingang))
        assert wareneingang.status == "eingetroffen"
        assert str(wareneingang.eingangsdatum) == "2026-08-05"
        # Gleiche Marke + Lieferanten-Artikelnummer = ein Artikel, zwei Varianten.
        artikel = session.scalars(select(Artikel).order_by(Artikel.lieferanten_artikelnr)).all()
        assert [a.lieferanten_artikelnr for a in artikel] == ["A1", "B2"]
        assert artikel[0].bezeichnung == "Poloshirt Court"
        # Kategorie aus dem FEDAS-Code.
        kategorien = [session.get(Kategorie, a.kategorie_id) for a in artikel]
        assert [(k.hauptgruppe, k.sportbereich) for k in kategorien] == [
            ("Textil", "Tennis"),
            ("Schuhe", "Tennis"),
        ]
    # Regel 2: jede Bestandsänderung ist eine Lagerbewegung.
    assert _anzahl(sessions, Lagerbewegung) == 3
    assert _bestand(sessions, codes["SF2"]) == ["2.00", "3.00", "5.00"]
    assert _bestand(sessions, codes["SF1"]) == []

    # Dieselbe Datei nicht zweimal, und die Datei muss zur Vorschau passen.
    assert importieren(client, pdf, lagerort_id=str(codes["SF2"])).status_code == 409
    anders = rechnung_pdf(header_lines=kopf(nummer="9001759399"))
    falscher_hash = client.post(
        "/import-invoice",
        files={"file": ("beleg.pdf", anders, "application/pdf")},
        data={"expected_hash": body["file_hash"], "confirmed": "true"},
    )
    assert falscher_hash.status_code == 409

    # Belegliste und Detail sind für alle lesbar (F3).
    welt.anmelden(ANNA)
    liste = client.get("/api/invoices").json()
    assert len(liste["items"]) == 1
    beleg_id = liste["items"][0]["id"]
    assert client.get(f"/api/invoices/{beleg_id}").status_code == 200
    assert client.delete(f"/api/invoices/{beleg_id}").status_code == 403

    # Löschen: Beleg, Wareneingang und Buchungen weg, Artikelstamm bleibt (Regel 4).
    welt.anmelden(CHEF)
    assert client.delete(f"/api/invoices/{beleg_id}").status_code == 200
    assert _anzahl(sessions, Dokument) == 0
    assert _anzahl(sessions, Lagerbewegung) == 0
    assert _bestand(sessions, codes["SF2"]) == []
    assert _anzahl(sessions, Variante) == 3


def test_rechnung_an_externes_lager_hat_kein_eingangsdatum(welt):
    """Regel 6/D13: Ware an GEWA/VEBO/Dietikon bekommt noch kein Datum."""
    welt.anmelden(CHEF)
    pdf = rechnung_pdf()
    antwort = importieren(welt.client, pdf, lagerort_id=str(welt.codes["GEWA"]))
    assert antwort.status_code == 200, antwort.text
    with welt.sessions() as session:
        wareneingang = session.scalar(select(Wareneingang))
        assert wareneingang.lagerort_id == welt.codes["GEWA"]
        assert wareneingang.eingangsdatum is None
    assert _bestand(welt.sessions, welt.codes["GEWA"]) == ["2.00", "3.00", "5.00"]


def test_auftragsbestaetigung_erwartet_dann_teilweise_und_mehr_eingetroffen(welt, monkeypatch):
    """Regel 3/D6: eine Auftragsbestätigung bucht keinen Bestand. Die Filiale
    bestätigt die Ankunft - auch Mitarbeiter (D21). Restmengen bleiben offen
    (D22), Mehrlieferung wird gewarnt und trotzdem gebucht (C1)."""
    client, sessions, codes = welt.client, welt.sessions, welt.codes
    # Der Intersport-Parser kennt nur Rechnungen; die Auftragsbestätigungs-
    # Layouts folgen mit den weiteren Parsern.
    original = importer.parse_with_parser
    monkeypatch.setattr(
        importer,
        "parse_with_parser",
        lambda *args, **kwargs: {**original(*args, **kwargs), "document_type": "auftragsbestaetigung"},
    )
    welt.anmelden(CHEF)
    antwort = importieren(client, rechnung_pdf(), lagerort_id=str(codes["SF1"]))
    assert antwort.status_code == 200, antwort.text
    assert _bestand(sessions, codes["SF1"]) == []
    assert _anzahl(sessions, Lagerbewegung) == 0

    welt.anmelden(ANNA)
    offen = client.get("/api/wareneingaenge").json()["wareneingaenge"]
    assert len(offen) == 1 and offen[0]["dokument"]["typ"] == "auftragsbestaetigung"
    wareneingang_id = offen[0]["id"]
    polo_m, polo_l, schuh = [p["id"] for p in offen[0]["positionen"]]

    # Teillieferung: 4 von 5 Poloshirts M.
    teil = client.post(
        f"/api/wareneingaenge/{wareneingang_id}/ankunft",
        json={"mengen": {str(polo_m): "4"}, "eingangsdatum": "2026-08-07"},
    )
    assert teil.status_code == 200, teil.text
    assert teil.json()["status"] == "erwartet"
    assert teil.json()["eingangsdatum"] == "2026-08-07"
    assert _bestand(sessions, codes["SF1"]) == ["4.00"]
    rest = client.get("/api/wareneingaenge").json()["wareneingaenge"][0]["positionen"]
    assert [p["menge_offen"] for p in rest] == ["1.00", "3.00", "2.00"]

    # Ungültiges Datum wird abgelehnt.
    assert client.post(
        f"/api/wareneingaenge/{wareneingang_id}/ankunft",
        json={"mengen": {str(polo_l): "1"}, "eingangsdatum": "kein-datum"},
    ).status_code == 422

    # Rest plus ein Stück zu viel: Warnung, trotzdem gebucht, Eingang erledigt.
    fertig = client.post(
        f"/api/wareneingaenge/{wareneingang_id}/ankunft",
        json={"mengen": {str(polo_m): "2", str(polo_l): "3", str(schuh): "2"}},
    )
    assert fertig.status_code == 200, fertig.text
    assert fertig.json()["status"] == "eingetroffen"
    assert [m["menge_zuviel"] for m in fertig.json()["mehrlieferungen"]] == ["1.00"]
    assert _bestand(sessions, codes["SF1"]) == ["2.00", "3.00", "6.00"]
    assert client.get("/api/wareneingaenge").json()["wareneingaenge"] == []
    assert _anzahl(sessions, Lagerbewegung) == 4


def test_positionen_ohne_ean_und_kategorie_von_hand(welt):
    """Regel 5: ohne EAN ist der Schlüssel Artikelnummer + Farbe + Grösse;
    eine unleserliche EAN sperrt den Import, bis sie korrigiert ist.
    B8: eine von Hand gewählte Kategorie überschreibt kein späterer Import."""
    client, sessions = welt.client, welt.sessions
    ohne_ean = ["Nike", "224100", "A1", "9988770010", "", "Poloshirt", "5", "Stk", "49.90", "30.00"]
    kaputt = ohne_ean[:4] + ["40066"] + ohne_ean[5:]
    variante = lambda text: ["", "", "", "", "", text, "", "", "", ""]  # noqa: E731

    welt.anmelden(CHEF)
    erste = rechnung_pdf(
        header_lines=kopf(nummer="9000000001"),
        rows=[ohne_ean, variante("(Weiss)/M"), ohne_ean, variante("(Weiss)/L"), ohne_ean, variante("(Weiss)/M")],
    )
    vorschau = hochladen(client, erste).json()
    assert vorschau["rows_with_warnings"] == 0 and vorschau["rows_with_hints"] == 3
    assert importieren(client, erste).status_code == 200
    with sessions() as session:
        varianten = session.scalars(select(Variante).order_by(Variante.id)).all()
        assert [(v.farbe, v.groesse, v.ean) for v in varianten] == [("Weiss", "M", None), ("Weiss", "L", None)]
    assert _bestand(sessions, welt.codes["SF1"]) == ["10.00", "5.00"]

    # Kategorie von Hand: Schuhe statt des FEDAS-Vorschlags Textil.
    kategorien = client.get("/api/kategorien").json()["items"]
    schuhe = next(k["id"] for k in kategorien if (k["hauptgruppe"], k["sportbereich"]) == ("Schuhe", "Tennis"))
    assert client.put(f"/api/articles/{varianten[0].id}/kategorie", json={"kategorie_id": schuhe}).status_code == 200

    # Zweiter Beleg: unleserliche EAN sperrt, nach Korrektur geht es; die
    # Kategorie von Hand bleibt.
    zweite = rechnung_pdf(header_lines=kopf(nummer="9000000002"), rows=[kaputt, variante("(Weiss)/M")])
    assert hochladen(client, zweite).json()["rows_with_warnings"] == 1
    assert importieren(client, zweite).status_code == 409
    antwort = importieren(client, zweite, corrections='{"1": {"ean": ""}}')
    assert antwort.status_code == 200, antwort.text
    assert _anzahl(sessions, Variante) == 2
    with sessions() as session:
        artikel = session.scalar(select(Artikel))
        assert artikel.kategorie_id == schuhe and artikel.kategorie_manuell is True


def test_ecom_retoure_und_einkaufspreis(welt):
    """ECOM-Retouren kommen im INTERSPORT-Layout, erkennbar an der Referenz
    „ret.Ecom" - sie gehören zur Gruppe ECOM (Code 555, 23.09.2026). Regel 10:
    der Einkaufspreis (Spalte „Preis") wird gespeichert, wenn er dasteht."""
    client, sessions = welt.client, welt.sessions
    welt.anmelden(CHEF)
    retoure = rechnung_pdf(header_lines=kopf(nummer="9000000011") + [[(30, "Referenz"), (200, "SCH-SF"), (260, "ret.Ecom")]])
    assert hochladen(client, retoure).json()["supplier_name"] == "ECOM (Retouren Intersport-Onlineshop)"
    assert importieren(client, retoure).status_code == 200
    normal = rechnung_pdf(header_lines=kopf(nummer="9000000012"), rows=[["Nike", "224100", "C3", "1", "4006381333931", "Hoodie", "1", "Stk", "89.90", "45.00"]])
    assert importieren(client, normal).status_code == 200
    with sessions() as session:
        lieferanten = {
            d.dokumentnummer: session.get(Lieferant, d.lieferant_id).typ for d in session.scalars(select(Dokument))
        }
        assert lieferanten == {"9000000011": "ecom", "9000000012": "intersport"}
        assert sorted(str(p.ek) for p in session.scalars(select(Preis))) == ["30.00", "30.00", "45.00", "80.00"]
    polo = client.get("/api/erfassen/variante?ean=4006632041234").json()["variante"]["varianten_id"]
    assert client.get(f"/api/varianten/{polo}/etikett").json()["lieferant_code"] == "555"
