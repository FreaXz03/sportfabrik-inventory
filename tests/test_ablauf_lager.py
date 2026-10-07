"""Ablauf „Lager": Ware kommt über GEWA in die Filialen, wird zwischen
Filialen umgelagert, verkauft/ausgebucht, rückgängig gemacht und gezählt;
Bestandsansicht, Ausbuchungsliste und Übersicht zeigen das Ergebnis.

Deckt Phase C (C2–C5), Regel 2, 6, 9 sowie D13, D17, F9–F11, F14, F15 über
die echte App mit Anmeldung ab.
"""

from datetime import date, timedelta
from decimal import Decimal

from conftest import ANNA, CHEF, ZENTRALE
from sqlalchemy import func, select, update
from testbelege import POSITIONEN, importieren, kopf, rechnung_pdf

from app.core.i18n import translate
from app.core.models import Bestand, Lagerbewegung, Variante, WareneingangPosition
from app.services.reduktion import letzter_wareneingang
from app.services.uebersicht import aktuelles

POLO_M = "4006632041234"


def _menge(sessions, varianten_id, lagerort_id):
    with sessions() as session:
        bestand = session.get(Bestand, (varianten_id, lagerort_id))
        return None if bestand is None else bestand.menge


def _uhr(sessions, varianten_id, lagerort_id):
    """Start der Reduktionsuhr (Regel 6) für diesen Artikel in dieser Filiale."""
    with sessions() as session:
        artikel_id = session.get(Variante, varianten_id).artikel_id
        return letzter_wareneingang(session, artikel_id, lagerort_id)


def _ankommen(welt, wareneingang_id, eingangsdatum=None):
    """Ankunft einer Umlagerung komplett bestätigen (nach dem Auspacken,
    Entscheid 28.09.2026) - wie eine Lieferung, über dieselbe API."""
    with welt.sessions() as session:
        positionen = session.scalars(
            select(WareneingangPosition).where(WareneingangPosition.wareneingang_id == wareneingang_id)
        ).all()
        mengen = {str(p.id): str(p.menge) for p in positionen}
    daten = {"mengen": mengen, **({"eingangsdatum": eingangsdatum} if eingangsdatum else {})}
    antwort = welt.client.post(f"/api/wareneingaenge/{wareneingang_id}/ankunft", json=daten)
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["status"] == "eingetroffen"
    return antwort.json()


def _bestand_ist_summe_der_bewegungen(sessions):
    """Regel 2: der Bestand ist immer die Summe der Lagerbewegungen."""
    with sessions() as session:
        summen = {
            (varianten_id, lagerort_id): summe
            for varianten_id, lagerort_id, summe in session.execute(
                select(
                    Lagerbewegung.varianten_id,
                    Lagerbewegung.lagerort_id,
                    func.sum(Lagerbewegung.menge),
                ).group_by(Lagerbewegung.varianten_id, Lagerbewegung.lagerort_id)
            )
        }
        for bestand in session.scalars(select(Bestand)):
            schluessel = (bestand.varianten_id, bestand.lagerort_id)
            assert Decimal(summen.get(schluessel, 0)) == bestand.menge, schluessel


def test_gewa_filiale_umlagern_ausbuchen_zaehlen(welt):
    client, sessions, codes = welt.client, welt.sessions, welt.codes
    sf1, sf2, gewa = codes["SF1"], codes["SF2"], codes["GEWA"]

    # Lieferung an die GEWA: Bestand dort, aber noch keine Uhr (D13).
    welt.anmelden(CHEF)
    assert importieren(client, rechnung_pdf(), lagerort_id=str(gewa)).status_code == 200
    polo = client.get(f"/api/erfassen/variante?ean={POLO_M}").json()["variante"]["varianten_id"]
    assert _menge(sessions, polo, gewa) == Decimal("5")
    assert _uhr(sessions, polo, gewa) is None

    # GEWA → SF1 wie eine Lieferung (Entscheid 28.09.2026): der Filialleiter
    # versendet mit Versanddatum, die Ware ist unterwegs, die SF1 bestätigt
    # die Ankunft. Das Eingangsdatum wird erst dann gesetzt, auch rückwirkend (D13).
    welt.anmelden(CHEF)
    stamm = client.get("/api/umlagerung/stammdaten").json()
    assert stamm["quelle_aktiv"] == sf1
    antwort = client.post(
        "/api/umlagerung",
        json={
            "quelle_id": gewa,
            "ziel_id": sf1,
            "versanddatum": "2026-08-08",
            "positionen": [{"varianten_id": polo, "menge": "2"}, {"varianten_id": polo, "menge": "1"}],
        },
    )
    assert antwort.status_code == 200, antwort.text
    versand = antwort.json()
    assert versand["ziel"]["code"] == "SF1" and versand["stueck"] == "3.00"
    assert versand["versanddatum"] == "2026-08-08"
    assert _menge(sessions, polo, gewa) == Decimal("2")
    assert _menge(sessions, polo, sf1) is None  # unterwegs: noch nirgends Bestand
    erwartet = client.get("/api/wareneingaenge").json()["wareneingaenge"]
    assert [(w["id"], w["dokument"], w["umlagerung"]["von"]["code"], w["umlagerung"]["versanddatum"]) for w in erwartet] == [
        (versand["wareneingang_id"], None, "GEWA", "2026-08-08")
    ]
    assert [p["menge_erwartet"] for p in erwartet[0]["positionen"]] == ["3.00"]
    assert client.get("/api/dashboard").json()["filiale"]["erwartet_total"] == 1
    # Ankunft bestätigen darf auch die Mitarbeiterin (D21).
    welt.anmelden(ANNA)
    _ankommen(welt, versand["wareneingang_id"], "2026-08-10")
    assert _menge(sessions, polo, sf1) == Decimal("3")
    assert _uhr(sessions, polo, sf1) == date(2026, 8, 10)
    welt.anmelden(CHEF)
    # Unbekanntes Ziel, gleiches Ziel und Versand in der Zukunft werden abgelehnt.
    position = [{"varianten_id": polo, "menge": "1"}]
    assert client.post("/api/umlagerung", json={"quelle_id": gewa, "ziel_id": 999999, "positionen": position}).status_code == 404
    assert client.post("/api/umlagerung", json={"quelle_id": gewa, "ziel_id": gewa, "positionen": position}).status_code == 409
    morgen = (date.today() + timedelta(days=1)).isoformat()
    assert client.post("/api/umlagerung", json={"quelle_id": gewa, "ziel_id": sf1, "versanddatum": morgen, "positionen": position}).status_code == 409

    # SF1 → SF2, die SF2 hatte den Artikel nie: Uhr startet bei der Ankunft (F11).
    erste = client.post(
        "/api/umlagerung",
        json={"quelle_id": sf1, "ziel_id": sf2, "positionen": [{"varianten_id": polo, "menge": "1"}]},
    )
    assert erste.status_code == 200, erste.text
    assert _uhr(sessions, polo, sf2) is None
    _ankommen(welt, erste.json()["wareneingang_id"])
    assert _uhr(sessions, polo, sf2) == date.today()
    # Zweite Umlagerung: jetzt kennt die SF2 den Artikel, die Uhr bleibt (F10),
    # und das ursprüngliche Eingangsdatum reist mit (D17).
    with sessions() as session:
        session.execute(
            update(Lagerbewegung)
            .where(Lagerbewegung.lagerort_id == sf2)
            .values(eingangsdatum=date(2026, 8, 12))
        )
        session.commit()
    zweite = client.post(
        "/api/umlagerung",
        json={"quelle_id": sf1, "ziel_id": sf2, "positionen": [{"varianten_id": polo, "menge": "1"}]},
    )
    assert zweite.status_code == 200, zweite.text
    _ankommen(welt, zweite.json()["wareneingang_id"])
    assert _uhr(sessions, polo, sf2) == date(2026, 8, 12)
    with sessions() as session:
        assert session.get(Bestand, (polo, sf2)).aeltestes_eingangsdatum == date(2026, 8, 10)
    # Zu wenig an der Quelle: gemeldet, trotzdem gebucht.
    knapp = client.post(
        "/api/umlagerung",
        json={"quelle_id": sf2, "ziel_id": sf1, "positionen": [{"varianten_id": polo, "menge": "3"}]},
    )
    assert knapp.status_code == 200 and knapp.json()["fehlbestand"]
    assert _menge(sessions, polo, sf2) == Decimal("-1")
    _ankommen(welt, knapp.json()["wareneingang_id"])
    assert _menge(sessions, polo, sf1) == Decimal("4")

    # Ausbuchen per Scan: ein Scan = ein Stück (F15), Gründe nach F14.
    welt.anmelden(CHEF)
    assert client.get("/api/ausbuchen/stammdaten").json()["gruende"][0] == "verkauf"
    verkauf = client.post("/api/ausbuchen", json={"ean": POLO_M, "grund": "verkauf"})
    assert verkauf.status_code == 200, verkauf.text
    assert verkauf.json()["lagerort"]["code"] == "SF1"
    assert verkauf.json()["bestand_nachher"] == "3.00"
    for _ in range(3):
        client.post("/api/ausbuchen", json={"ean": POLO_M, "grund": "diebstahl"})
    # Zu wenig Bestand: warnen, trotzdem buchen (F9).
    minus = client.post("/api/ausbuchen", json={"ean": POLO_M, "grund": "defekt"})
    assert minus.status_code == 200 and minus.json()["bestand_reicht_nicht"] is True
    assert _menge(sessions, polo, sf1) == Decimal("-1")
    # Rückgängig ist eine Gegenbuchung, nur einmal.
    storno = client.post(f"/api/ausbuchen/{minus.json()['bewegung_id']}/storno")
    assert storno.status_code == 200
    assert client.post(f"/api/ausbuchen/{minus.json()['bewegung_id']}/storno").status_code == 409
    assert _menge(sessions, polo, sf1) == Decimal("0")
    # Fehler verständlich, nichts gebucht.
    assert client.post("/api/ausbuchen", json={"ean": POLO_M, "grund": "sonstiges"}).status_code == 409
    unbekannt = client.post("/api/ausbuchen", json={"ean": "7612345678900", "grund": "verkauf"})
    assert unbekannt.status_code == 409 and "7612345678900" in unbekannt.json()["detail"]
    sonstiges = client.post(
        "/api/ausbuchen", json={"ean": POLO_M, "grund": "sonstiges", "freitext": "Musterteil"}
    )
    assert sonstiges.status_code == 200

    # Liste der Ausbuchungen: Zeit, Person, Grund, Storno.
    liste = client.get("/api/ausbuchungen").json()
    assert liste["gewaehlt"] == sf1
    assert sorted(z["grund"] for z in liste["zeilen"]) == [
        "defekt", "diebstahl", "diebstahl", "diebstahl", "sonstiges: Musterteil", "verkauf"
    ]
    assert {z["benutzer_name"] for z in liste["zeilen"]} == {"Chef"}
    assert sum(z["storniert"] for z in liste["zeilen"]) == 1

    # Mitarbeiterin darf weiterhin die eigene Filiale zählen.
    welt.anmelden(ANNA)
    # Korrektur (C5): gezählte Menge eingeben, System bucht die Differenz.
    zaehlen = client.post(
        "/api/korrektur",
        json={"varianten_id": polo, "lagerort_id": sf1, "gezaehlt": "5", "grund": "inventur"},
    )
    assert zaehlen.status_code == 200, zaehlen.text
    assert zaehlen.json()["differenz"] == "6.00"
    assert _menge(sessions, polo, sf1) == Decimal("5")
    assert client.post(
        "/api/korrektur",
        json={"varianten_id": polo, "lagerort_id": sf1, "gezaehlt": "-3", "grund": "inventur"},
    ).status_code in (409, 422)

    # Bestandsansicht: aktive Filiale, Suche, alle Lagerorte (C2).
    eigene = client.get("/api/bestand").json()
    assert eigene["gewaehlt"] == sf1
    assert [(z["varianten_id"], z["menge"]) for z in eigene["zeilen"]] == [(polo, "5.00")]
    assert client.get("/api/bestand?q=Laufschuh").json()["zeilen"] == []
    alle = client.get("/api/bestand?alle=true").json()["zeilen"]
    assert {z["lagerort"]["code"] for z in alle} == {"SF1", "SF2", "GEWA"}
    assert any(z["lagerort"]["verkauf"] is False for z in alle)

    # Übersicht der aktiven Filiale.
    uebersicht = client.get("/api/dashboard")
    assert uebersicht.status_code == 200 and uebersicht.json()["filiale"]

    _bestand_ist_summe_der_bewegungen(sessions)

    # Ohne Anmeldung nichts.
    client.post("/logout")
    for pfad in ("/api/ausbuchen", "/api/umlagerung", "/api/korrektur"):
        assert client.post(pfad, json={}).status_code in (401, 422), pfad
    assert client.get("/api/bestand").status_code == 401
    assert client.get("/ausbuchen", follow_redirects=False).status_code == 303


def test_anstehend_fuehrt_zur_gefilterten_liste(welt):
    """Inbox 24.09.2026: ein Klick auf einen Punkt unter „Anstehend" zeigt
    genau die gezählten Einträge. Darum muss jede Zahl der Übersicht gleich
    der Trefferzahl der verlinkten, gefilterten Liste sein."""
    client, codes = welt.client, welt.codes
    heute = date.today()
    vor_40_monaten = date(heute.year - 3, heute.month, 1) - timedelta(days=150)  # > 36 Monate
    vor_20_monaten = date(heute.year - 2, heute.month, 1) + timedelta(days=150)  # 18–36 Monate
    welt.anmelden(CHEF)
    alt = rechnung_pdf(header_lines=kopf(nummer="9000000021", datum=vor_40_monaten.strftime("%d.%m.%Y")), rows=POSITIONEN[:2])
    mittel = rechnung_pdf(header_lines=kopf(nummer="9000000022", datum=vor_20_monaten.strftime("%d.%m.%Y")), rows=POSITIONEN[2:])
    assert importieren(client, alt, lagerort_id=str(codes["SF1"])).status_code == 200
    assert importieren(client, mittel, lagerort_id=str(codes["SF1"])).status_code == 200
    # Von Hand: ohne EAN und ohne Kategorie; eine Variante ins Minus.
    client.post("/api/erfassen", json={"positionen": [{"marke": "CMP", "bezeichnung": "Jacke", "menge": "1", "uvp": "99"}]})
    for _ in range(6):
        client.post("/api/ausbuchen", json={"ean": POLO_M, "grund": "verkauf"})

    uebersicht = client.get("/api/dashboard").json()
    filiale, stamm = uebersicht["filiale"], uebersicht["stamm"]
    assert filiale["negativ"] == 1
    assert stamm["ohne_ean"] == 1 and stamm["ohne_kategorie"] == 1
    assert filiale["reduktionen"]["70"]["faellig"] == 1  # Poloshirt L (M ist negativ)
    assert filiale["reduktionen"]["50"]["faellig"] == 1  # Laufschuh

    def treffer(pfad):
        antwort = client.get(pfad)
        assert antwort.status_code == 200, (pfad, antwort.text)
        return antwort.json()["total"]

    assert treffer("/api/articles?ohne_ean=true") == stamm["ohne_ean"]
    assert treffer("/api/articles?kategorie_fehlt=true") == stamm["ohne_kategorie"]
    assert treffer("/api/bestand?nur_negativ=true") == filiale["negativ"]

    # Entscheid 29.09.2026: „ohne EAN" und „ohne Kategorie" zählen den ganzen
    # Stamm, für alle Rollen in jeder Filiale; Liste und Zahl stimmen überein.
    client.post("/api/erfassen", json={"lagerort_id": codes["SF2"], "positionen": [{"marke": "CMP", "bezeichnung": "Weste", "menge": "1", "uvp": "59"}]})
    for konto in (CHEF, ANNA, ZENTRALE):
        welt.anmelden(konto)
        stamm = client.get("/api/dashboard").json()["stamm"]
        assert stamm["ohne_ean"] == 2 and stamm["ohne_kategorie"] == 2, konto
        assert treffer("/api/articles?ohne_ean=true") == 2
        assert treffer("/api/articles?kategorie_fehlt=true") == 2
    welt.anmelden(CHEF)
    for stufe in ("50", "70"):
        for stand in ("faellig", "bald"):
            pfad = f"/api/bestand?reduktion={stufe}&reduktion_status={stand}"
            assert treffer(pfad) == filiale["reduktionen"][stufe][stand], pfad
    zeilen = client.get("/api/bestand?reduktion=50&reduktion_status=faellig").json()["zeilen"]
    assert [z["bezeichnung"] for z in zeilen] == ["Laufschuh"]
    assert client.get("/api/bestand?reduktion=40&reduktion_status=faellig").status_code == 422


def test_aktuelles_fasst_lieferungen_und_umlagerungen_zusammen(welt):
    """Anforderung 8 (24.09.2026): Aktuelles zeigt eine Lieferung als ganze
    Lieferung und eine Umlagerung als einen Eintrag, dazu Abgänge mit anderem
    Grund als Verkauf - keine einzelnen Verkäufe, Zugänge oder Korrekturen."""
    client, codes = welt.client, welt.codes
    sf1, sf2 = codes["SF1"], codes["SF2"]
    welt.anmelden(CHEF)
    assert importieren(client, rechnung_pdf(), lagerort_id=str(sf1)).status_code == 200
    polo_m = client.get(f"/api/erfassen/variante?ean={POLO_M}").json()["variante"]["varianten_id"]
    polo_l = client.get("/api/erfassen/variante?ean=4006632041241").json()["variante"]["varianten_id"]
    versand = client.post(
        "/api/umlagerung",
        json={"quelle_id": sf1, "ziel_id": sf2, "positionen": [
            {"varianten_id": polo_m, "menge": "1"}, {"varianten_id": polo_l, "menge": "2"}]},
    )
    assert versand.status_code == 200
    assert client.post("/api/ausbuchen", json={"ean": POLO_M, "grund": "verkauf"}).status_code == 200
    assert client.post("/api/ausbuchen", json={"ean": POLO_M, "grund": "defekt"}).status_code == 200
    assert client.post(
        "/api/korrektur", json={"varianten_id": polo_l, "lagerort_id": sf1, "gezaehlt": "0", "grund": "inventur"}
    ).status_code == 200

    eintraege = client.get("/api/dashboard").json()["aktuelles"]
    assert [e["art"] for e in eintraege] == ["abgang", "umlagerung", "lieferung"]
    abgang, umlagerung, lieferung = eintraege
    assert abgang["grund"] == "defekt" and abgang["menge"] == "-1.00" and abgang["bezeichnung"] == "Poloshirt"
    assert (umlagerung["von"], umlagerung["nach"]) == ("SF1", "SF2")
    assert umlagerung["positionen"] == 2 and umlagerung["stueck"] == "3.00"
    assert lieferung["positionen"] == 3 and lieferung["stueck"] == "10.00"
    assert lieferung["dokumentnummer"] == "9001759392" and lieferung["lagerort"] == "SF1"

    # Die Zielfiliale sieht die Umlagerung erst, wenn sie angekommen ist -
    # dann als eigenen Eintrag; ohne Filiale erscheint sie einmal (nicht je Seite).
    with welt.sessions() as session:
        assert aktuelles(session, sf2) == []
    _ankommen(welt, versand.json()["wareneingang_id"])
    with welt.sessions() as session:
        in_sf2 = aktuelles(session, sf2)
        ueberall = aktuelles(session, None)
    assert [(e["art"], e["von"], e["nach"], e["stueck"]) for e in in_sf2] == [("umlagerung", "SF1", "SF2", "3.00")]
    assert [e["art"] for e in ueberall] == ["abgang", "umlagerung", "lieferung"]


def test_umlagerung_unterwegs_stornieren(welt):
    """Umlagerung unterwegs stornieren (Entscheid 29.09.2026): Filialleiter
    der Quelle, wer versendet hat, oder Zentrale. Der noch offene Rest geht an die Quelle zurück,
    mit seinem alten Datum; schon Angekommenes bleibt am Ziel."""
    client, sessions, codes = welt.client, welt.sessions, welt.codes
    sf1, sf3 = codes["SF1"], codes["SF3"]
    welt.anmelden(CHEF)
    assert importieren(client, rechnung_pdf(), lagerort_id=str(sf1)).status_code == 200
    polo = client.get(f"/api/erfassen/variante?ean={POLO_M}").json()["variante"]["varianten_id"]
    uhr_vorher = _uhr(sessions, polo, sf1)
    versand = client.post(
        "/api/umlagerung",
        json={"quelle_id": sf1, "ziel_id": sf3, "positionen": [{"varianten_id": polo, "menge": "3"}]},
    ).json()
    umlagerung_id = versand["wareneingang_id"]
    assert _menge(sessions, polo, sf1) == Decimal("2")

    # Unterwegs-Liste der Quelle zeigt die Umlagerung.
    unterwegs = client.get(f"/api/umlagerung/unterwegs?quelle_id={sf1}").json()["umlagerungen"]
    assert [u["id"] for u in unterwegs] == [umlagerung_id]

    # 1 Stück kommt an der SF3 an, der Rest ist noch unterwegs.
    with sessions() as session:
        position_id = session.scalar(
            select(WareneingangPosition.id).where(WareneingangPosition.wareneingang_id == umlagerung_id)
        )
    teil = client.post(f"/api/wareneingaenge/{umlagerung_id}/ankunft", json={"mengen": {str(position_id): "1"}})
    assert teil.status_code == 200, teil.text

    # Mitarbeiterin darf nicht stornieren (Regel 9).
    welt.anmelden(ANNA)
    assert client.post(f"/api/umlagerung/{umlagerung_id}/stornieren").status_code == 403

    # Filialleiter ohne die Quelle als eigene Filiale darf nicht.
    welt.anmelden(ZENTRALE)
    fremd = client.post(
        "/api/umlagerung",
        json={"quelle_id": sf3, "ziel_id": sf1, "positionen": [{"varianten_id": polo, "menge": "1"}]},
    ).json()["wareneingang_id"]
    welt.anmelden(CHEF)
    assert client.post(f"/api/umlagerung/{fremd}/stornieren").status_code == 403

    storno = client.post(f"/api/umlagerung/{umlagerung_id}/stornieren")
    assert storno.status_code == 200, storno.text
    assert storno.json()["stueck"] == "2.00"
    assert _menge(sessions, polo, sf1) == Decimal("4")
    # Das angekommene Stück ging nicht zurück; die Zentrale hat es oben
    # schon wieder Richtung SF1 verschickt.
    assert _menge(sessions, polo, sf3) == Decimal("0")
    assert _uhr(sessions, polo, sf1) == uhr_vorher  # keine neue Uhr an der Quelle
    assert client.get(f"/api/umlagerung/unterwegs?quelle_id={sf1}").json()["umlagerungen"] == []
    welt.anmelden(ZENTRALE)
    offen = [w["id"] for w in client.get("/api/wareneingaenge").json()["wareneingaenge"]]
    assert umlagerung_id not in offen and fremd in offen

    # Zweimal stornieren, danach ankommen oder eine Lieferung stornieren: abgelehnt.
    assert client.post(f"/api/umlagerung/{umlagerung_id}/stornieren").status_code == 409
    ankunft = client.post(
        f"/api/wareneingaenge/{umlagerung_id}/ankunft", json={"mengen": {str(position_id): "1"}}
    )
    assert ankunft.status_code == 409
    assert ankunft.json()["detail"] == translate("errors.wareneingang.cancelled", "de")
    with sessions() as session:
        lieferung = session.scalar(
            select(WareneingangPosition.wareneingang_id).where(WareneingangPosition.id != position_id).limit(1)
        )
    assert client.post(f"/api/umlagerung/{lieferung}/stornieren").status_code == 409
    # Zentrale darf jede Quelle.
    assert client.post(f"/api/umlagerung/{fremd}/stornieren").status_code == 200

    # Wer versendet hat, darf auch stornieren - auch aus einer fremden
    # Quelle (Entscheid 29.09.2026, z. B. Filialleiter versendet ab GEWA).
    welt.anmelden(CHEF)
    eigene = client.post(
        "/api/umlagerung",
        json={"quelle_id": codes["GEWA"], "ziel_id": sf3, "positionen": [{"varianten_id": polo, "menge": "1"}]},
    ).json()["wareneingang_id"]
    assert eigene in [u["id"] for u in client.get("/api/umlagerung/unterwegs").json()["umlagerungen"]]
    assert client.post(f"/api/umlagerung/{eigene}/stornieren").status_code == 200
    _bestand_ist_summe_der_bewegungen(sessions)


def test_bestand_filter_nach_aktueller_stufe(welt):
    """2026-10-01: die Stufen-Beschriftungen der Übersicht öffnen den Bestand,
    gefiltert auf die Varianten in genau dieser Stufe - dieselbe Einteilung wie
    `stufen_verteilung`, inklusive der 30-%-Stufe ab Eingang."""
    client, codes = welt.client, welt.codes
    heute = date.today()
    vor_40_monaten = date(heute.year - 3, heute.month, 1) - timedelta(days=150)
    vor_20_monaten = date(heute.year - 2, heute.month, 1) + timedelta(days=150)
    welt.anmelden(CHEF)
    for nummer, datum, positionen in (
        ("9000000031", vor_40_monaten, POSITIONEN[:2]),
        ("9000000032", vor_20_monaten, POSITIONEN[2:3]),
        ("9000000033", heute, [["Nike", "424100", "C3", "9988770013", "4006632041265", "Jacke", "4", "Stk", "89.00", "50.00"]]),
    ):
        pdf = rechnung_pdf(header_lines=kopf(nummer=nummer, datum=datum.strftime("%d.%m.%Y")), rows=positionen)
        assert importieren(client, pdf, lagerort_id=str(codes["SF1"])).status_code == 200
    verteilung = client.get("/api/dashboard").json()["filiale"]["stufen"]
    for stufe in ("30", "50", "70"):
        antwort = client.get(f"/api/bestand?stufe={stufe}")
        assert antwort.status_code == 200, antwort.text
        stueck = sum(Decimal(str(z["menge"])) for z in antwort.json()["zeilen"])
        assert stueck == Decimal(str(verteilung[stufe])) and stueck > 0, stufe
    assert client.get("/api/bestand?stufe=40").status_code == 422
    assert client.get("/api/bestand?stufe=50&alle=true").status_code == 422
