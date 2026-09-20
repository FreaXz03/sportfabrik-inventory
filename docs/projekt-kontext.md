# Sportfabrik Warenwirtschaft — Projektkontext, Vision & Zielbild

Stand: 2026-09-20 (Rev. 5 — Umlagerung behält Datum; Reduktion pro Filiale, GEWA-Eingangsdatum, Etikettendrucker, Scanner, Kategorien final) · **Massgebliche Zielbeschreibung** des Projekts. Technischer Ist-Zustand des Codes: `README.md` und `docs/architektur.md`, `docs/datenmodell.md`.
Repo: github.com/FreaXz03/sportfabrik-inventory (Branch `main`, letzter Commit `ea5c7ac`).

---

## 1. Unternehmen & Geschäftsmodell

| Punkt | Beschreibung |
|---|---|
| Firma | **Sportfabrik** / Sport Fabrik AG (sportfabrik.ch) — Discounter/Outlet von **Intersport** (Verbandsmitglied Nr. 10166) |
| Grösse | **4 Filialen** in der Schweiz (siehe unten), gegründet **2005**. Hauptsitz Volketswil |
| IT-Umfang | pro Filiale ca. **4–5 PCs** → total ca. 16–20 Arbeitsplätze |
| Sortiment | Markenware: Bekleidung, Schuhe, Hartwaren, Velos, Ski, Winterausrüstung, Food usw. |
| Preislogik | Verkauf **reduziert ab UVP** in Stufen **‑30 % / ‑50 % / ‑70 %**. Neue Ware meist ‑30 %; je länger im Laden, desto stärker runtergeschrieben |

### Filialen & Lagerorte

| Kürzel | Standort | Adresse | Telefon | E-Mail |
|---|---|---|---|---|
| **SF1** | Volketswil *(Hauptsitz, Server-Standort)* | Industriestrasse 21, 8604 Volketswil | 043 444 93 33 | volketswil@sportfabrik.ch |
| **SF2** | Regensdorf | Althardstrasse 10, 8105 Regensdorf | 044 840 05 90 | regensdorf@sportfabrik.ch |
| **SF3** | Hägendorf | Industriestrasse West 40/42, 4614 Hägendorf | 062 216 53 88 | haegendorf@sportfabrik.ch |
| **SF4** | Conthey | Route Cantonale 7, 1964 Conthey | 027 322 75 83 | conthey@sportfabrik.ch |
| **GEWA** | Externes Lager *(kein Verkauf)* | GEWA-John Leuenberger, Grubenstrasse 22, 3322 Urtenen-Schönbühl | – | – |

**GEWA** = externes Lager, in dem Ware ausgepackt und aufbereitet wird; danach geht sie in eine Filiale. → Im System ein eigener **Lagerort ohne Verkauf**; Weitergabe an eine Filiale = **Umlagerung** (gehört damit schon ins MVP).

### Warenquellen

| Quelle | Beschreibung | Dokumente (gemäss Beispielen) |
|---|---|---|
| **Intersport** | Direktlieferung Intersport Schweiz | PDF-Rechnung, Intersport-Layout (Parser existiert) |
| **ECOM** | Retouren Intersport-Onlineshop | **gleiches Intersport-Rechnungslayout**, erkennbar an Referenz „SCH-SF ret.Ecom“ / Ex. Belegnr. „SF ECOM …“ |
| **Dritthändler / Marken** | z. B. Alpina, Chris Sports (Giro), CMP/Campagnolo, Nike, adidas, Puma … | je Lieferant eigenes Layout; oft **Auftragsbestätigungen**, teils gescannt |
| **Externe Händler** | unabhängige Händler/Restposten („Close Out“) | eigenes Layout, oft **ohne EAN** |

## 2. Ist-Zustand im Laden (Problem)

- **Kasse (internes Intersport-Kassensystem) komplett manuell:** Kategorie anklicken → Preis eintippen → Prozent wählen → verkaufen. Keine EAN-Suche.
- **Kein Warenwirtschaftssystem:** keine Artikeldatenbank, keine Lagerbestände, keine Preisübersicht.

### Kassenkategorien (Ist-Aufbau, Screenshot vom 20.09.2026)

„Verkauf starten“ → **Hauptgruppe** → **Sportbereich**. Textil, Hartware und Schuhe haben dieselben 11 Sportbereiche:

| Hauptgruppe | Sportbereiche |
|---|---|
| Textil | Velo · Freizeit · Tennis · Winter · Outdoor · Fussball · Kids · Baden · Indoor · Running · Rollsport |
| Hartware | dieselben 11 |
| Schuhe | dieselben 11 |
| Velo | *keine Unterkategorien* |
| Food | *keine Unterkategorien* |

→ Total **35 Kassenkategorien** (3 × 11 + Velo + Food). Im System als **zwei Felder** abbilden: `hauptgruppe` × `sportbereich` (bei Velo/Food leer). So passt es 1:1 zur Kasse und lässt sich gut filtern/auswerten.

**Automatische Kategorie-Zuordnung über FEDAS:** Intersport-Rechnungen enthalten pro Position einen 6-stelligen **FEDAS-Code** (europäischer Standard für Sportartikel). Aus den Beispielen ersichtlich: 1. Ziffer = Produktart (1 = Hartware, 2 = Textil, 3 = Schuhe), Ziffern 2–3 = Sportart (z. B. 24 Tennis, 32 Fussball, 60 Velo, 64 Outdoor, 75 Freizeit/Lifestyle). → Eine Mapping-Tabelle FEDAS → Kassenkategorie schlägt die Kategorie beim Import automatisch vor; nur bei Dokumenten ohne FEDAS muss sie von Hand gewählt werden (einmal pro Artikel, danach gemerkt).

## 3. Endziel (Vision)

> Ein **Warenwirtschaftssystem für alle 4 Filialen**, in dem jede Ware beim Eingang erfasst wird (Upload von Lieferschein/Rechnung oder manuell), das **alle je erfassten Artikel dauerhaft** mit Preisverlauf speichert, **pro Filiale den aktuellen Lagerbestand** führt, Filialen beim **Runterschreiben** unterstützt — und später mit der **Kasse** verbunden wird, sodass verkaufte Artikel automatisch ausgebucht werden und an der Kasse nur noch gescannt wird.

## 4. Entscheidungen (Stand 20.09.2026)

| # | Thema | Entscheid |
|---|---|---|
| D1 | Artikelstamm | **Gemeinsam für alle Filialen.** Nur Bestand, Wareneingänge und Reduktionen sind filialbezogen |
| D2 | Server | **Ein zentraler Server in Volketswil (SF1).** Netzwerk/VPN-Konzept wird später gemeinsam erarbeitet |
| D3 | Arbeitsplätze | ca. 4–5 PCs pro Filiale |
| D4 | Kasse | Internes Intersport-Kassensystem; Kategorien siehe oben (Hartware bestätigt). **Zugriff/Schnittstelle: Fabian klärt mit Intersport ab.** Anbindung später |
| D5 | Reduktion | **Jede Filiale entscheidet selbst**, aber es gibt eine **zentrale Empfehlung**, damit möglichst alle Filialen gleich reduzieren. Regeln siehe 8.3: Eingang ‑30 %, nach **18 Monaten** Hinweis ‑50 %, nach **36 Monaten** ‑70 % — gerechnet **pro Filiale** ab **letztem Wareneingang derselben Artikelnummer in dieser Filiale**; Nachlieferung startet die Uhr für **beide** Stufen neu |
| D6 | Dokumente | Es kommen Rechnungen, Lieferscheine **und Auftragsbestätigungen**; weitere Beispiele werden laufend nachgereicht. **Bestand wird erst gebucht, wenn die Ware eingetroffen ist** |
| D7 | Einkaufspreis | **Optional** speichern, falls im Dokument vorhanden — keine Priorität |
| D8 | Rechte | Mitarbeiter dürfen vorerst **alles ausser Dokumente hochladen/bearbeiten**. Feinere Rechte später |
| D9 | **Keine KI / keine externen Dienste** | Alle Dokumente werden **lokal auf dem eigenen Server** erkannt — keine Weitergabe an Drittanbieter, keine KI-Extraktion |
| D10 | EAN | EAN muss **nachträglich erfassbar** sein. Wird nie eine nachgetragen, **generiert das System eine interne EAN** (inkl. Etikett) |
| D11 | GEWA | Externes Aufbereitungslager → eigener Lagerort, Ware wird von dort an Filialen umgelagert |
| D12 | Chris Sports | „Preis“ auf deren Dokumenten = **UVP** (Rabatt 70 % → EK = 30 % des UVP) |
| D13 | Eingangsdatum bei GEWA-Ware | Ware, die an die GEWA geht, bekommt **noch kein Eingangsdatum**. Das Datum wird gesetzt/nachgetragen, **sobald die Ware in der Filiale angekommen ist** — erst ab dann zählt die Lagerdauer |
| D14 | Etikettendrucker | Eine Etikettenmaschine ist vorhanden, alle PCs im WLAN können darauf drucken (Modell noch unbekannt) |
| D15 | Scanner | Heute nur an den 2 Kassen-PCs. Für Wareneingang/EAN-Nachtrag werden **Funk-Scanner** angeschafft |
| D16 | Kategorien | Velo und Food haben **keine** Unterkategorien; „Hartware“ bestätigt |
| D17 | Umlagerung Filiale → Filiale | Ware **behält ihr ursprüngliches Eingangsdatum** (wird durch Umbuchen nicht „verjüngt“). Nur GEWA → Filiale setzt das Datum erstmals (D13) |

## 5. Anforderungen

### Muss (MVP)

| # | Anforderung | Details |
|---|---|---|
| Z1 | **Wareneingang per Upload** | Rechnung / Lieferschein / Auftragsbestätigung hochladen → Positionen extrahieren → prüfen/korrigieren → bestätigen |
| Z2 | **Wareneingang manuell** | Artikel ohne Dokument erfassen, schnell hintereinander, mit EAN-Scanner |
| Z3 | **Artikelstamm „für immer“** | Jeder je erfasste Artikel bleibt gespeichert, auch ausverkauft. Suche nach EAN, Marke, Artikelnr., Bezeichnung, Kategorie |
| Z4 | **UVP-Preisverlauf** (+ optional EK) | UVP je Artikel über die Zeit; Preis älterer Artikel nachschlagen |
| Z5 | **Lagerbestand pro Filiale** | Aktueller Bestand je Variante × Filiale, inkl. Eingangsdatum (für Lagerdauer) |
| Z6 | **Manuelles Ausbuchen** | Verkäufe/Abgänge per Scan von Hand ausbuchen (später automatisch durch die Kasse) |
| Z7 | **Filialen & Lagerorte** | SF1–SF4 + GEWA; getrennte Bestände/Wareneingänge, gemeinsamer Artikelstamm, Filialwechsel, Umlagerung GEWA → Filiale |
| Z8 | **Mehrsprachig** | DE / EN / FR |
| Z9 | **Kassenkategorien** | Jeder Artikel hat Hauptgruppe + Sportbereich wie in der Kasse; Vorschlag via FEDAS |
| Z10 | **Runterschreib-Hinweise** | Übersicht/Benachrichtigung je Filiale gemäss Regeln in 8.3 (18 / 36 Monate) |
| Z11 | **EAN nachtragen / generieren** | EAN jederzeit per Scan nachtragen; sonst interne EAN generieren und Etikett drucken |

### Bereits vorhanden und weiterhin gewünscht
Zweistufiger Import mit Vorschau & Korrektur, Stapel-Import, OCR für Papier-Scans, Artikelnotizen, Excel-Export, Kassennummer-Login, Hell-/Dunkelmodus, Barrierefreiheit (grosse Schrift/Spaltenwahl), Backups, Docker-Deployment.

### Später (Backlog, wird laufend ergänzt)
- [ ] **Kassenanbindung**: Scan an der Kasse liefert Kategorie, UVP, Reduktion; Verkauf bucht automatisch aus
- [ ] Preisschilddruck mit reduziertem Preis
- [ ] Umlagerungen zwischen Filialen (GEWA → Filiale ist bereits MVP)
- [ ] Inventur (Zählen per Scanner, Differenzen buchen)
- [ ] Auswertungen: Lagerwert, Lagerdauer, Abverkauf nach Marke/Kategorie/Filiale, Marge (wenn EK vorhanden)
- [ ] Feinere Benutzerrechte
- [ ] *(weitere Ziele werden hier ergänzt)*

## 6. Analyse der Beispieldokumente (20.09.2026)

| Beispiel | Dokumenttyp | PDF-Art | EAN | UVP | EK | Farbe/Grösse | Besonderheiten |
|---|---|---|---|---|---|---|---|
| **Intersport** (Rg. 9001759392, 21 S., ECOM-Retouren) | Rechnung | Text | ✅ | ✅ | ✅ (Preis) | ✅ 2. Zeile „(Farbe)/Grösse“ | FEDAS-Code, Marke, Lief.-Art.-Nr.; **bestehender Parser** |
| **Externer Händler** (Rg. 72586, Bollé Close Out, Chippis) | Rechnung (mit Lieferschein-Nr.) | Text | ❌ | ❌ | ✅ | ✅ unter Bezeichnung | **Lieferadresse Conthey**, Rechnung an Volketswil → Filiale aus Lieferadresse ableiten |
| **Alpina** (AB 160165) | Auftragsbestätigung | Text | ❌ | ✅ | ✅ HEK + Netto | ✅ in Bezeichnung (z. B. „matt 52-56“) | Liefertermin je Position |
| **Chris Sports** (AB CS-12809663, Giro-Socken) | Auftragsbestätigung (Liquidation) | Text | ✅ | ✅ („Preis“ = UVP) | ✅ Betrag | ✅ „Farbe,Grösse“ je Zeile | Varianten sauber unter Artikel gruppiert |
| **CMP 2** (AB 2026A-F30-246) | Auftragsbestätigung | Text | ❌ | ✅ (VK) | ✅ (EK) | ✅ **Grössen-Matrix** (92–176) | Lieferung an **GEWA** (externes Lager) |
| **CMP 1** (Bestellung 22065) | Bestellung | **Scan (Bild)** | ❌ | ✅ (VK) | ✅ (Preise) | ✅ Grössen-Matrix | Farbige Tabelle, OCR-Text unbrauchbar |

### Erkenntnisse & Konsequenzen

1. **Jedes Lieferanten-Layout ist anders** — 6 Beispiele, 6 Layouts, weitere folgen. Wegen D9 (keine KI) → **regelbasierte Erkennung, komplett lokal** (siehe 8.4):
   - **Lieferanten-Erkennung** automatisch über Merkmale im Dokument (MwSt.-Nr., Firmenname, GLN, Tabellenkopf).
   - **Ein Parser pro Layout** als Plug-in; wiederkehrende Muster (Tabelle mit Kopfzeile, Farbe/Grösse in Folgezeile, Grössen-Matrix) als gemeinsame Bausteine, damit ein neues Layout meist nur eine kleine Konfiguration braucht.
   - **Ehrliche Einschränkung:** Ein Layout, das das System noch nie gesehen hat, kann ohne KI nicht automatisch gelesen werden. Ablauf dann: Dokument wird als „unbekanntes Layout“ markiert → Positionen manuell erfassen (Kopfdaten vorausgefüllt) → Beispiel an Fabian/Entwicklung → Parser ergänzen. Je mehr Beispiele, desto seltener passiert das.
2. **Viele Dokumente haben keine EAN** (4 von 6), und auch physisch hat nicht jeder Artikel einen Barcode. → Varianten müssen **ohne EAN** existieren können (Schlüssel: Lieferant + Artikelnummer + Farbe + Grösse). EAN jederzeit **per Scan nachtragen**; hat ein Artikel nie eine, **generiert das System eine interne EAN-13** (GS1-Bereich 20–29 für interne Nummern, mit Prüfziffer — kollidiert nie mit echten Hersteller-EANs) und druckt ein Etikett. So ist später **jeder** Artikel an der Kasse scanbar.
3. **UVP fehlt teilweise** (externer Händler) → in der Vorschau als Pflichtfeld nachfragen, sonst kein Verkaufspreis berechenbar. Bereits bekannter UVP derselben Artikelnummer wird vorgeschlagen.
4. **Auftragsbestätigung ≠ Wareneingang.** → Dokument erzeugt einen **erwarteten Wareneingang**; erst „Ware eingetroffen“ (mit Mengenkontrolle) bucht den **Lagerzugang** (D6).
5. **Lagerort aus Lieferadresse** erkennbar (SF1–SF4 oder GEWA, Adressen siehe oben) → automatische Vorauswahl beim Upload, manuell änderbar. Ware an GEWA wird später an eine Filiale umgelagert.
6. **Grössen-Matrix** (CMP): eine Zeile = mehrere Grössen mit je eigener Menge → Parser muss in Einzelvarianten auflösen.
7. **ECOM** braucht keinen eigenen Parser: Intersport-Layout, Quelle über Referenzfeld erkennen.

## 7. Abgleich Zielbild ↔ aktuelles Repo

| Bereich | Heute im Repo | Lücke zum Ziel |
|---|---|---|
| Upload & Parsing | ✅ Intersport-PDF, OCR (Tesseract, lokal), Vorschau, Korrektur, Stapel | Nur 1 Layout; Lieferant hartcodiert; keine Lieferanten-Erkennung; keine Dokumenttypen; keine Grössen-Matrix; OCR für farbige Tabellen-Scans zu schwach |
| Manuelle Erfassung | ❌ | neu |
| Artikelstamm | ✅ `products` (EAN eindeutig), Varianten-Gruppierung zur Laufzeit | Kein Modell↔Variante; **EAN-Pflicht blockiert Artikel ohne EAN**; keine Kategorien |
| Preise | ✅ UVP je Rechnungsposition | EK optional, Reduktionsstufen fehlen |
| Lagerbestand | ❌ | neu (Lagerbewegungen, Lagerdauer, Lagerort GEWA) |
| Filialen | ✅ `lagerorte` (SF1–SF4 + GEWA) + `benutzer_lagerorte` (m:n), Filialwechsel in der Oberfläche | Bestand/Wareneingänge/Reduktionen noch nicht filialbezogen (Phase B/C) |
| Sprache | ✅ i18n DE/FR/EN (Katalog + Sprachwahl pro Benutzer, inkl. Backend-Fehlermeldungen) | — |
| Rollen | Mitarbeiter / Filialleiter (`chef`) / Admin-Zentrale (`admin`) | Rollen inkl. Admin und Rechte gemäss Regel 9 umgesetzt (Phase A, Punkt 1) |
| Deployment | Docker, 1 Laden-Server | Zentraler Server Volketswil, Zugriff aus 4 Filialen |

## 8. Architektur-Vorschläge

### 8.1 Deployment
- Ein Server in **Volketswil**, eine PostgreSQL-DB, Trennung über `filiale_id`.
- Andere Filialen greifen über **VPN** zu (z. B. WireGuard/Tailscale — wird später gemeinsam aufgesetzt). Nicht ungeschützt ins Internet.
- ⚠️ Login nur mit Kassennummer ist nur im geschützten Netz vertretbar → Zugriff auf VPN/Ladennetz beschränken.

### 8.2 Datenmodell (Vorschlag)

| Tabelle | Zweck | Filialbezogen? |
|---|---|---|
| `lagerorte` | SF1–SF4 (Verkauf) + GEWA (kein Verkauf), inkl. Adresse (für Auto-Erkennung) — **umgesetzt** | – |
| `lieferanten` | Name, Typ (Intersport / ECOM / Dritthändler / Extern), Parser-Zuordnung | nein |
| `kategorien` | Hauptgruppe × Sportbereich (Kassenstruktur) + FEDAS-Mapping | nein |
| `artikel` | Modell: Marke, Lieferant, Lief.-Art.-Nr., Bezeichnung, Kategorie, FEDAS | nein |
| `varianten` | Farbe, Grösse, **EAN (optional, eindeutig wenn vorhanden)**, Flag `ean_intern` für generierte EANs | nein |
| `preise` | Verlauf je Variante: UVP, EK (optional), Datum, Quelle | nein |
| `dokumente` | Upload: Typ (Rechnung/Lieferschein/AB/Bestellung), Datei, Hash, Lieferant, erkannte Filiale | ja |
| `wareneingaenge` + `positionen` | Erwartet → erhalten; Menge, UVP, EK, Original-Snapshot | ja |
| `lagerbewegungen` | Journal: Zugang, Verkauf, Ausbuchung, Korrektur, Umlagerung — mit Menge ±, Grund, Benutzer, Zeit | ja |
| `bestand` | Aktueller Bestand je Variante × Filiale + ältestes Eingangsdatum | ja |
| `reduktionen` | Stufe je Artikel × Filiale mit Gültig-ab; zentrale **Empfehlung** separat | ja |
| `benutzer`, `benutzer_filialen` | Rollen, Filialzuordnung, Sprache — **Filialzuordnung als `benutzer_lagerorte` (m:n) umgesetzt**, Sprache folgt in Phase A Punkt 2 | teils |

Kernprinzipien: **Bestand nie überschreiben, sondern als Bewegung buchen.** Für die Reduktionsregeln zählt das Datum des **letzten Wareneingangs derselben Artikelnummer** (siehe 8.3).

### 8.3 Runterschreib-Logik (D5)

| Stufe | Wann | Referenzdatum |
|---|---|---|
| ‑30 % | beim Eingang (Standard) | – |
| ‑50 % | Hinweis nach **18 Monaten** | letzter Wareneingang derselben **Artikelnummer in dieser Filiale** — Nachlieferung startet die Uhr neu |
| ‑70 % | Hinweis nach **36 Monaten** | letzter Wareneingang derselben **Artikelnummer in dieser Filiale** — Nachlieferung startet die Uhr neu |

- „Artikelnummer“ = Lieferanten-Artikelnummer (Modell), also über alle Farben/Grössen hinweg.
- Berechnung **pro Filiale** (D5): Eine Lieferung nach SF2 setzt die Uhr in SF1 nicht zurück.
- Ware ohne Eingangsdatum (z. B. noch in der GEWA) erzeugt **keine** Hinweise.
- Zentrale (Admin) sieht die Empfehlungen aller Filialen und kann eine **einheitliche Empfehlung** setzen; jede Filiale übernimmt oder weicht bewusst ab (Abweichungen sichtbar).
- Hinweise als Liste „Zum Runterschreiben fällig“ + Zähler im Dashboard; Schwellen (18/36 Monate) konfigurierbar.

### 8.4 Dokumenterkennung ohne KI (D9)
- **Text-PDFs** (5 von 6 Beispielen): Wortkoordinaten auslesen (PyMuPDF, wie heute) → Layout-Parser.
- **Scans** (z. B. CMP-Bestellung): lokale OCR mit **Tesseract** (bereits im Projekt) + Bildvorverarbeitung (Graustufen, Kontrast, Farbhintergründe entfernen) + Tabellen-/Linienerkennung (OpenCV). Qualität bei farbigen Tabellen begrenzt → Vorschau zeigt unsichere Felder markiert zur Korrektur.
- **Lieferanten-Erkennung** über Merkmale → passender Parser; nichts erkannt → „unbekanntes Layout“ → manuelle Erfassung.
- Alles läuft auf dem Server in Volketswil; keine Daten verlassen das Firmennetz.

### 8.5 Ablauf GEWA → Filiale (D13)
Umbuchungen passieren spontan — deshalb bewusst einfach:

| Schritt | Im System | Eingangsdatum (Lagerdauer) |
|---|---|---|
| 1. Lieferung an GEWA | Wareneingang auf Lagerort **GEWA** (Lieferadresse wird erkannt) | **leer** |
| 2. Aufbereitung in der GEWA | Ware ist sichtbar unter „In der GEWA“, kann aber nicht verkauft/ausgebucht werden | leer |
| 3. Ware geht in Filiale X | **Umlagerung GEWA → SFx**: Artikel/Positionen oder ganze Lieferung auswählen | – |
| 4. Ankunft bestätigen | Filiale bestätigt Ankunft; Datum wird vorgeschlagen (heute), kann **nachträglich/rückwirkend** eingetragen werden — auch als Sammel-Nachtrag für mehrere Artikel | **gesetzt** → ab jetzt zählen 18/36 Monate |

Zusätzlich: Liste „**Unterwegs / ohne Eingangsdatum**“ je Filiale, damit nichts vergessen geht.

### 8.6 Hardware: Etiketten & Scanner
- **Etiketten:** Das System erzeugt Etiketten (Barcode EAN-13 inkl. interner EAN, Marke, Bezeichnung, Grösse, UVP) als **PDF im passenden Etikettenformat** → druckbar von jedem PC auf die vorhandene Etikettenmaschine, ohne Treiber-Spezialitäten. Falls die Maschine eine eigene Druckersprache kann (z. B. Zebra/ZPL), später Direktdruck als Option. **Modell + Etikettengrösse notieren** (siehe offene Fragen).
- **Scanner:** Das Web-System funktioniert mit jedem Scanner im **Tastatur-Modus (HID)** — keine Software nötig. Empfehlung für die Funk-Scanner: 1D/2D-Scanner mit **USB-Funk-Dongle oder Bluetooth**, HID-Modus, liest **EAN-13 + Code 128**, idealerweise mit **Speicher-/Batch-Modus** (im Lager scannen ohne Funkreichweite). Erst 1 Gerät testen, dann pro Filiale 1–2 Stück.

### 8.7 Mehrsprachigkeit
Übersetzungsdateien `de/en/fr`, Sprache pro Benutzer; Artikeltexte bleiben in Lieferantensprache.

### 8.8 Was bleibt
FastAPI, PostgreSQL, Alembic, Docker, Vanilla-JS-Frontend, zweistufiger Import mit Hash-Prüfung, Audit-Snapshot, Advisory-Lock, Tests, Backups.

## 9. Roadmap

| Phase | Inhalt | Ergebnis |
|---|---|---|
| **A — Fundament** | Filialen, Rollen (D8), Filialwechsel, i18n-Gerüst, neues Datenmodell inkl. Kategorien, Migration der bestehenden Daten (→ SF1) | mehrfilialfähig & mehrsprachig |
| **B — Wareneingang v2** | Dokumenttypen, Lieferanten-Erkennung, erwartet→eingetroffen, Lagerort aus Lieferadresse, manuelle Erfassung mit Scanner, EAN nachtragen/generieren + Etikett, FEDAS-Kategorievorschlag | jede Ware kommt ins System |
| **C — Lagerbestand** | Lagerbewegungen, Bestand je Lagerort, Umlagerung GEWA → Filiale, Ausbuchen per Scan, Korrekturen | aktueller Bestand |
| **D — Preise & Reduktion** | UVP/EK-Verlauf, Reduktionsstufen, zentrale Empfehlung, 18-/36-Monats-Hinweise | Runterschreiben unterstützt |
| **E — Weitere Lieferanten** | Parser für Alpina, Chris Sports, CMP (Text + Scan), externer Händler; weitere laufend nach Beispielen | Upload für alle bekannten Lieferanten |
| **F — Betrieb** | Server Volketswil, VPN, externe Backups, Datenumzug | alle 4 Filialen produktiv |
| **G — Kasse** | Anbindung Intersport-Kasse (abhängig von Abklärung mit Intersport) | kein manuelles Eintippen mehr |

## 10. Offene Fragen

Alle Fragen aus Rev. 2 und Rev. 3 sind beantwortet (D1–D16). Noch offen:

1. **Etikettenmaschine:** Marke/Modell und Etikettengrösse (bei Gelegenheit abfotografieren).
2. **Kasse:** Ergebnis der Abklärung mit Intersport (Zugriff/Schnittstelle).

### Laufend
- Weitere Beispieldokumente sammeln (insb. Lieferscheine, Nike/adidas/Puma, ECOM) → Parser-Liste in Abschnitt 6 ergänzen.
- Funk-Scanner: 1 Testgerät beschaffen.

## 11. Stand der Umsetzung

| Phase | Status |
|---|---|
| Konzept (D1–D17) | ✅ abgeschlossen (20.09.2026) |
| A — Fundament, Punkt 1 (Lagerorte, Rollen, Benutzer↔Lagerort, Filialwechsel) | ✅ abgeschlossen, Branch `feature/warenwirtschaft-v2` |
| A — Fundament, Punkt 2 (i18n DE/FR/EN, Sprachwahl pro Benutzer) | ✅ abgeschlossen, Branch `feature/warenwirtschaft-v2` |
| A — Fundament, Punkte 3–4 (neues Datenmodell, Migration Altdaten, Live-Import, Tests/Doku) | ✅ abgeschlossen, Branch `feature/warenwirtschaft-v2` |
| B — Wareneingang v2: FEDAS-Kategorievorschlag | ⏳ Infrastruktur fertig, restliche Codes offen (siehe unten) |
| B (übrige Punkte), C–G | offen |

**Details zu Phase A, Punkt 1** (siehe `docs/datenmodell.md` für die Tabellen im Detail):
- Neue Tabellen `lagerorte` (SF1–SF4 + GEWA, Seed-Daten) und `benutzer_lagerorte` (m:n, mit `ist_primaer`) via Alembic-Migration `a1b2c3d4e5f6`; bestehende Benutzer auf SF1 zugeordnet.
- `users.role` um `admin` erweitert (Rollen: `mitarbeiter`, `chef` = Filialleiter, `admin` = Zentrale), Rechte gemäss Regel 9 in `app/routers/auth.py` und `app/routers/article_details.py` umgesetzt.
- Filialwechsel in der Oberfläche: `/api/me` liefert aktive Filiale + wählbare Filialen, `POST /api/active-lagerort` wechselt sie (Admin zusätzlich „Alle Filialen“); UI-Auswahl in der Session-Leiste (`app/static/js/session.js`).
- `scripts/manage_users.py` erweitert um Filialzuordnung (`add-mitarbeiter`/`add-chef <kassennummer> <name> <lagerort-codes...>`) und `add-admin`.
- Bestand/Wareneingänge/Reduktionen sind noch nicht filialbezogen — das kommt mit dem neuen Datenmodell in Phase A Punkt 3 bzw. den Phasen B–D.

**Details zu Phase A, Punkt 2** (siehe `docs/architektur.md` Abschnitt „Mehrsprachigkeit (i18n)"):
- `users.language` (DE/FR/EN, Default `de`) via Alembic-Migration `b2c3d4e5f6a7`.
- Katalog als einzige Quelle: `app/static/i18n/{de,fr,en}.json` (327 Keys), gelesen von Backend (`app/core/i18n.py`, `translate()`) und Frontend (`app/static/js/i18n.js`, `data-i18n`-Attribute + `window.SportfabrikI18n.t()`).
- Spracherkennung pro Request: eingeloggt die Kontosprache, anonym (`/login`) der `Accept-Language`-Header (`app/routers/auth.py`, `get_language`/`get_language_optional`).
- Alle bestehenden Templates (`login.html`, `dashboard.html`, `preview.html`, `articles.html`, `history.html`) und JS-Dateien auf Keys umgestellt; **alle** `HTTPException`-Fehlermeldungen im Backend (Router **und** Services: `parser.py`, `ocr.py`, `corrections.py`, `importer.py`) laufen über `translate()`.
- Sprachwahl: `POST /api/language` (Konto), Umschalter DE/FR/EN in der Session-Leiste bzw. auf der Login-Seite (`localStorage` vor dem Login).
- Bewusst nicht übersetzt: Artikeldaten aus Lieferantendokumenten (Regel 7), feste deutsche Textanker im INTERSPORT-Layout (Parser sucht z. B. immer „Rechnungsdatum" im PDF), Excel-Export-Spaltenüberschriften (eigenes Dokumentformat, offener Punkt).
- Tests: `tests/test_i18n.py` (Katalog/`translate()`, Spracherkennung, `/api/language`); Gesamtsuite jetzt 108 bestandene Tests (vorher 86).

**Details zu Phase A, Punkte 3–4** (siehe `docs/datenmodell.md` für die Tabellen im Detail):
- Neues Datenmodell gemäss Abschnitt 8.2 vollständig umgesetzt: `lieferanten`, `kategorien` (35 Kassenkategorien), `artikel`, `varianten`, `preise`, `dokumente`, `wareneingaenge`, `wareneingang_positionen` (+`_quelle`), `lagerbewegungen`, `bestand` via Alembic-Migration `c3d4e5f6a7b8`. Bestand wird jetzt append-only über `lagerbewegungen` geführt (Regel 2), nicht mehr implizit über `invoice_items`.
- Bestehende Daten (`products`/`invoices`/`invoice_items`/`invoice_item_sources`/`article_notes`) vollständig und verlustfrei migriert (alte Tabellen bleiben unangetastet, „nie verwerfen") — einzige bewusste Lücke: die frühere INTERSPORT-eigene Artikelnummer (`products.article_no`) wird nicht übernommen, nur noch die Lieferanten-Artikelnummer als Artikel-Schlüssel (Regel 5), der Altwert bleibt in `products` einsehbar.
- **Live-Import umgestellt**: `app/services/importer.py` schreibt neu importierte Rechnungen direkt ins neue Schema (Artikel-Gruppierung, Varianten mit/ohne EAN, Preise, Lagerbewegungen, Bestand); Wareneingänge werden gegen die **aktive Filiale** des hochladenden Kontos gebucht (`require_active_lagerort` in `app/routers/auth.py`) statt fest gegen SF1. `delete_invoice()` räumt Lagerbewegungen/Bestand/Preise konsistent mit auf.
- `app/services/parser.py` erfasst jetzt zusätzlich den FEDAS-Code je Position (`artikel.fedas_code`) — die automatische Kategorie-Vorschlagslogik daraus ist Teil von Phase B (siehe unten).
- `app/services/article_groups.py` nutzt die echte Fremdschlüsselbeziehung (`varianten.artikel_id`) statt einer Laufzeit-Query über Marke + Lieferanten-Artikelnummer.
- Alle betroffenen Router (`catalog.py`, `history.py`, `article_details.py`, `dashboard.py`) sowie `article_export.py` auf das neue Schema umgestellt. Die frühere separate Spalte „Art. Nr." (INTERSPORT-eigene Nummer) ist aus Artikelsuche, Excel-Export und Filtern entfernt (siehe oben); `/api/articles` filtert jetzt über `supplier_article_no` statt `article_no`.
- Tests vollständig an das neue Schema angepasst (u. a. `test_importer.py`, `test_catalog.py`, `test_history.py`, `test_article_details.py`, `test_article_export.py`, `test_corrections.py`); Migration zusätzlich gegen echtes PostgreSQL verifiziert (leere DB, DB mit repräsentativen Altdaten, Downgrade/Upgrade-Rundlauf) sowie der komplette Live-Import- und Router-Pfad per Smoke-Test gegen PostgreSQL durchgespielt.
- Bekannte Einschränkung: `bestand` nach der Migration entspricht der kumulierten historischen Wareneingänge (das alte System kannte keine Verkäufe/Ausbuchungen) — kein exakter physischer Bestand, bis Phase C (manuelles Ausbuchen) bzw. eine Inventur das korrigiert.

**Details zu Phase B, FEDAS-Kategorievorschlag** (erster Teilschritt, siehe Roadmap Abschnitt 9):
- `app/core/fedas.py`: feste Zuordnung 1. FEDAS-Ziffer → Hauptgruppe (`1`=Hartware, `2`=Textil, `3`=Schuhe) sowie Ziffern 2–3 → Sportbereich, aktuell nur die aus echten Rechnungen bestätigten Codes (`24`=Tennis, `32`=Fussball, `60`=Velo, `64`=Outdoor, `75`=Freizeit — 6 der 11 Sportbereiche fehlen noch: Winter, Kids, Baden, Indoor, Running, Rollsport, ebenso die Produktart-Ziffer(n) für die Hauptgruppen Velo/Food selbst).
- `app/services/importer.py` setzt `artikel.kategorie_id` automatisch beim Anlegen eines neuen Artikels, sofern der FEDAS-Code eine bekannte Kombination ergibt; ist der Code (noch) nicht zugeordnet, bleibt `kategorie_id` leer. Ein bereits gesetzter Wert wird von späteren Rechnungen nie überschrieben („einmal pro Artikel, danach gemerkt"); fehlt er noch, wird er bei einer späteren Rechnung mit bekanntem Code nachträglich gesetzt.
- Bewusst noch nicht gebaut: eine Oberfläche zur manuellen Kategorie-Wahl, wenn der FEDAS-Code fehlt oder unbekannt ist (nächster Teilschritt) — bis dahin bleibt `kategorie_id` in diesem Fall einfach leer, ohne Auswirkung auf den restlichen Import.
- Tests: `tests/test_fedas.py` (reine Zuordnungslogik), `tests/test_importer_fedas.py` (Zusammenspiel mit dem Import: neuer Artikel, unbekannter/fehlender Code, nachträgliches Befüllen, kein Überschreiben) — zusätzlich per Smoke-Test gegen echtes PostgreSQL verifiziert.

*Dieses Dokument wird bei jeder Entscheidung/Phase nachgeführt. Die Master-Kopie liegt im Claude-Projekt „Sportfabrik WarenWirtschaftsSystem“.*
