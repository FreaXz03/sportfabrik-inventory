from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Integer,
    ForeignKey,
    Numeric,
    String,
    JSON,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base

# Hinweis Altdaten: Die frueheren Tabellen products/invoices/invoice_items/
# invoice_item_sources sind mit Migration c3d4e5f6a7b8 vollstaendig nach
# artikel/varianten/dokumente/wareneingaenge/wareneingang_positionen(_quelle)
# migriert worden (Phase A Punkt 3, "nie verwerfen"). Ihre Tabellen bleiben in
# der Datenbank bestehen (kein DROP), sind aber ab hier nicht mehr gemappt -
# die App liest/schreibt sie nicht mehr. Siehe docs/datenmodell.md.


class User(Base):
    """Anmeldung übers Kassensystem-Muster: Mitarbeiter nur mit Kassennummer,
    Filialleiter/Admin zusätzlich mit Passwort. Rollen steuern Zugriff gemäss
    Regel 9 (siehe app/routers/auth.py): Mitarbeiter alles ausser Dokumente,
    Filialleiter (`chef`) zusätzlich Dokumente, Admin/Zentrale filialübergreifend.
    Die Filialzuordnung liegt in `benutzer_lagerorte` (m:n, Admin braucht keine)."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('mitarbeiter', 'chef', 'admin')", name="ck_users_role"),
        CheckConstraint(
            "(role IN ('chef', 'admin') AND password_hash IS NOT NULL) OR "
            "(role = 'mitarbeiter' AND password_hash IS NULL)",
            name="ck_users_chef_has_password",
        ),
        CheckConstraint("language IN ('de', 'fr', 'en')", name="ck_users_language"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    kassennummer: Mapped[str] = mapped_column(String(20), unique=True, index=True)

    name: Mapped[str | None] = mapped_column(String(100))

    role: Mapped[str] = mapped_column(String(20))

    password_hash: Mapped[str | None] = mapped_column(String(200))

    # Regel 7: Deutsch ist Standard, jederzeit pro Benutzer umstellbar
    # (siehe app/core/i18n.py, POST /api/language).
    language: Mapped[str] = mapped_column(
        String(2), default="de", server_default=text("'de'")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Sicherheit S2 (Entscheid 24.09.2026): falsche Passwörter zählen, nach 5
    # ist das Konto 20 Minuten gesperrt (app/services/anmeldung.py).
    fehlversuche: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    gesperrt_bis: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Punkt 14 (Entscheid 24.09.2026): gewählte Schnellzugriffe und ihre
    # Reihenfolge, je Benutzer. None = noch keine eigene Auswahl getroffen,
    # siehe app/core/schnellzugriffe.py.
    schnellzugriffe: Mapped[list[str] | None] = mapped_column(JSON)


class Lagerort(Base):
    """Filiale (SF1-SF4, Verkauf) oder externer Standort ohne Verkauf: die
    Verarbeitungsstellen GEWA und VEBO sowie das Lager Dietikon. Seed-Daten in
    app/core/lagerorte.py, Adresse dient später auch der automatischen
    Filial-Erkennung aus der Lieferadresse eines Dokuments.

    `verkauf` trägt die Regel 6: Nur an einem Lagerort mit Verkauf bekommt Ware
    ein Eingangsdatum, erst damit startet die Reduktionsuhr (18/36 Monate)."""

    __tablename__ = "lagerorte"

    id: Mapped[int] = mapped_column(primary_key=True)

    code: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))

    strasse: Mapped[str | None] = mapped_column(String(200))
    plz: Mapped[str | None] = mapped_column(String(10))
    ort: Mapped[str | None] = mapped_column(String(100))
    telefon: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(200))

    verkauf: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class BenutzerLagerort(Base):
    """Ordnet einen Benutzer einer oder mehreren Filialen zu (m:n, z.B. Aushilfe
    an mehreren Standorten). `ist_primaer` markiert die Filiale, die nach dem
    Login vorausgewählt ist. Admin-Konten brauchen keinen Eintrag hier."""

    __tablename__ = "benutzer_lagerorte"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    lagerort_id: Mapped[int] = mapped_column(
        ForeignKey("lagerorte.id"), primary_key=True
    )
    ist_primaer: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )


class ArticleNote(Base):
    """Notiz zu einem Artikel (Modell-Ebene, gilt für alle Varianten/Farben/
    Grössen gemeinsam - vor der Migration wurde das zur Laufzeit über
    app/services/article_groups.py nachgebildet, jetzt ist artikel_id die
    echte Gruppe)."""

    __tablename__ = "article_notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    artikel_id: Mapped[int] = mapped_column(ForeignKey("artikel.id"), index=True)
    body: Mapped[str] = mapped_column(String(2000))
    author_user_id: Mapped[int] = mapped_column()
    author_name: Mapped[str] = mapped_column(String(100))
    author_number: Mapped[str] = mapped_column(String(20))
    updated_by: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    version: Mapped[int] = mapped_column(default=1)


class Lieferant(Base):
    """Lieferant/Quelle eines Dokuments (Intersport, ECOM, Dritthändler, Extern,
    Intern - siehe projekt-kontext.md Abschnitt 1 „Warenquellen"). `typ` ist
    zugleich die Lieferantengruppe; der Etikett-Code dazu steht in
    app/core/lieferanten.py. `parser_key`
    verweist auf das zuständige Parser-Modul; `None` = noch kein
    automatischer Parser (Lieferanten-Erkennung ist Phase B)."""

    __tablename__ = "lieferanten"
    __table_args__ = (
        CheckConstraint(
            "typ IN ('intersport', 'ecom', 'drittanbieter', 'extern', 'intern')",
            name="ck_lieferanten_typ",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    typ: Mapped[str] = mapped_column(String(20))
    parser_key: Mapped[str | None] = mapped_column(String(50))


class Kategorie(Base):
    """Kassenkategorie: Hauptgruppe × Sportbereich, exakt wie in der Kasse
    (Regel 8). Velo und Food haben keinen Sportbereich. Fixe Seed-Daten in
    app/core/kategorien.py (35 Kombinationen). An den Artikel kommt sie über
    den FEDAS-Vorschlag (app/core/fedas.py) oder von Hand
    (app/services/kategorien.py, Teilaufgabe B8)."""

    __tablename__ = "kategorien"
    __table_args__ = (
        CheckConstraint(
            "hauptgruppe IN ('Textil', 'Hartware', 'Schuhe', 'Velo', 'Food')",
            name="ck_kategorien_hauptgruppe",
        ),
        UniqueConstraint("hauptgruppe", "sportbereich", name="uq_kategorien_kombi"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    hauptgruppe: Mapped[str] = mapped_column(String(20))
    sportbereich: Mapped[str | None] = mapped_column(String(20))


class Dokument(Base):
    """Hochgeladenes/erfasstes Dokument - verallgemeinert die frühere
    invoices-Tabelle auf alle Dokumenttypen aus D6 (Rechnung, Lieferschein,
    Auftragsbestätigung, Bestellung). `lagerort_id` ist die aus der
    Lieferadresse erkannte bzw. gewählte Filiale."""

    __tablename__ = "dokumente"
    __table_args__ = (
        CheckConstraint(
            "typ IN ('rechnung', 'lieferschein', 'auftragsbestaetigung', 'bestellung')",
            name="ck_dokumente_typ",
        ),
        # Belegnummern sind nur beim jeweiligen Lieferanten eindeutig - zwei
        # Lieferanten dürfen dieselbe Nummer verwenden (Phase B, Teilaufgabe
        # B2, Migration e5f6a7b8c9d0). Der Importer prüft zusätzlich selbst auf
        # Duplikate, damit der Benutzer eine verständliche Meldung bekommt
        # statt eines Datenbankfehlers.
        UniqueConstraint(
            "lieferant_id", "dokumentnummer", name="uq_dokumente_lieferant_dokumentnummer"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    lieferant_id: Mapped[int | None] = mapped_column(ForeignKey("lieferanten.id"), index=True)
    lagerort_id: Mapped[int | None] = mapped_column(ForeignKey("lagerorte.id"), index=True)

    typ: Mapped[str] = mapped_column(String(30))

    # Nur zusammen mit `lieferant_id` eindeutig, siehe __table_args__. Ist
    # `lieferant_id` leer (bisher nie: der Import weist ein Dokument ohne
    # erkannten Lieferanten ab), greift die Eindeutigkeit nicht - NULL gilt in
    # PostgreSQL wie in SQLite als von allem verschieden.
    dokumentnummer: Mapped[str] = mapped_column(String(100), index=True)
    dokumentdatum: Mapped[date | None] = mapped_column(Date)
    belegdatum: Mapped[date | None] = mapped_column(Date)

    dateiname: Mapped[str | None] = mapped_column(String(500))
    datei_hash: Mapped[str | None] = mapped_column(String(64), unique=True)

    hochgeladen_am: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    hochgeladen_von_kassennummer: Mapped[str | None] = mapped_column(String(20))
    hochgeladen_von_name: Mapped[str | None] = mapped_column(String(100))

    # Siehe invoices.ocr_used (frühere Tabelle) für den Hintergrund.
    ocr_verwendet: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )


class Artikel(Base):
    """Modell-Ebene, filialübergreifend (Regel 4): Marke + Lieferanten-
    Artikelnummer. Ohne Lieferanten-Artikelnummer bleibt jeder Artikel
    einzeln (siehe app/services/article_groups.py). Farbe/Grösse/EAN liegen
    in `varianten`."""

    __tablename__ = "artikel"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Leer bei manuell erfasster Ware ohne Beleg (D23/D27) - aus einem
    # Lieferantendokument kommt der Lieferant dagegen immer mit.
    lieferant_id: Mapped[int | None] = mapped_column(
        ForeignKey("lieferanten.id"), index=True
    )
    marke: Mapped[str | None] = mapped_column(String(100))
    lieferanten_artikelnr: Mapped[str | None] = mapped_column(String(100), index=True)
    bezeichnung: Mapped[str | None] = mapped_column(String(500))

    kategorie_id: Mapped[int | None] = mapped_column(ForeignKey("kategorien.id"))
    # Woher die Kategorie stammt (Phase B, Teilaufgabe B8, Migration
    # c9d0e1f2a3b4): `False` = Vorschlag aus dem FEDAS-Code, `True` = von Hand
    # gewählt. Eine von Hand gewählte Kategorie überschreibt kein Import mehr.
    kategorie_manuell: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    fedas_code: Mapped[str | None] = mapped_column(String(10))


class Variante(Base):
    """Farbe/Grösse/EAN eines Artikels (Regel 5: EAN optional, Schlüssel ohne
    EAN ist Lieferant + Artikelnr. + Farbe + Grösse über `artikel_id`).
    `ean_intern` markiert vom System generierte EANs (Phase B, noch
    ungenutzt). `first_seen`/`last_seen` wie früher auf `products`."""

    __tablename__ = "varianten"

    id: Mapped[int] = mapped_column(primary_key=True)

    artikel_id: Mapped[int] = mapped_column(ForeignKey("artikel.id"), index=True)
    farbe: Mapped[str | None] = mapped_column(String(250))
    groesse: Mapped[str | None] = mapped_column(String(100))

    ean: Mapped[str | None] = mapped_column(String(30), unique=True, index=True)
    ean_intern: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )

    first_seen: Mapped[date | None] = mapped_column(Date)
    last_seen: Mapped[date | None] = mapped_column(Date)


class Preis(Base):
    """UVP/EK-Verlauf je Variante (Regel 10: EK optional, nie Pflicht)."""

    __tablename__ = "preise"

    id: Mapped[int] = mapped_column(primary_key=True)

    varianten_id: Mapped[int] = mapped_column(ForeignKey("varianten.id"), index=True)
    uvp: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    ek: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    datum: Mapped[date | None] = mapped_column(Date)
    dokument_id: Mapped[int | None] = mapped_column(ForeignKey("dokumente.id"))


class Wareneingang(Base):
    """Wareneingang: erwartet → eingetroffen (Regel 3, D6).

    `erwartet` kommt von Auftragsbestätigungen und Bestellungen: die Ware ist
    angekündigt, aber noch nicht da - es gibt keine Lagerbewegung, keinen
    Bestand und kein Eingangsdatum. Erst die bestätigte Ankunft bucht
    (`app/services/wareneingang.py`). Kommt nur ein Teil an, bleibt der
    Wareneingang `erwartet`, bis keine Position mehr offen ist (D22); der
    bereits gebuchte Teil steht in `wareneingang_positionen.menge_eingetroffen`.
    """

    __tablename__ = "wareneingaenge"
    __table_args__ = (
        CheckConstraint(
            "status IN ('erwartet', 'eingetroffen')", name="ck_wareneingaenge_status"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # Leer bei manueller Erfassung: Ware ohne Dokument ist ein direkter
    # Wareneingang ohne Beleg (D27).
    dokument_id: Mapped[int | None] = mapped_column(
        ForeignKey("dokumente.id"), index=True
    )
    lagerort_id: Mapped[int] = mapped_column(ForeignKey("lagerorte.id"), index=True)
    status: Mapped[str] = mapped_column(String(20))
    eingangsdatum: Mapped[date | None] = mapped_column(Date)


class WareneingangPosition(Base):
    """Eine Position (Zeile) eines Wareneingangs - verallgemeinert die frühere
    invoice_items-Tabelle.

    `menge` ist die Menge laut Beleg (erwartet), `menge_eingetroffen` die
    davon tatsächlich angekommene. Die Differenz ist die offene Restmenge
    (D22). Bei einer Rechnung/einem Lieferschein sind beide von Anfang an
    gleich, weil die Ware mit dem Beleg kommt.
    """

    __tablename__ = "wareneingang_positionen"

    id: Mapped[int] = mapped_column(primary_key=True)

    wareneingang_id: Mapped[int] = mapped_column(
        ForeignKey("wareneingaenge.id"), index=True
    )
    varianten_id: Mapped[int] = mapped_column(ForeignKey("varianten.id"), index=True)

    menge: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    menge_eingetroffen: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=0, server_default=text("0")
    )
    einheit: Mapped[str | None] = mapped_column(String(30))
    uvp: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    ek: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))


class WareneingangPositionQuelle(Base):
    """Unveränderter Original-Snapshot je Position für spätere Audits -
    verallgemeinert die frühere invoice_item_sources-Tabelle."""

    __tablename__ = "wareneingang_positionen_quelle"
    position_id: Mapped[int] = mapped_column(
        ForeignKey("wareneingang_positionen.id"), primary_key=True
    )
    data: Mapped[dict] = mapped_column(JSON)


class Lagerbewegung(Base):
    """Journal aller Bestandsänderungen (Regel 2: Bestand nie direkt
    überschreiben, jede Änderung eine Zeile hier). Benutzer als
    Momentaufnahme gespeichert (wie bei `dokumente`/`article_notes`), nicht
    als Fremdschlüssel - bleibt lesbar, auch wenn das Konto später entfernt
    wird."""

    __tablename__ = "lagerbewegungen"
    __table_args__ = (
        CheckConstraint(
            "typ IN ('zugang', 'verkauf', 'ausbuchung', 'korrektur', 'umlagerung')",
            name="ck_lagerbewegungen_typ",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    lagerort_id: Mapped[int] = mapped_column(ForeignKey("lagerorte.id"), index=True)
    varianten_id: Mapped[int] = mapped_column(ForeignKey("varianten.id"), index=True)
    typ: Mapped[str] = mapped_column(String(20))
    menge: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    grund: Mapped[str | None] = mapped_column(String(200))
    # Nur bei einer Umlagerung, die in der Zielfiliale die Reduktionsuhr
    # startet (D13: externer Standort -> Filiale, F11: Filiale ohne bisherigen
    # Wareneingang). Sonst leer - das Datum eines Zugangs steht am
    # Wareneingang.
    eingangsdatum: Mapped[date | None] = mapped_column(Date)

    wareneingang_position_id: Mapped[int | None] = mapped_column(
        ForeignKey("wareneingang_positionen.id")
    )
    benutzer_kassennummer: Mapped[str | None] = mapped_column(String(20))
    benutzer_name: Mapped[str | None] = mapped_column(String(100))

    zeitpunkt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Bestand(Base):
    """Aktueller Bestand je Variante × Filiale, aus `lagerbewegungen`
    abgeleitet (Regel 2) und dort auch aktuell gehalten - nie direkt
    geschrieben ausser beim Nachführen der Summe. `aeltestes_eingangsdatum`
    dient der Reduktionslogik (Phase D, 8.3)."""

    __tablename__ = "bestand"

    varianten_id: Mapped[int] = mapped_column(ForeignKey("varianten.id"), primary_key=True)
    lagerort_id: Mapped[int] = mapped_column(ForeignKey("lagerorte.id"), primary_key=True)
    menge: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, server_default=text("0"))
    aeltestes_eingangsdatum: Mapped[date | None] = mapped_column(Date)


class ReduktionManuell(Base):
    """Von Hand gewählte Reduktionsstufe je Modell × Filiale (24.09.2026).

    Getrennt von der Empfehlung nach Regel 6, die weiterhin berechnet wird:
    gilt eine Zeile, ist sie die wirksame Stufe (auch unter der Empfehlung).
    Löschen heisst zurück zur Empfehlung. Wie das Modell selbst gilt sie für
    alle Farben und Grössen. Benutzer als Momentaufnahme - bleibt lesbar,
    auch wenn das Konto gelöscht wird (Entscheid 24.09.2026)."""

    __tablename__ = "reduktionen_manuell"
    __table_args__ = (
        UniqueConstraint("artikel_id", "lagerort_id", name="uq_reduktionen_manuell_artikel_lagerort"),
        CheckConstraint("prozent IN (30, 50, 70)", name="ck_reduktionen_manuell_prozent"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    artikel_id: Mapped[int] = mapped_column(ForeignKey("artikel.id", ondelete="CASCADE"), index=True)
    lagerort_id: Mapped[int] = mapped_column(ForeignKey("lagerorte.id"), index=True)
    prozent: Mapped[int] = mapped_column(Integer)
    benutzer_kassennummer: Mapped[str | None] = mapped_column(String(20))
    benutzer_name: Mapped[str | None] = mapped_column(String(100))
    gesetzt_am: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ReduktionBestaetigt(Base):
    """Bestätigung „erledigt" auf der Runterschreiben-Liste (D-F1,
    25.09.2026): eine Filiale bestätigt, ein fälliges Modell heruntergeschrieben
    zu haben - es verschwindet dann aus der fälligen Liste, bis die nächste
    Stufe fällig wird (`stufe` hier weicht dann von der neu berechneten
    Stufe ab und die Zeile zählt nicht mehr). Bezieht sich auf die
    automatische Stufe nach Regel 6, nicht auf `reduktionen_manuell`."""

    __tablename__ = "reduktionen_bestaetigt"
    __table_args__ = (
        UniqueConstraint("artikel_id", "lagerort_id", name="uq_reduktion_bestaetigt_artikel_lagerort"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    artikel_id: Mapped[int] = mapped_column(ForeignKey("artikel.id", ondelete="CASCADE"), index=True)
    lagerort_id: Mapped[int] = mapped_column(ForeignKey("lagerorte.id"), index=True)
    stufe: Mapped[int] = mapped_column(Integer)
    benutzer_kassennummer: Mapped[str | None] = mapped_column(String(20))
    benutzer_name: Mapped[str | None] = mapped_column(String(100))
    bestaetigt_am: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Hinweis(Base):
    """Kurzer Hinweis an eine Filiale (D-F2, 25.09.2026): aktuell nur beim
    Nachlieferungs-Fall - ein Modell mit bereits reduziertem Altbestand
    bekommt Nachschub. Regel 6 lässt die Uhr für das ganze Modell neu
    starten (keine Chargentrennung im Bestand); der Hinweis macht das
    sichtbar, damit die Filiale den Altbestand bei Bedarf von Hand wieder auf
    seine bisherige Stufe setzt (`reduktionen_manuell`)."""

    __tablename__ = "hinweise"
    __table_args__ = (
        CheckConstraint("typ IN ('nachlieferung_reduziert')", name="ck_hinweise_typ"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    lagerort_id: Mapped[int] = mapped_column(ForeignKey("lagerorte.id"), index=True)
    artikel_id: Mapped[int] = mapped_column(ForeignKey("artikel.id", ondelete="CASCADE"), index=True)
    typ: Mapped[str] = mapped_column(String(30))
    alte_stufe: Mapped[int] = mapped_column(Integer)
    erstellt_am: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ReduktionEmpfehlungZentrale(Base):
    """Empfehlung der Zentrale für eine Reduktionsstufe ab einem Datum
    (D-F3, 25.09.2026): die Zentrale setzt sie je Modell für eine Filiale,
    die Filiale übernimmt oder lehnt mit Grund ab. Getrennt von
    `reduktionen_manuell` (das ist die tatsächlich wirksame Wahl vor Ort) -
    „übernehmen" setzt dort dieselbe Stufe."""

    __tablename__ = "reduktion_empfehlung_zentrale"
    __table_args__ = (
        CheckConstraint("prozent IN (30, 50, 70)", name="ck_empfehlung_zentrale_prozent"),
        CheckConstraint(
            "status IN ('offen', 'uebernommen', 'abgelehnt')", name="ck_empfehlung_zentrale_status"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    artikel_id: Mapped[int] = mapped_column(ForeignKey("artikel.id", ondelete="CASCADE"), index=True)
    lagerort_id: Mapped[int] = mapped_column(ForeignKey("lagerorte.id"), index=True)
    prozent: Mapped[int] = mapped_column(Integer)
    ab_datum: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="offen", server_default=text("'offen'"))
    ablehnungsgrund: Mapped[str | None] = mapped_column(String(200))
    gesetzt_von_kassennummer: Mapped[str | None] = mapped_column(String(20))
    gesetzt_von_name: Mapped[str | None] = mapped_column(String(100))
    gesetzt_am: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    beantwortet_von_name: Mapped[str | None] = mapped_column(String(100))
    beantwortet_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
