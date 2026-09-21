# Datenmodell

Verwaltet über SQLAlchemy 2.0 (`app/core/models.py`) und Alembic-Migrationen
(`migrations/`). Seit Migration `c3d4e5f6a7b8` (Phase A Punkt 3) gilt das
Datenmodell aus `projekt-kontext.md` Abschnitt 8.2: Artikelstamm
filialübergreifend, Bestand/Wareneingänge/Reduktionen filialbezogen, Bestand
nie direkt überschrieben, sondern als `lagerbewegungen`-Journal geführt
(Regel 2).

## Alte Tabellen (`products`, `invoices`, `invoice_items`,
`invoice_item_sources`)

Bleiben unangetastet in der Datenbank (kein `DROP`, „nie verwerfen"), sind
aber **nicht mehr gemappt** — die App liest/schreibt sie seit
`c3d4e5f6a7b8` nicht mehr. Ihre Daten wurden vollständig in die neuen
Tabellen migriert (siehe „Migration der Altdaten" unten). Eine Ausnahme:
`products.article_no` (INTERSPORT-eigene Artikelnummer je Variante) wird
**nicht** übernommen — das neue Modell führt nur noch die
Lieferanten-Artikelnummer (`artikel.lieferanten_artikelnr`) als
Artikel-Schlüssel (Regel 5); der historische Wert bleibt in der alten,
unangetasteten `products`-Tabelle einsehbar.

## Neue Tabellen

```mermaid
erDiagram
    LIEFERANTEN ||--o{ ARTIKEL : "liefert"
    KATEGORIEN ||--o{ ARTIKEL : "kategorisiert"
    ARTIKEL ||--o{ VARIANTEN : "hat"
    VARIANTEN ||--o{ PREISE : "Preisverlauf"
    VARIANTEN ||--o{ WARENEINGANG_POSITIONEN : "Position in"
    VARIANTEN ||--o{ LAGERBEWEGUNGEN : "betrifft"
    VARIANTEN ||--o{ BESTAND : "Bestand je Filiale"
    ARTIKEL ||--o{ ARTICLE_NOTES : "hat Notizen"
    LIEFERANTEN ||--o{ DOKUMENTE : "Absender"
    LAGERORTE ||--o{ DOKUMENTE : "Zielfiliale"
    DOKUMENTE ||--o{ WARENEINGAENGE : "erzeugt"
    LAGERORTE ||--o{ WARENEINGAENGE : "Filiale"
    WARENEINGAENGE ||--o{ WARENEINGANG_POSITIONEN : "enthält"
    WARENEINGANG_POSITIONEN ||--o| WARENEINGANG_POSITIONEN_QUELLE : "Original-Snapshot"
    DOKUMENTE ||--o{ PREISE : "Quelle"
    LAGERORTE ||--o{ LAGERBEWEGUNGEN : "Filiale"
    LAGERORTE ||--o{ BESTAND : "Filiale"
    WARENEINGANG_POSITIONEN ||--o| LAGERBEWEGUNGEN : "erzeugt Zugang"

    LIEFERANTEN {
        int id PK
        string name UK
        string typ
        string parser_key
    }
    KATEGORIEN {
        int id PK
        string hauptgruppe
        string sportbereich
    }
    ARTIKEL {
        int id PK
        int lieferant_id FK
        string marke
        string lieferanten_artikelnr
        string bezeichnung
        int kategorie_id FK
        string fedas_code
    }
    VARIANTEN {
        int id PK
        int artikel_id FK
        string farbe
        string groesse
        string ean UK
        boolean ean_intern
        date first_seen
        date last_seen
    }
    PREISE {
        int id PK
        int varianten_id FK
        numeric uvp
        numeric ek
        date datum
        int dokument_id FK
    }
    DOKUMENTE {
        int id PK
        int lieferant_id FK
        int lagerort_id FK
        string typ
        string dokumentnummer UK
        date dokumentdatum
        date belegdatum
        string dateiname
        string datei_hash UK
        datetime hochgeladen_am
        string hochgeladen_von_kassennummer
        string hochgeladen_von_name
        boolean ocr_verwendet
    }
    WARENEINGAENGE {
        int id PK
        int dokument_id FK
        int lagerort_id FK
        string status
        date eingangsdatum
    }
    WARENEINGANG_POSITIONEN {
        int id PK
        int wareneingang_id FK
        int varianten_id FK
        numeric menge
        string einheit
        numeric uvp
        numeric ek
    }
    WARENEINGANG_POSITIONEN_QUELLE {
        int position_id PK_FK
        json data
    }
    LAGERBEWEGUNGEN {
        int id PK
        int lagerort_id FK
        int varianten_id FK
        string typ
        numeric menge
        string grund
        int wareneingang_position_id FK
        string benutzer_kassennummer
        string benutzer_name
        datetime zeitpunkt
    }
    BESTAND {
        int varianten_id PK_FK
        int lagerort_id PK_FK
        numeric menge
        date aeltestes_eingangsdatum
    }
    ARTICLE_NOTES {
        int id PK
        int artikel_id FK
        string body
        int author_user_id
        string author_name
        string author_number
        string updated_by
        datetime created_at
        datetime updated_at
        int version
    }
```

`article_notes.artikel_id` (bis `c3d4e5f6a7b8`: `product_id`) steht wie
`dokumente`/`lagerbewegungen` absichtlich ohne Fremdschlüssel auf
`users.id` für den Autor — siehe Begründung weiter unten bei `users`.

## Tabellen im Detail

### `lieferanten`
Ein Datensatz je Lieferant. `typ` (`intersport`/`ecom`/`drittanbieter`/
`extern`) und `parser_key` (verweist auf das passende Parser-Modul in
`app/services/parsers/`, aktuell nur `intersport`) steuern die automatische
Lieferanten-Erkennung beim Dokumenten-Upload: die Registry erkennt das Layout
und der Import schlägt den Lieferanten über denselben `parser_key` nach
(Phase B, Teilaufgabe B1 — siehe `docs/architektur.md`, „PDF-Parsing"). Ein
Lieferant ohne passendes Parser-Modul (bzw. umgekehrt) lässt den Import
scheitern, darum prüft `tests/test_parser_registry.py` beide Seiten
gegeneinander. Seed-Daten in `app/core/lieferanten.py`.

### `kategorien`
Kassenkategorien: Hauptgruppe (Textil, Hartware, Schuhe, Velo, Food) ×
Sportbereich (Regel 8) — Velo und Food ohne Sportbereich. 35 fixe
Kombinationen, Seed-Daten in `app/core/kategorien.py`. Ein FEDAS→Kategorie-
Mapping: `app/core/fedas.py` (Phase B, siehe `projekt-kontext.md` Details zu
Phase B), aktuell nur die aus echten Rechnungen bestätigten Codes.

### `artikel`
Modell-Ebene, filialübergreifend (Regel 4): Marke + Lieferanten-Artikelnummer
identifizieren ein Modell über alle Farben/Grössen hinweg. Fehlt die
Lieferanten-Artikelnummer, bleibt jedes Vorkommen ein eigener Artikel (echte
Fremdschlüsselbeziehung statt der früheren Laufzeit-Gruppierung in
`app/services/article_groups.py`, die jetzt nur noch `varianten.artikel_id`
abfragt). `fedas_code` wird beim Import mitgeschrieben, sofern die Rechnung
ihn liefert. `kategorie_id` wird beim Anlegen eines neuen Artikels automatisch
aus dem FEDAS-Code vorgeschlagen (`app/core/fedas.py` + `app/services/
importer.py`), sofern die Kombination bekannt ist - sonst bleibt sie leer
(eine manuelle Auswahl-Oberfläche dafür ist noch nicht gebaut). Ein einmal
gesetzter Wert wird nie überschrieben, ein noch leerer aber bei einer
späteren Rechnung mit bekanntem Code nachträglich befüllt.

### `varianten`
Farbe/Grösse/EAN eines Artikels (Regel 5: EAN optional — Schlüssel ohne EAN
ist Lieferant + Artikelnummer + Farbe + Grösse über `artikel_id`). Seit
Teilaufgabe B3 gilt das auch beim Upload: eine Position ohne EAN läuft mit
Hinweis durch und landet als Variante mit leerer EAN. Mehrere solche Varianten
stören sich nicht, weil NULL im Unique-Index nicht kollidiert.
`ean_intern` markiert vom System generierte EANs (EAN-13 im GS1-Bereich
20–29, Phase B, noch ungenutzt). `first_seen`/`last_seen` wie früher auf
`products`, bei jedem Import/jeder Löschung neu berechnet.

### `preise`
UVP/EK-Verlauf je Variante (Regel 10: EK optional, nie Pflicht), mit Datum
und verweisendem Dokument. Ersetzt die frühere implizite Preishistorie über
`invoice_items.uvp` + `invoices.invoice_date`.

### `dokumente`
Verallgemeinert die frühere `invoices`-Tabelle auf alle Dokumenttypen aus D6
(Rechnung, Lieferschein, Auftragsbestätigung, Bestellung). `typ` kommt seit
Teilaufgabe B1 aus dem Dokument selbst (das erkannte Parser-Modul liefert ihn
mit) statt fest als `rechnung`; ohne erkannten Typ wird nicht importiert.
`datei_hash` ist global eindeutig (dieselbe Datei ist dasselbe Dokument, egal
von wem), die Belegnummer dagegen nur **je Lieferant**:
`UNIQUE (lieferant_id, dokumentnummer)` seit Migration e5f6a7b8c9d0 (Phase B,
Teilaufgabe B2). Belegnummern sind Lieferantensache und überschneiden sich
zwangslos — vorher hätte die Rechnung eines neuen Lieferanten nur deshalb als
Duplikat gegolten, weil INTERSPORT die Nummer schon verwendet hatte. Ist
`lieferant_id` leer, greift die Eindeutigkeit nicht (NULL gilt als von allem
verschieden); der Import weist ein Dokument ohne erkannten Lieferanten aber ab,
darum kommt das nicht vor. Die verständliche Meldung („Rechnung … wurde bereits
importiert") kommt aus dem Importer, der Constraint ist der Rückfall für zwei
gleichzeitige Importe. `lagerort_id` ist die Zielfiliale: seit Teilaufgabe B4 der beim Import
gewählte Lagerort, vorgeschlagen aus der Lieferadresse des Dokuments
(`app/services/lieferadresse.py`, D19) und sonst die aktive Filiale. Ein
Dokument hat genau einen Lagerort (D20).
`ocr_verwendet` markiert Dokumente, die mangels Textebene per Tesseract-OCR
gelesen wurden.

### `wareneingaenge`
Ein Wareneingang je Dokument (aktuell 1:1, das Schema erlaubt später mehrere
je Dokument z. B. bei Teillieferungen). `status` unterscheidet `erwartet`
(nur bei Auftragsbestätigungen — noch keine Bestandsbuchung, Regel 3) von
`eingetroffen` (Ware ist da, `lagerbewegungen`/`bestand` werden geschrieben).
Rechnungen und Lieferscheine sind sofort `eingetroffen`, Auftragsbestätigungen
und Bestellungen erst `erwartet` (Teilaufgabe B5). `eingangsdatum` wird beim
ersten Zugang gesetzt — rückwirkend möglich (D13), in einem Lager ohne Verkauf
gar nicht (Regel 6).

`eingangsdatum` folgt Regel 6: Bei einer Filiale (`lagerorte.verkauf = true`)
ist es das Rechnungsdatum, bei einem Lager ohne Verkauf (GEWA) bleibt es
**leer** und wird erst bei Ankunft in einer Filiale gesetzt — die
Reduktionsuhr (18/36 Monate) soll nicht schon im Zwischenlager laufen.
Dasselbe gilt für `bestand.aeltestes_eingangsdatum`.

### `wareneingang_positionen` (+ `wareneingang_positionen_quelle`)
Eine Zeile je Position eines Wareneingangs — verallgemeinert die frühere
`invoice_items`-Tabelle. `wareneingang_positionen_quelle` ist der optionale
1:1-Original-Snapshot (Rohtext, Seiten-/Zeilennummer, Parser-Warnungen,
`correction_audit`) als JSON, genau wie früher `invoice_item_sources` —
bleibt auch erhalten, wenn sich `varianten`/`artikel` später ändern. `menge` ist die Menge laut Beleg (erwartet),
`menge_eingetroffen` die davon tatsächlich angekommene; die Differenz ist die
offene Restmenge (D22, Migration `f6a7b8c9d0e1`). Bei Rechnung/Lieferschein
sind beide von Anfang an gleich.

### `lagerbewegungen`
Append-only-Journal jeder Bestandsänderung (Regel 2): `typ` ist `zugang`,
`verkauf`, `ausbuchung`, `korrektur` oder `umlagerung`. Jede importierte
Rechnungsposition erzeugt genau eine Bewegung vom Typ `zugang`. Benutzer wird
als Momentaufnahme gespeichert (wie bei `dokumente`/`article_notes`), nicht
als Fremdschlüssel.

### `bestand`
Aktueller Bestand je Variante × Filiale (zusammengesetzter Primärschlüssel),
aus `lagerbewegungen` abgeleitet und dort auch aktuell gehalten (nie direkt
geschrieben ausser beim Nachführen der Summe). `aeltestes_eingangsdatum`
dient später der Reduktionslogik (Phase D, 18/36 Monate ab letztem
Wareneingang derselben Lieferanten-Artikelnummer in dieser Filiale).

**Bekannte Einschränkung nach der Migration:** Da das alte System nie
Verkäufe/Ausbuchungen erfasst hat, entspricht der migrierte `bestand` der
kumulierten historischen Wareneingänge, nicht dem tatsächlichen physischen
Bestand — wird erst mit dem manuellen Ausbuchen (Phase C) bzw. einer
Inventur korrigiert.

### `article_notes`
Wie zuvor, jetzt an `artikel_id` statt `product_id` — eine Notiz gilt für das
ganze Modell (alle Farben/Grössen), nicht mehr nur für die beim Erstellen
angezeigte Variante. Optimistisches Sperren über `version` unverändert.

### `users`, `lagerorte`, `benutzer_lagerorte`
Unverändert seit Phase A Punkt 1/2 (siehe Migrationshistorie unten).

## Migration der Altdaten (`c3d4e5f6a7b8`)

Läuft automatisch beim `alembic upgrade head` (nicht im Offline-`--sql`-
Modus, siehe unten) und ist verlustfrei bis auf `products.article_no` (siehe
oben):

1. **Lieferanten/Kategorien**: Seed-Daten wie oben.
2. **`products` → `artikel` + `varianten`**: gleiche Gruppierung wie zuvor
   `article_groups.py` — gleiche Marke (getrimmt, ohne Gross-/
   Kleinschreibung) + gleiche, nicht-leere Lieferanten-Artikelnummer
   (getrimmt) = ein Artikel; fehlt die Nummer, bleibt jedes Produkt ein
   eigener Artikel.
3. **`invoices` → `dokumente` + `wareneingaenge`**: `typ = 'rechnung'`,
   `status` immer `'eingetroffen'` (altes System kannte nur eingetroffene
   Ware), Lagerort SF1 (Altdaten-Regel aus CLAUDE.md).
4. **`invoice_items` + `invoice_item_sources` → `wareneingang_positionen`
   (+ `_quelle`) + `preise` (falls UVP vorhanden) + `lagerbewegungen`**
   (Typ `zugang`, falls Menge vorhanden).
5. **`bestand`**: aus den neu erzeugten `lagerbewegungen` aggregiert.
6. **`article_notes.product_id` → `artikel_id`**: über die in Schritt 2
   gebildete Zuordnung.

## Migrationshistorie

| Revision | Beschreibung |
|---|---|
| `5ce94c6a96e3` | Baseline: `products`, `invoices`, `invoice_items`, `invoice_item_sources` |
| `7129c5082ac9` | `users`-Tabelle inkl. beider Check-Constraints |
| `246c67c1d45e` | `imported_by_kassennummer`/`imported_by_name` auf `invoices` |
| `d567ef887517` | `ocr_used` (Boolean, Default `false`) auf `invoices` |
| `e901abc23456` | Neue Tabelle `article_notes` inkl. Autor-Snapshot und Versionsfeld |
| `a1b2c3d4e5f6` | Neue Tabellen `lagerorte` (SF1-SF4 + GEWA, Seed-Daten) und `benutzer_lagerorte` (m:n); `users.role` um `admin` erweitert; bestehende Benutzer auf SF1 zugeordnet |
| `b2c3d4e5f6a7` | `users.language` (DE/FR/EN, Default `de`) inkl. Check-Constraint |
| `c3d4e5f6a7b8` | Neues Datenmodell (Phase A Punkt 3): `lieferanten`, `kategorien`, `artikel`, `varianten`, `preise`, `dokumente`, `wareneingaenge`, `wareneingang_positionen` (+`_quelle`), `lagerbewegungen`, `bestand`; vollständige Datenmigration der Altdaten; `article_notes.product_id` → `artikel_id` |
| `d4e5f6a7b8c9` | Reparatur: Id-Sequenzen der neuen Tabellen auf `MAX(id)` setzen. `c3d4e5f6a7b8` hat sie in seiner ersten Fassung nur nachgezogen, wenn es Altdaten gab — auf einer frischen Datenbank scheiterte dadurch der erste Insert ohne explizite Id. Idempotent, nur PostgreSQL, auf einer korrekten Datenbank ein No-Op |

Schema-Änderungen laufen ausschliesslich über Alembic
(`alembic revision --autogenerate`); der Container führt beim Start
automatisch `alembic upgrade head` aus (siehe `SERVER-SETUP.md`).
