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

## 4. Entscheidungen (Stand 21.09.2026)

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
| D14 | Etikettendrucker | **Sato CL4NX Plus** (Industrie-Etikettendrucker), alle PCs im WLAN können darauf drucken. Etikettengrösse noch offen (siehe Abschnitt 10) |
| D15 | Scanner | Heute nur an den 2 Kassen-PCs. Für Wareneingang/EAN-Nachtrag werden **Funk-Scanner** angeschafft |
| D16 | Kategorien | Velo und Food haben **keine** Unterkategorien; „Hartware“ bestätigt |
| D17 | Umlagerung Filiale → Filiale | Ware **behält ihr ursprüngliches Eingangsdatum** (wird durch Umbuchen nicht „verjüngt“). Nur GEWA → Filiale setzt das Datum erstmals (D13) |
| D18 | Position ohne EAN beim Upload *(21.09.2026)* | **Mit Hinweis durchlassen** — der Import wird davon nicht gesperrt (Regel 5). Eine EAN, die im Dokument steht, aber unleserlich ist, bleibt dagegen eine blockierende Warnung: das ist ein Lesefehler-Verdacht und keine bewusst fehlende Nummer |
| D19 | Lagerort aus der Lieferadresse *(21.09.2026)* | Der erkannte Lagerort ist **nur ein Vorschlag** und bleibt beim Import änderbar |
| D20 | Ein Beleg, eine Lieferadresse *(21.09.2026)* | Ein Dokument hat **eine** Lieferadresse, also einen Wareneingang auf einen Lagerort. Wird die Ware danach auf Filialen verteilt, läuft das ganz normal über eine **Warenverschiebung (Umlagerung)** — nicht über mehrere Lagerorte am selben Dokument |
| D21 | „Ware eingetroffen" bestätigen *(21.09.2026)* | Dürfen **auch Mitarbeiter** — das ist Lagerarbeit, kein Dokument-Recht (Regel 9) |
| D22 | Teillieferung *(21.09.2026)* | Kommt weniger an als erwartet, bleibt die **Restmenge offen** („erwartet"), damit fehlende Ware sichtbar bleibt |
| D23 | Manuelle Erfassung, Pflichtfelder *(21.09.2026)* | **Marke + Bezeichnung + Menge + UVP** genügen. Alles andere (Lieferant, Kategorie, Farbe, Grösse, EAN) ist optional |
| D24 | Interne EAN *(21.09.2026)* | Wird **auf Knopfdruck** erzeugt (wenn ein Etikett gebraucht wird), nicht automatisch beim Import |
| D25 | Inhalt des Etiketts *(21.09.2026)* | **Jahrgang** (Jahr des Wareneingangs), **Lieferant**, **UVP** und die **Reduktionsstufe** (30 / 50 / 70 %). Ob zusätzlich der Barcode aufs Etikett soll, ist noch offen (siehe Abschnitt 10) |
| D26 | Wer auf welchen Lagerort bucht *(21.09.2026, bestätigt)* | **Wer Dokumente hochladen darf, darf auf jeden Lagerort buchen** (eigene Filiale zuoberst). Das Ziel bestimmt der Beleg über seine Lieferadresse, nicht die gerade aktive Filiale — sonst liesse sich eine Lieferung an eine andere Filiale oder an die GEWA gar nicht erfassen. Filialwechsel und Leseansichten bleiben bei den zugewiesenen Filialen |
| D27 | Ware ohne Dokument *(21.09.2026)* | Manuelle Erfassung ist ein **direkter Wareneingang ohne Beleg** — es entsteht kein Dokument und keine Belegnummer. Gebucht wird sofort auf die gewählte Filiale; nachvollziehbar bleibt alles über das Journal `lagerbewegungen` (wer, wann, wie viel) |

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
| Upload & Parsing | ✅ Intersport-PDF, OCR (Tesseract, lokal), Vorschau, Korrektur, Stapel, **Parser-Registry mit Lieferanten-/Dokumenttyp-Erkennung** (Phase B, Teilaufgabe 1) | Bisher nur 1 Layout registriert (weitere in Phase E); keine Grössen-Matrix; OCR für farbige Tabellen-Scans zu schwach; erwartet→eingetroffen, Lagerort aus Lieferadresse und manuelle Erfassung offen |
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
- **Etiketten:** Drucker ist ein **Sato CL4NX Plus** (D14). Das System erzeugt die Etiketten als **PDF im passenden Etikettenformat** → druckbar von jedem PC über den normalen Druckertreiber, ohne Treiber-Spezialitäten. Der CL4NX Plus versteht zusätzlich seine eigene Druckersprache (SBPL) und kann fremde emulieren — **Direktdruck** bleibt damit als späterer Ausbau offen, ist aber für den Start nicht nötig. Inhalt gemäss D25: Jahrgang des Wareneingangs, Lieferant, UVP, Reduktionsstufe. Zwei Konsequenzen: (1) Weil die **Reduktionsstufe auf dem Etikett steht**, braucht jedes Runterschreiben ein neues Etikett — die Liste „Zum Runterschreiben fällig" (Phase D) soll darum direkt zum Etikettendruck führen. (2) Weil der **Jahrgang** aus dem Wareneingang kommt, lässt sich für Ware in der GEWA noch kein Etikett drucken (D13: dort gibt es noch kein Eingangsdatum). Noch offen: Etikettengrösse und ob der Barcode mit aufs Etikett soll (Abschnitt 10).
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

Alle Fragen aus Rev. 2 und Rev. 3 sind beantwortet (D1–D27). Noch offen:

1. **Etikettengrösse** des Sato CL4NX Plus (welche Rollen sind im Einsatz — Breite × Höhe in mm).
2. **Barcode aufs Etikett?** D25 nennt Jahrgang, Lieferant, UVP und Reduktionsstufe. Soll der EAN-Barcode **zusätzlich** drauf? Ohne ihn bleibt ein Artikel ohne Hersteller-EAN an der Kasse unscannbar — das war der Zweck der internen EAN (D10).
3. **Kasse:** Ergebnis der Abklärung mit Intersport (Zugriff/Schnittstelle).
4. **Filialbezug beim Lesen:** Sollen Übersicht, Rechnungsliste und Artikeldetails nur die eigene Filiale zeigen? (Heute zeigen sie allen Konten alle Filialen; Regel 9 regelt nur das Schreiben.)
5. **Ausbuchen per Scan** (Phase C): blockieren, wenn der Bestand dadurch negativ würde, oder mit Warnung zulassen?
6. **Umlagerung GEWA → Filiale** (Phase C): bucht die abholende Filiale selbst, oder die GEWA/Zentrale?
7. **Mehr geliefert als bestellt:** einfach buchen (heutiges Verhalten) oder warnen?

### Laufend
- Weitere Beispieldokumente sammeln (insb. Lieferscheine, Nike/adidas/Puma, ECOM) → Parser-Liste in Abschnitt 6 ergänzen.
- Funk-Scanner: 1 Testgerät beschaffen.

## 11. Stand der Umsetzung

| Phase | Status |
|---|---|
| Konzept (D1–D27) | ✅ abgeschlossen (D1–D17 am 20.09.2026, D18–D27 am 21.09.2026) |
| A — Fundament, Punkt 1 (Lagerorte, Rollen, Benutzer↔Lagerort, Filialwechsel) | ✅ abgeschlossen, Branch `feature/warenwirtschaft-v2` |
| A — Fundament, Punkt 2 (i18n DE/FR/EN, Sprachwahl pro Benutzer) | ✅ abgeschlossen, Branch `feature/warenwirtschaft-v2` |
| A — Fundament, Punkte 3–4 (neues Datenmodell, Migration Altdaten, Live-Import, Tests/Doku) | ✅ abgeschlossen, Branch `feature/warenwirtschaft-v2` |
| B — Wareneingang v2: FEDAS-Kategorievorschlag | ⏳ Infrastruktur fertig, restliche Codes offen (siehe unten) |
| B — Wareneingang v2, Teilaufgabe 1 (Parser-Registry, Lieferanten- und Dokumenttyp-Erkennung) | ✅ abgeschlossen, Branch `claude/next-step-l8tzqq` |
| B — Wareneingang v2, Teilaufgabe 2 (Belegnummer je Lieferant eindeutig) | ✅ abgeschlossen, Branch `claude/next-step-l8tzqq` |
| B — Wareneingang v2, Teilaufgabe 3 (EAN wirklich optional) | ✅ abgeschlossen, Branch `claude/next-step-l8tzqq` |
| B — Wareneingang v2, Teilaufgabe 4 (Lagerort aus der Lieferadresse) | ✅ abgeschlossen, Branch `claude/next-step-l8tzqq` |
| B — Wareneingang v2, Teilaufgabe 5 (erwartet → eingetroffen) | ✅ abgeschlossen, Branch `claude/next-step-l8tzqq` |
| B — Wareneingang v2, Teilaufgabe 6 (manuelle Erfassung mit Scanner) | ✅ abgeschlossen, Branch `claude/next-step-l8tzqq` |
| B — Wareneingang v2, Teilaufgaben 7–8 | offen (Aufteilung siehe unten) |
| C–G | offen |
| Oberfläche: durchgängiges Gestaltungssystem (alle Seiten) | ✅ abgeschlossen, Branch `feature/warenwirtschaft-v2` |

**Phase B — Wareneingang v2, Aufteilung in Teilaufgaben** (aus Roadmap
Abschnitt 9 und den offenen Punkten des Code-Reviews; eine Teilaufgabe = ein
Commit, Reihenfolge nach Abhängigkeit):

| # | Teilaufgabe | Status |
|---|---|---|
| B1 | **Parser-Registry**: ein Modul je Lieferanten-Layout mit gemeinsamer Schnittstelle, automatische Lieferanten- und Dokumenttyp-Erkennung, unbekanntes Layout klar melden | ✅ abgeschlossen |
| B2 | Belegnummer nur **je Lieferant** eindeutig (`UNIQUE (lieferant_id, dokumentnummer)`) inkl. Duplikatsprüfung im Importer — offener Punkt aus dem Review, Voraussetzung für den zweiten Lieferanten | ✅ abgeschlossen |
| B3 | **EAN wirklich optional** (Regel 5) auch in Parser/Korrekturen — Voraussetzung für manuelle Erfassung und für Lieferanten ohne EAN (4 von 6 Beispielen) | ✅ abgeschlossen |
| B4 | **Lagerort aus der Lieferadresse** erkennen (SF1–SF4/GEWA, Adressen in `lagerorte`) und beim Upload **vorschlagen**, änderbar (D19); ein Beleg = ein Lagerort (D20) | ✅ abgeschlossen |
| B5 | **Erwartet → eingetroffen**: Auftragsbestätigung/Bestellung erzeugen einen *erwarteten* Wareneingang, erst „Ware eingetroffen" (mit Mengenkontrolle) bucht Bestand (Regel 3, D6). Auch Mitarbeiter dürfen bestätigen (D21), Restmengen bleiben offen (D22) | ✅ abgeschlossen |
| B6 | **Manuelle Erfassung** (Z2) mit Scanner, schnell hintereinander — auch als Weg für unbekannte Layouts (Kopfdaten vorausgefüllt). Pflicht sind nur Marke + Bezeichnung + Menge + UVP (D23); ohne Beleg (D27) | ✅ abgeschlossen |
| B7 | **EAN nachtragen/generieren**: interne EAN-13 im GS1-Bereich 20–29 mit Prüfziffer (Regel 5/D10), **auf Knopfdruck** (D24) + Etikett als PDF für den Sato CL4NX Plus (D14/D25) | offen |
| B8 | **Kategorie von Hand wählen**, wenn der FEDAS-Code fehlt oder unbekannt ist (danach dauerhaft gemerkt) — Rest des ersten Teilschritts | offen |

**Details zu Phase A, Punkt 1** (siehe `docs/datenmodell.md` für die Tabellen im Detail):
- Neue Tabellen `lagerorte` (SF1–SF4 + GEWA, Seed-Daten) und `benutzer_lagerorte` (m:n, mit `ist_primaer`) via Alembic-Migration `a1b2c3d4e5f6`; bestehende Benutzer auf SF1 zugeordnet.
- `users.role` um `admin` erweitert (Rollen: `mitarbeiter`, `chef` = Filialleiter, `admin` = Zentrale), Rechte gemäss Regel 9 in `app/routers/auth.py` und `app/routers/article_details.py` umgesetzt.
- Filialwechsel in der Oberfläche: `/api/me` liefert aktive Filiale + wählbare Filialen, `POST /api/active-lagerort` wechselt sie (Admin zusätzlich „Alle Filialen“); UI-Auswahl in der Session-Leiste (`app/static/js/session.js`).
- `scripts/manage_users.py` erweitert um Filialzuordnung (`add-mitarbeiter`/`add-chef <kassennummer> <name> <lagerort-codes...>`) und `add-admin`.
- Bestand/Wareneingänge/Reduktionen sind noch nicht filialbezogen — das kommt mit dem neuen Datenmodell in Phase A Punkt 3 bzw. den Phasen B–D.

**Details zu Phase A, Punkt 2** (siehe `docs/architektur.md` Abschnitt „Mehrsprachigkeit (i18n)"):
- `users.language` (DE/FR/EN, Default `de`) via Alembic-Migration `b2c3d4e5f6a7`.
- Katalog als einzige Quelle: `app/static/i18n/{de,fr,en}.json` (330 Keys), gelesen von Backend (`app/core/i18n.py`, `translate()`) und Frontend (`app/static/js/i18n.js`, `data-i18n`-Attribute + `window.SportfabrikI18n.t()`).
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
- `app/services/importer.py` setzt `artikel.kategorie_id` automatisch, sobald eine Rechnungsposition einen bekannten FEDAS-Code mitbringt — beim Anlegen eines neuen Artikels ebenso wie beim Nachtragen an einem bestehenden (auch wenn die Variante über ihre EAN gefunden wurde, was für die migrierten Altartikel der Normalfall ist); ist der Code (noch) nicht zugeordnet, bleibt `kategorie_id` leer. Ein bereits gesetzter Wert wird von späteren Rechnungen nie überschrieben („einmal pro Artikel, danach gemerkt"); fehlt er noch, wird er bei einer späteren Rechnung mit bekanntem Code nachträglich gesetzt.
- Bewusst noch nicht gebaut: eine Oberfläche zur manuellen Kategorie-Wahl, wenn der FEDAS-Code fehlt oder unbekannt ist (nächster Teilschritt) — bis dahin bleibt `kategorie_id` in diesem Fall einfach leer, ohne Auswirkung auf den restlichen Import.
- Tests: `tests/test_fedas.py` (reine Zuordnungslogik), `tests/test_importer_fedas.py` (Zusammenspiel mit dem Import: neuer Artikel, unbekannter/fehlender Code, nachträgliches Befüllen, kein Überschreiben) — zusätzlich per Smoke-Test gegen echtes PostgreSQL verifiziert.

**Details zu Phase B, Teilaufgabe B1 — Parser-Registry mit Lieferanten- und
Dokumenttyp-Erkennung** (siehe `docs/architektur.md`, Abschnitt „PDF-Parsing:
ein Modul je Lieferanten-Layout"):
- Aus `app/services/parser.py` ist das Paket `app/services/parsers/` geworden:
  `base.py` (gemeinsame Bausteine — PDF **einmal** einlesen inkl. OCR-Rückfall
  je Seite, Wortkoordinaten zu Zeilen gruppieren, Zahlen in Schweizer
  Schreibweise), `intersport.py` (bisheriges Layout als erstes Plug-in) und
  `__init__.py` als Registry. Schnittstelle je Layout-Modul:
  `KEY` (= `lieferanten.parser_key`), `LIEFERANT_NAME`, `detect()`, `parse()`,
  `dates()`. Ein weiteres Layout (Phase E) braucht damit nur ein neues Modul
  und einen Eintrag in `PARSERS`.
- **Lieferanten-Erkennung** über Merkmale im Dokument statt hartcodiert: jedes
  Modul bewertet das Dokument mit einer Punktzahl, die höchste gewinnt. Für das
  INTERSPORT-Layout ist die Positionstabelle mit ihrer Kopfzeile das
  Pflichtmerkmal (auf einem Scan ist das Firmenlogo nicht immer als Text
  lesbar, die Tabelle aber schon), Firmenname und Rechnungsnummer erhöhen die
  Punktzahl nur. Bei Gleichstand bricht die Erkennung mit einer klaren Meldung
  ab, statt einen Lieferanten zu raten.
- **Unbekanntes Layout** meldet der Upload jetzt als solches („Dieses
  Dokumentlayout kennt das System noch nicht … bitte als Beispiel
  weitergeben", HTTP 422) statt als „Tabellenkopf fehlt auf Seite 1" — das ist
  genau der Ablauf aus Abschnitt 6, Punkt 1. Weicht dagegen eine einzelne Seite
  eines *erkannten* Layouts ab, bleibt die bisherige, genauere Meldung.
- **Dokumenttyp** (D6) kommt aus dem Dokument: `dokumente.typ` wird nicht mehr
  fest als `rechnung` geschrieben, sondern aus dem Parser-Ergebnis übernommen;
  ohne erkannten Typ wird nicht gebucht. Das INTERSPORT-Layout kommt bisher nur
  als Rechnung vor (Anker „Rechnung Nr."). Der Status
  `wareneingaenge.status` bleibt darum noch immer `eingetroffen` — der Weg
  „erwartet → eingetroffen" ist Teilaufgabe B5.
- Der **Lieferant** wird über den erkannten `parser_key` nachgeschlagen (vorher
  Konstante `INTERSPORT_PARSER_KEY` im Importer).
- `invoice_dates()` ist als `dates()` ins INTERSPORT-Modul gewandert: die
  deutschen Textanker („Rechnungsdatum"/„Belegdatum") gehören zum Layout, nicht
  zum Import.
- **Nur noch ein Lesedurchgang:** Erkennung, Positionen und Rechnungs-/
  Belegdatum arbeiten auf demselben eingelesenen Dokument. Vorher öffnete der
  Import die Datei für die Datumsfelder ein zweites Mal und schickte einen Scan
  damit zweimal durch die Texterkennung (bei einer 21-seitigen Rechnung
  spürbar).
- Die Vorschau zeigt den erkannten Lieferanten und den Dokumenttyp über der
  Positionstabelle; `/upload-preview` und `/validate-preview` liefern dafür
  `parser_key`, `supplier_name` und `document_type` (siehe
  `docs/api-referenz.md`). Neue Übersetzungs-Keys in DE/FR/EN, keine
  hartcodierten Texte (Regel 7).
- Tests: `tests/test_parser_registry.py` (Schnittstellenvertrag jedes
  registrierten Moduls, `parser_key` ↔ Lieferanten-Seed, Erkennung mit/ohne
  Firmenname, Punktegleichstand, übersetzte Meldung in DE/FR/EN, nur ein
  Lesedurchgang) und `tests/test_import_end_to_end.py` (kompletter Weg
  PDF → Erkennung → Positionen → Datenbank mit einer selbst gebauten
  Mini-Rechnung, läuft also **ohne** `INTERSPORT_TEST_PDF` — diese Lücke
  hatten die bisherigen Import-Tests, die den Parser durch eine Attrappe
  ersetzen). `tests/test_parser.py` heisst jetzt
  `tests/test_parser_intersport.py`. Gesamtsuite: 166 bestandene Tests
  (vorher 145); zusätzlich gegen echtes PostgreSQL 16 durchgespielt (Import
  mit Kategorien/Bestand, Duplikat, GEWA-Regel ohne Eingangsdatum,
  unbekanntes Layout, Löschen).

**Details zu Phase B, Teilaufgabe B2 — Belegnummer nur je Lieferant eindeutig**
(Migration `e5f6a7b8c9d0`, siehe auch `docs/datenmodell.md`, `dokumente`):
- Belegnummern sind Lieferantensache und überschneiden sich zwangslos. Vorher
  war `dokumente.dokumentnummer` **global** eindeutig — die Rechnung eines
  neuen Lieferanten wäre als Duplikat abgewiesen worden, nur weil INTERSPORT
  dieselbe Nummer schon verwendet hatte. Jetzt gilt
  `UNIQUE (lieferant_id, dokumentnummer)`.
- Zu entfernen waren **zwei** Objekte, weil Migration `c3d4e5f6a7b8` beides
  angelegt hatte: die Spalten-Eindeutigkeit (in PostgreSQL als Constraint
  `dokumente_dokumentnummer_key`) und zusätzlich einen eigenen UNIQUE-Index.
  Der Index auf der Nummer bleibt, nur nicht mehr eindeutig.
- `datei_hash` bleibt global eindeutig: dieselbe Datei ist dasselbe Dokument,
  egal von wem.
- Der Importer schlägt den Lieferanten jetzt **vor** der Duplikatsprüfung nach
  und vergleicht Datei-Hash (global) oder Belegnummer beim selben Lieferanten.
  Die verständliche Meldung kommt weiterhin aus dem Importer, der
  Datenbank-Constraint ist der Rückfall für zwei gleichzeitige Importe.
- `GET /invoice-import-status` (Stapel-Warteschlange) nimmt zusätzlich
  `parser_key`: die Belegnummer allein sagt nichts mehr, ohne Lieferant zählt
  nur der Datei-Hash. Die Warteschlange im Browser schickt den Wert mit und
  vergleicht ihn auch beim Duplikat innerhalb der eigenen Auswahl.
- Tests: zwei Lieferanten mit derselben Nummer (über ein zweites, nur im Test
  registriertes Layout), derselbe Lieferant mit derselben Nummer aus einer
  anderen Datei, der Datenbank-Constraint selbst, die Statusabfrage mit und
  ohne Lieferant sowie die Warteschlange im Node-Test. Gesamtsuite: 170
  bestandene Tests.
- Gegen echtes PostgreSQL 16 geprüft: Migration auf leerer und auf gefüllter
  Datenbank, `downgrade`/`upgrade`-Rundlauf mit Daten, Verhalten beider
  Constraints, kompletter Importweg mit zwei Lieferanten. `alembic revision
  --autogenerate` zeigt für `dokumente` keine Abweichung zwischen Modell und
  Schema mehr. Dabei aufgefallen (nicht geändert, betrifft eine andere
  Tabelle): `varianten.ean` hat aus demselben Grund ebenfalls doppelt
  hinterlegte Eindeutigkeit (Constraint `varianten_ean_key` **und**
  UNIQUE-Index `ix_varianten_ean`) — fachlich harmlos, aber unnötig.
- Der `downgrade` scheitert absichtlich, sobald zwei Lieferanten dieselbe
  Nummer verwenden: dann gibt es keine global eindeutige Nummer mehr.

**Details zu Phase B, Teilaufgabe B4 — Lagerort aus der Lieferadresse**
(D19/D20, siehe `docs/architektur.md`, Abschnitt „Lagerort aus der
Lieferadresse"):
- Bisher buchte jeder Import gegen die aktive Filiale des Kontos, obwohl auf
  dem Beleg steht, wohin die Ware ging — beim externen Händler geht die
  Rechnung nach Volketswil und die Ware nach Conthey, CMP liefert an die GEWA.
- Neues Modul `app/services/lieferadresse.py`: erkennt den Lagerort aus dem
  Dokumenttext. Reine Textlogik ohne Datenbank und ohne Layout-Wissen, damit
  sie bei jedem Lieferanten gleich funktioniert. Merkmale mit Punkten
  (PLZ 3, Ort 2, eigener Name wie „GEWA" 2, Strasse 1), Mindestpunktzahl und
  Umlaut-Toleranz („Hägendorf"/„Haegendorf").
- Zwei Durchgänge: zuerst im Umfeld eines Lieferadress-Ankers
  („Lieferadresse", „Lieferung an", „Warenempfänger", „Ship to" …), sonst im
  ganzen Text. **Bei Gleichstand gibt es keinen Vorschlag** — stehen
  Rechnungs- und Lieferadresse gleichberechtigt im Text, wäre jede Wahl
  geraten; dann bleibt es bei der aktiven Filiale.
- D19 in der Oberfläche: die Vorschau zeigt „Wareneingang buchen auf" als
  Auswahl, vorbelegt mit dem Vorschlag, daneben die Begründung („Aus der
  Lieferadresse erkannt: SF4 · Conthey") oder der Hinweis, dass nichts erkannt
  wurde. `/import-invoice` nimmt den gewählten Lagerort entgegen und prüft ihn
  serverseitig; ohne Angabe bleibt alles wie bisher.
- Buchbar sind **alle** Lagerorte (eigene Filiale zuerst). Sonst liesse sich
  eine Lieferung an eine andere Filiale oder an die GEWA gar nicht erfassen —
  D19 wäre für genau die Fälle wirkungslos, für die es gedacht ist. Wer hier
  hinkommt, darf ohnehin Dokumente hochladen (Regel 9); eine falsch gewählte
  Filiale ist über eine Umlagerung korrigierbar. **Von Fabian bestätigt**
  (21.09.2026) und als D26 festgehalten. Filialwechsel und Leseansichten
  bleiben unverändert bei den zugewiesenen Filialen.
- Tests: `tests/test_lieferadresse.py` (24 Tests: jede Seed-Adresse,
  Lieferadresse schlägt Rechnungsadresse, Gleichstand ohne Vorschlag,
  Schreibweisen, „Lieferschein" ist kein Anker) und
  `tests/test_wareneingang_lagerort.py` (7 Tests über die echte App **mit
  Anmeldung**, also inklusive Rechteweg). Gesamtsuite: 213 bestandene Tests
  (vorher 182).
- Gegen echtes PostgreSQL 16 im Browser durchgespielt: Anmeldung, Upload einer
  Rechnung mit Lieferadresse Conthey, Vorauswahl SF4 mit Begründung,
  vollständige Auswahlliste.

**Details zu Phase B, Teilaufgabe B5 — erwartet → eingetroffen** (Regel 3, D6,
D21, D22; siehe `docs/architektur.md`, Abschnitt „Erwartet → eingetroffen"):
- Der Import unterscheidet jetzt nach Dokumenttyp: **Rechnung/Lieferschein**
  begleiten die Ware und buchen sofort, **Auftragsbestätigung/Bestellung**
  erzeugen einen Wareneingang mit Status `erwartet` — ohne Lagerbewegung, ohne
  Bestand, ohne Eingangsdatum. Artikel, Varianten und Preise entstehen
  trotzdem, damit angekündigte Ware im Stamm auffindbar ist.
- Migration `f6a7b8c9d0e1`: `wareneingang_positionen.menge_eingetroffen`.
  `menge` ist die Menge laut Beleg, die neue Spalte die davon angekommene, die
  Differenz die offene Restmenge. Altdaten werden aufgefüllt (alle bisherigen
  Wareneingänge stammen aus Rechnungen).
- Teillieferung (D22): Was ankommt, wird gebucht; der Rest bleibt offen und der
  Wareneingang weiter `erwartet`. Eine Nachlieferung wird einfach nochmals
  bestätigt. Erst wenn keine Position mehr offen ist, wechselt der Status.
- Eingangsdatum: beim ersten Zugang gesetzt, rückwirkend eintragbar (D13); in
  einem Lager ohne Verkauf (GEWA) gar nicht (Regel 6).
- `varianten.first_seen`/`last_seen` („Erste/letzte Lieferung") zählen nur noch
  **angekommene** Ware — eine Ankündigung ist keine Lieferung. Das gilt auch
  beim Neuberechnen nach dem Löschen eines Dokuments.
- Import und Ankunft buchen über **dieselbe** Funktion (`buche_zugang`) und
  nehmen dieselbe Datenbank-Sperre — beide Wege tun damit garantiert dasselbe.
- Neue Seite `/wareneingaenge` („Lieferungen" in der Navigation): offene
  Lieferungen der aktiven Filiale, je Position erwartet / bereits da / offen,
  Feld für die jetzt eingetroffene Menge und ein Eingangsdatum. Bedienbar auch
  von **Mitarbeitern** (D21). Übersetzungen DE/FR/EN.
- Tests: `tests/test_wareneingang_ankunft.py` (18 Tests, u. a. kein Bestand vor
  der Ankunft, vollständige und Teillieferung, Nachlieferung schliesst,
  GEWA ohne Eingangsdatum, unplausible Mengen, fremde Position, kompletter Weg
  über die API als angemeldete Mitarbeiterin). Gesamtsuite: 232 bestandene
  Tests (vorher 213).
- Gegen echtes PostgreSQL 16 geprüft: Migration auf einer Datenbank mit
  Altdaten (`menge_eingetroffen` korrekt aufgefüllt) und der ganze Ablauf im
  Browser als Mitarbeiterin — Teillieferung, sichtbare Restmenge, Abschluss.
- **Noch nicht erreichbar im Alltag:** Eine Auftragsbestätigung kann bisher
  nicht hochgeladen werden, weil die Parser-Registry nur das
  INTERSPORT-Rechnungslayout kennt (weitere Layouts: Phase E). Der Weg
  funktioniert also erst mit den nächsten Parsern oder mit der manuellen
  Erfassung (B6) vollständig.
- **Offen geblieben:** Kommt *mehr* an als bestellt, bucht das System es
  (Bestand = was physisch da ist). Ob das so bleiben oder eine Warnung geben
  soll, ist mit Fabian zu klären.

**Details zu Phase B, Teilaufgabe B6 — manuelle Erfassung mit Scanner**
(D23, D27, Regel 3/5/6/9/10; siehe `docs/architektur.md`, Abschnitt „Ware von
Hand erfassen"):
- Zweiter Weg, auf dem Ware ins System kommt: ohne PDF, ohne Parser
  (`app/services/manuelle_erfassung.py`, Seite `/erfassen`, Navigation
  „Erfassen"). Gedacht für Ware ohne Dokument **und** für Lieferanten, deren
  Layout noch kein Parser kennt — der Weg, der B5 und die Registry im Alltag
  überhaupt erst benutzbar macht, solange nur ein Layout erkannt wird.
- Migration `a7b8c9d0e1f2`: `wareneingaenge.dokument_id` und
  `artikel.lieferant_id` dürfen leer bleiben. Ware ohne Dokument ist ein
  direkter Wareneingang **ohne Beleg** (D27), ein Artikel braucht keinen
  Lieferanten (D23). Bestehende Daten bleiben unberührt.
- Pflicht sind nur **Marke, Bezeichnung, Menge und UVP** (D23). EAN, Farbe,
  Grösse, Einheit, Lieferanten-Artikelnummer, EK und Lieferant sind
  freiwillig (Regel 5 und Regel 10).
- Gebucht wird sofort (Regel 3 — von Hand erfasst wird nur, was man in den
  Händen hält), über **dieselbe** `buche_zugang()` und dieselbe Datenbank-
  Sperre wie Import und Ankunftsbestätigung. Ein Aufruf = ein Wareneingang mit
  allen Positionen, in einer Transaktion: entweder alles oder nichts.
- Neues Modul `app/services/artikel.py`: die Artikel- und Variantenregeln
  (Regel 4/5) stehen jetzt **einmal** da und werden von Import und Erfassung
  gemeinsam benutzt — sonst wären die beiden Wege früher oder später
  auseinandergelaufen. Dasselbe gilt für das EAN-Format, das sich die Vorschau
  jetzt von dort holt.
- Eingangsdatum: heute oder rückwirkend (D13); ein Lager ohne Verkauf (GEWA)
  bekommt keines (Regel 6), das Datumsfeld verschwindet dann auch in der
  Oberfläche.
- Bedienung auf den Scanner zugeschnitten: Barcode scannen → bekannte EAN
  füllt das Formular (Marke, Bezeichnung, Farbe, Grösse, Einheit, letzter
  UVP/EK) → Menge tippen → Enter legt die Position in eine Liste → nächster
  Artikel. Ein Knopf am Ende bucht alles. Unbekannte EAN wird übernommen, ohne
  EAN geht es auch.
- **Rechte:** Erfassen dürfen auch **Mitarbeiter** (Regel 9/D21) — es entsteht
  kein Dokument, also greift das Dokumentrecht nicht. Der Ziel-Lagerort läuft
  über dieselbe serverseitige Prüfung wie der Import (D26): vorgewählt ist die
  aktive Filiale, buchbar sind alle Lagerorte. Im Browser bestätigt: die
  Mitarbeiterin sieht „Erfassen", aber weiterhin kein „Rechnung hochladen".
- Audit wie beim Import: je Position ein unveränderter Schnappschuss der
  Eingabe in `wareneingang_positionen_quelle` (mit Benutzer und Zeitpunkt), die
  Lagerbewegung trägt den Grund `manuelle-erfassung` (fester Schlüssel, kein
  UI-Text).
- Tests: `tests/test_manuelle_erfassung.py` (55 Tests: Pflichtfelder, Komma als
  Dezimaltrennzeichen, eine falsche Position bucht nichts, Varianten mit und
  ohne EAN, Bestand je Filiale, GEWA ohne Eingangsdatum, rückwirkendes und
  zukünftiges Datum, Lieferant optional, EAN-Nachschlag, kompletter Weg über
  die API als angemeldete Mitarbeiterin). Gesamtsuite: 288 bestandene Tests
  (vorher 232).
- Gegen echtes PostgreSQL 16 geprüft: Migration vor und zurück sowie im
  Offline-Modus (`--sql`), Erfassung auf SF1/SF2/GEWA inkl. Bestand,
  Lagerbewegungen, Preisverlauf und Quellen-Snapshot. Danach der ganze Ablauf
  im Browser als Mitarbeiterin, auch auf Französisch.
- Nebenbefund behoben: Die Seite `/wareneingaenge` hing ihren i18n-Listener an
  `window`, das Ereignis wird aber auf `document` ausgelöst — ein Sprachwechsel
  liess die vom Skript erzeugten Texte (Spaltenköpfe, Meldungen) stehen. Beide
  Seiten warten jetzt auf den fertigen Katalog und zeichnen bei jedem
  Sprachwechsel neu.
- **Offen geblieben:** Kategorie (B8) und interne EAN samt Etikett (B7) fehlen
  auch hier noch — ein von Hand erfasster Artikel ohne Hersteller-EAN ist an
  der Kasse noch nicht scannbar.

**Details zu Phase B, Teilaufgabe B3 — EAN wirklich optional** (Entscheid D18,
siehe `docs/architektur.md`, Abschnitt „PDF-Parsing" → „Warnung oder Hinweis?"):
- Regel 5 galt im Datenmodell und im Importer, **nicht** aber im Parser und in
  den Korrekturen: dort war die EAN Pflichtfeld. Bei 4 von 6 Beispieldokumenten
  hat kein Artikel eine EAN — der Upload wäre für diese Lieferanten von
  vorneherein blockiert gewesen.
- Jede Position hat jetzt zwei getrennte Listen: `warnings` (sperrt den Import)
  und `hints` (läuft durch). Das Ergebnis zählt beides (`rows_with_warnings`,
  `rows_with_hints`).
- Keine EAN → Hinweis. Eine EAN, die im Dokument steht, aber kein gültiges
  Format hat → weiterhin blockierende Warnung. Dasselbe in den Korrekturen: die
  EAN löschen ist erlaubt (ergibt den Hinweis), Unsinn eintragen bleibt ein
  Fehler. Farbe und Grösse waren schon vorher optional.
- Die Vorschau zeigt Hinweise gedämpft unter den Warnungen derselben Position
  und als eigene Kennzahl „Positionen mit Hinweisen" (nicht als Warnung
  eingefärbt). Neue Übersetzungs-Keys in DE/FR/EN.
- Varianten ohne EAN werden über Lieferant + Artikelnummer + Farbe + Grösse
  zusammengeführt (Regel 5) — der Importer konnte das schon, jetzt kommt auch
  etwas dort an.
- Tests: `tests/test_ean_optional.py` (12 Tests vom Parser über die
  serverseitige Neuvalidierung bis in die Datenbank: Hinweis statt Warnung,
  unleserliche EAN blockiert, EAN löschen/nachtragen, zweimal dieselbe
  Kombination = eine Variante, unterschiedliche Grösse = zwei Varianten).
  Gesamtsuite: 182 bestandene Tests (vorher 170).
- Gegen echtes PostgreSQL 16 geprüft: mehrere Varianten mit leerer EAN bestehen
  nebeneinander (NULL kollidiert nicht im Unique-Index), Bestand wird je
  Variante gebucht. Artikelliste und Excel-Export zeigen eine leere EAN als
  „—" bzw. als leere Zelle.
- Noch offen (Teilaufgabe B7): interne EAN-13 erzeugen und Etikett drucken,
  damit auch Artikel ohne Hersteller-Barcode an der Kasse scanbar werden.
  `varianten.ean_intern` ist dafür vorbereitet, wird aber noch nie gesetzt.

**Code-Review nach Phase A** (21.09.2026, Branch `feature/warenwirtschaft-v2`) — vollständige
Durchsicht des bestehenden Codes auf Fehler; behoben und jeweils gegen echtes PostgreSQL bzw.
mit neuen Tests belegt:
- **Migration `c3d4e5f6a7b8`**: Die Id-Sequenzen wurden nur nachgezogen, wenn es Altdaten zu
  migrieren gab. Auf einer frischen Datenbank scheiterte dadurch der erste Insert ohne
  explizite Id („duplicate key"). Neue Migration `d4e5f6a7b8c9` repariert bereits migrierte
  Datenbanken idempotent.
- **FEDAS-Nachtrag**: Kategorie und FEDAS-Code wurden nur nachgetragen, wenn die Variante
  *nicht* über die EAN gefunden wurde — genau die migrierten Altartikel wären damit dauerhaft
  ohne Kategorie geblieben.
- **Regel 6 (GEWA)**: Ware an ein Lager ohne Verkauf (`lagerorte.verkauf = false`) bekommt
  jetzt tatsächlich kein Eingangsdatum — weder am Wareneingang noch in
  `bestand.aeltestes_eingangsdatum`. Die Reduktionsuhr (18/36 Monate) startet damit erst bei
  Ankunft in einer Filiale.
- **`delete_invoice()`**: `first_seen`/`last_seen` wurden aus dem Eingangsdatum neu berechnet,
  der Import setzt sie aber aus dem Dokumentdatum — nach der GEWA-Änderung wären sie für
  solche Varianten beim Löschen auf NULL gefallen. Jetzt beidseitig das Dokumentdatum.
- Kleinere Korrekturen: `reused_products` zählte in derselben Rechnung neu angelegte Varianten
  mit; `fedas_code` fehlte in der Längenprüfung (wäre erst in PostgreSQL als 503 aufgeschlagen);
  zwei verbliebene hartcodierte deutsche UI-Texte (Regel 7); gespeicherte Spalteneinstellungen
  der Artikelliste zeigten nach dem Wegfall der Spalte „Art. Nr." auf die falschen Spalten;
  toter Code in `article_details.py` und `auth.py` entfernt.
- **`app/static/js/i18n.js`**: Bei unveränderter Sprache wurde der Katalog erneut geholt und ein
  zweites `sportfabrik:i18n-ready` gesendet. Weil `session.js` direkt nach dem Laden die
  Kontosprache meldet, holte jede Seite ihren Katalog doppelt und ihre Daten dreifach
  (gemessen; jetzt 1× bzw. 2×) — im Ladennetz spürbar.
- **Neue Tests**: `tests/test_lagerbewegungen.py` (10 Tests: Zugang, Bestand je Filiale,
  ältestes Eingangsdatum, GEWA-Regel, Neuberechnung beim Löschen — diese Kernlogik aus Regel 2
  hatte bis dahin keinen einzigen Test) und zwei Katalogtests in `tests/test_i18n.py`, die Keys
  und Platzhalter aller drei Sprachen vergleichen. Gesamtsuite: 145 bestandene Tests.

**Details zur Überarbeitung der Oberfläche** (siehe `docs/architektur.md`, Abschnitt
„Gestaltung: ein Token-Satz für alle Seiten"):
- `app/static/css/app.css` vollständig neu aufgebaut: nummerierte Abschnitte, alle Farben,
  Abstände, Radien, Schatten und Übergänge als Custom Properties in `:root`. Der Dunkelmodus
  definiert nur noch diese Tokens neu, kein Baustein hat eigene Dunkelmodus-Regeln.
- Ruhigere Grundfläche, klarere Schriftstufen, feine Trennlinien statt Zebrastreifen in den
  Tabellen, weiche Schatten statt farbiger Rahmen; das Orange bleibt Akzent für die
  Hauptaktion, Verweise und Warnungen. Die Marke selbst ist unverändert.
- Zweizeilige, beim Scrollen stehende Kopfzeile (Marke + Navigation, darunter die
  Sitzungsleiste); Kopf- und Fusszeile richten sich über `--content-max` an derselben Kante
  aus wie der Inhalt. Vorher lief die Navigation über die Inhaltsbreite hinaus.
- Bedienelemente vereinheitlicht: Knöpfe mit Zustandsfarben und Drück-Rückmeldung, Felder mit
  weichem Fokusring statt dickem Rahmen, `<select>` mit eigenem Pfeil, Sprachwahl als
  segmentierte Steuerung, „Werte bearbeiten" als sauberer Schalter, Zahnrad einfarbig.
- Zugänglichkeit: sichtbarer Tastaturfokus bleibt erhalten, `color-scheme` für native
  Bedienelemente, `@media (prefers-reduced-motion: reduce)` schaltet alle Übergänge ab,
  Mobilansicht ohne waagrechten Überlauf (vorher 428 px Inhalt auf 390 px Bildschirm).
- Nebenbei behoben: In der Artikelsuche liess sich die Spalte „Marke" (`data-col="1"`) nicht
  ausblenden — für sie fehlte die passende `hide-col-*`-Regel, das Häkchen blieb wirkungslos.
- Keine neuen UI-Texte (Regel 7): die Änderung ist rein gestalterisch, alle Zeichenketten
  laufen unverändert über die bestehenden Übersetzungs-Keys. Cache-Parameter der Templates
  auf `?v=premium-1` gezogen, damit Filialrechner die neue Datei laden.

**Offene Punkte aus dem Review** (bewusst nicht im Review-Commit geändert, siehe Abschnitt 9):
- ~~`dokumente.dokumentnummer` ist **global** eindeutig~~ — erledigt mit Teilaufgabe B2
  (Migration `e5f6a7b8c9d0`, siehe unten): jetzt `UNIQUE (lieferant_id, dokumentnummer)`
  inkl. Duplikatsprüfung im Importer.
- ~~Regel 5 („EAN ist optional") gilt im Datenmodell und im Importer, **nicht** aber in
  Parser/Korrekturen~~ — erledigt mit Teilaufgabe B3 (siehe unten): eine Position ohne
  EAN läuft mit Hinweis durch, eine unleserliche EAN bleibt eine Warnung.
- Filialbezug der Ansichten: Dashboard, Rechnungsliste und Artikeldetails zeigen jedem
  angemeldeten Konto die Dokumente **aller** Filialen. Ob Regel 9 („Admin/Zentrale
  filialübergreifend") auch das Lesen einschränken soll, ist eine fachliche Frage an Fabian.

*Dieses Dokument wird bei jeder Entscheidung/Phase nachgeführt. Die Master-Kopie liegt im Claude-Projekt „Sportfabrik WarenWirtschaftsSystem“.*
