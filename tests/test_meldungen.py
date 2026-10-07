"""Punkte 4 und 5 (2026-10-01): Fehlermeldung und unbekanntes Dokument per Mail an Fabian.

Harte Regeln: nur auf ausdrücklichen Klick, nur an fabian_morf@icloud.com (nie
ein Empfänger vom Benutzer), nie automatisch - auch nicht bei unbekanntem
Layout (Regel 1, Ausnahme 2026-10-01). Der Mailversand ist hier ein Fälscher.
"""

import pymupdf
import pytest
from conftest import ANNA, CHEF

EMPFAENGER = "fabian_morf@icloud.com"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
PDF = b"%PDF-1.4\n" + b"0" * 64


class FakeSMTP:
    gesendet: list = []

    def __init__(self, host, port, timeout=None):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self, **kwargs):
        pass

    def login(self, user, password):
        pass

    def send_message(self, nachricht):
        FakeSMTP.gesendet.append(nachricht)


@pytest.fixture
def mail(monkeypatch):
    import app.services.mail as mailmodul

    FakeSMTP.gesendet = []
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_FROM", "inventory@sportfabrik.test")
    monkeypatch.setattr(mailmodul.smtplib, "SMTP", FakeSMTP)
    mailmodul._versand_log.clear()
    return FakeSMTP.gesendet


def _fehler(client, **felder):
    daten = {"titel": "Scanner piept nicht", "nachricht": "Beim Ausbuchen kommt kein Ton.", "seite": "/ausbuchen", **felder}
    dateien = daten.pop("files", [])
    return client.post("/api/fehlermeldung", data=daten, files=dateien)


def test_fehlermeldung_geht_nur_an_fabian_mit_kontext_und_bild(welt, mail):
    welt.anmelden(ANNA)
    antwort = _fehler(welt.client, files=[("bilder", ("foto.png", PNG, "image/png"))])
    assert antwort.status_code == 200, antwort.text
    assert len(mail) == 1
    nachricht = mail[0]
    assert nachricht["To"] == EMPFAENGER
    assert "Scanner piept nicht" in nachricht["Subject"]
    text = nachricht.get_body(preferencelist=("plain",)).get_content()
    assert "Beim Ausbuchen kommt kein Ton." in text and "Anna" in text and "910141" in text and "/ausbuchen" in text
    assert [a.get_filename() for a in nachricht.iter_attachments()] == ["foto.png"]


def test_empfaenger_ist_nie_vom_benutzer_und_betreff_ohne_zeilenumbruch(welt, mail):
    welt.anmelden(ANNA)
    antwort = _fehler(welt.client, titel="Hallo\r\nBcc: fremd@example.com", an="fremd@example.com")
    assert antwort.status_code == 200
    nachricht = mail[0]
    assert nachricht["To"] == EMPFAENGER and nachricht["Bcc"] is None
    assert "\n" not in nachricht["Subject"] and "\r" not in nachricht["Subject"]


def test_fehlermeldung_prueft_eingabe(welt, mail):
    welt.anmelden(ANNA)
    assert _fehler(welt.client, titel="  ").status_code == 422
    assert _fehler(welt.client, nachricht="").status_code == 422
    assert _fehler(welt.client, nachricht="x" * 4001).status_code == 422
    assert _fehler(welt.client, files=[("bilder", ("a.exe", b"MZ" + b"0" * 50, "application/octet-stream"))]).status_code == 422
    # Typ stimmt, Inhalt nicht (kein echtes PNG)
    assert _fehler(welt.client, files=[("bilder", ("a.png", b"kein bild", "image/png"))]).status_code == 422
    viele = [("bilder", (f"{i}.png", PNG, "image/png")) for i in range(5)]
    assert _fehler(welt.client, files=viele).status_code == 422
    gross = [("bilder", ("g.png", PNG + b"0" * (6 * 1024 * 1024), "image/png"))]
    assert _fehler(welt.client, files=gross).status_code == 422
    assert mail == []


def test_ohne_anmeldung_und_ohne_smtp(welt, monkeypatch, mail):
    assert _fehler(welt.client).status_code == 401
    welt.anmelden(ANNA)
    monkeypatch.delenv("SMTP_HOST")
    assert _fehler(welt.client).status_code == 503
    assert mail == []
    assert welt.client.get("/api/meldungen/status").json() == {"konfiguriert": False, "empfaenger": EMPFAENGER}


def test_begrenzung_je_konto(welt, mail):
    welt.anmelden(ANNA)
    codes = [_fehler(welt.client).status_code for _ in range(12)]
    assert codes.count(200) == 10 and codes[-1] == 429
    assert len(mail) == 10


def test_dokument_senden_nur_chef_nur_pdf_nur_auf_klick(welt, mail):
    url = "/api/dokument-melden"
    welt.anmelden(ANNA)
    assert welt.client.post(url, files={"file": ("x.pdf", PDF, "application/pdf")}).status_code == 403
    welt.anmelden(CHEF)
    assert welt.client.post(url, files={"file": ("x.pdf", b"kein pdf", "application/pdf")}).status_code == 422
    assert mail == []
    antwort = welt.client.post(url, data={"notiz": "Neuer Lieferant", "an": "fremd@example.com"}, files={"file": ("CMP Nachbest.pdf", PDF, "application/pdf")})
    assert antwort.status_code == 200, antwort.text
    nachricht = mail[0]
    assert nachricht["To"] == EMPFAENGER and "CMP Nachbest.pdf" in nachricht["Subject"]
    assert [a.get_filename() for a in nachricht.iter_attachments()] == ["CMP Nachbest.pdf"]
    text = nachricht.get_body(preferencelist=("plain",)).get_content()
    assert "Neuer Lieferant" in text and "Filialleiter" in text or "chef" in text


def test_unbekanntes_layout_sendet_nie_automatisch(welt, mail):
    """Der Upload meldet das unbekannte Layout mit Fehlercode - gesendet wird nichts."""
    dokument = pymupdf.open()
    dokument.new_page().insert_text((72, 72), "Voellig unbekanntes Layout 123")
    pdf = dokument.tobytes()
    welt.anmelden(CHEF)
    antwort = welt.client.post("/upload-preview", files={"file": ("neu.pdf", pdf, "application/pdf")})
    assert antwort.status_code == 422
    assert antwort.headers.get("X-Error-Code") == "unknown_layout"
    assert mail == []
