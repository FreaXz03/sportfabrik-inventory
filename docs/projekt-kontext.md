# Sportfabrik Warenwirtschaft — Projektkontext, Vision & Zielbild

Stand: 2026-09-24 (Rev. 6 vom 21.09.2026: zwei externe Verarbeitungsstellen GEWA und VEBO plus externes Lager Dietikon, Eingangsdatum startet erst in einer Filiale; ergänzt um die bestätigten Antworten vom 22.–24.09.2026 in Abschnitt 10) · **Massgebliche Zielbeschreibung** des Projekts. Technischer Ist-Zustand des Codes: `README.md` und `docs/architektur.md`, `docs/datenmodell.md`.
Repo: github.com/FreaXz03/sportfabrik-inventory (Branch `main`: Phase B inkl. B8, übernommen mit PR #9, Merge-Commit `d1c6533`. Phase C und die Inbox-Anforderungen vom 23.09.2026 liegen auf `feature/warenwirtschaft-v2`, noch nicht in `main`).

---

## Ergänzung vom 23.09.2026, abends

Neue fachliche Anforderungen: [Inbox-Anforderungen vom 23.09.2026](anforderungen-inbox-2026-09-23.md). Dort stehen die aktuelle Lieferantengruppierung (111/555/333/999/444), Bedienungsanforderungen und der noch zu klärende Konflikt zwischen vollständiger Artikellöschung und dauerhafter Stammhaltung. Die neue Gruppierung präzisiert die ältere Warenquellen-Tabelle unten. Benutzerfreundlichkeit und gute Lesbarkeit für Mitarbeitende mit Brille oder wenig PC-Erfahrung sind zentrale Anforderungen. Keine dieser Ergänzungen ist durch diesen Doku-Abgleich als umgesetzt bestätigt.

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
| **SF2** | Conthey | Route Cantonale 7, 1964 Conthey | 027 322 75 83 | conthey@sportfabrik.ch |
| **SF3** | Regensdorf | Althardstrasse 10, 8105 Regensdorf | 044 840 05 90 | regensdorf@sportfabrik.ch |
| **SF4** | Hägendorf | Industriestrasse West 40/42, 4614 Hägendorf | 062 216 53 88 | haegendorf@sportfabrik.ch |
| **GEWA** | Externe Verarbeitung *(kein Verkauf)* | GEWA-John Leuenberger, Grubenstrasse 22, 3322 Urtenen-Schönbühl | – | – |
| **VEBO** | Externe Verarbeitung *(kein Verkauf)* | *Adresse noch nachzutragen* | – | – |
| **DIETIKON** | Externes Lager *(kein Verkauf)* | *Adresse noch nachzutragen*, Dietikon | – | – |

**GEWA** und **VEBO** = zwei externe **Verarbeitungsstellen**, in denen Ware ausgepackt und aufbereitet wird; danach geht sie in eine Filiale. Fachlich gleichwertig — was für die eine gilt, gilt auch für die andere.

**Dietikon** = externes **Lager** ohne Verarbeitung; Ware wird dort nur zwischengelagert.

→ Im System sind alle drei eigene **Lagerorte ohne Verkauf** (`verkauf = false`). Weitergabe an eine Filiale = **Umlagerung** (gehört damit schon ins MVP). Das System unterscheidet Verarbeitungsstelle und Lager bewusst **nicht** technisch — für alle Regeln zählt allein, dass dort nicht verkauft wird.

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
| D9 | **Belegdaten bleiben lokal** | Rechnungen, Lieferscheine und Auftragsbestätigungen werden **lokal auf dem eigenen Server** von eigenen Parsern gelesen — keine Weitergabe an Drittanbieter, keine KI-Extraktion. Ausserhalb der Belegverarbeitung ist KI erlaubt, auch extern (präzisiert 22.09.2026; vorher galt „keine KI, keine externen Dienste" für alles). Für den **Parserbau** darf Fabian einzelne Belege bewusst zeigen (22.09.2026); im fertigen System liest sie weiterhin nur der eigene Parser, später auch ohne Internet |
| D10 | EAN | EAN muss **nachträglich erfassbar** sein. Wird nie eine nachgetragen, **generiert das System eine interne EAN** (inkl. Etikett) |
| D11 | Externe Standorte | Zwei Verarbeitungsstellen (GEWA, VEBO) und ein externes Lager (Dietikon) → je ein eigener Lagerort ohne Verkauf, Ware wird von dort an Filialen umgelagert |
| D12 | Chris Sports | „Preis“ auf deren Dokumenten = **UVP** (Rabatt 70 % → EK = 30 % des UVP) |
| D13 | Eingangsdatum bei externer Ware | Ware, die an GEWA, VEBO oder das Lager Dietikon geht, bekommt **noch kein Eingangsdatum**. Das Datum wird gesetzt/nachgetragen, **sobald die Ware in einer Filiale (SF1–SF4) angekommen ist** — erst ab dann zählt die Lagerdauer |
| D14 | Etikettendrucker | **Sato CL4NX Plus** (Industrie-Etikettendrucker), alle PCs im WLAN können darauf drucken. Etikettengrösse noch offen (siehe Abschnitt 10) |
| D15 | Scanner | Heute nur an den 2 Kassen-PCs. Für Wareneingang/EAN-Nachtrag werden **Funk-Scanner** angeschafft |
| D16 | Kategorien | Velo und Food haben **keine** Unterkategorien; „Hartware“ bestätigt |
| D17 | Umlagerung Filiale → Filiale | Ware **behält ihr ursprüngliches Eingangsdatum** (wird durch Umbuchen nicht „verjüngt“). Nur der Weg von einem externen Standort (GEWA/VEBO/Dietikon) in eine Filiale setzt das Datum erstmals (D13) |
| D18 | Position ohne EAN beim Upload *(21.09.2026)* | **Mit Hinweis durchlassen** — der Import wird davon nicht gesperrt (Regel 5). Eine EAN, die im Dokument steht, aber unleserlich ist, bleibt dagegen eine blockierende Warnung: das ist ein Lesefehler-Verdacht und keine bewusst fehlende Nummer |
| D19 | Lagerort aus der Lieferadresse *(21.09.2026)* | Der erkannte Lagerort ist **nur ein Vorschlag** und bleibt beim Import änderbar |
| D20 | Ein Beleg, eine Lieferadresse *(21.09.2026)* | Ein Dokument hat **eine** Lieferadresse, also einen Wareneingang auf einen Lagerort. Wird die Ware danach auf Filialen verteilt, läuft das ganz normal über eine **Warenverschiebung (Umlagerung)** — nicht über mehrere Lagerorte am selben Dokument |
| D21 | „Ware eingetroffen" bestätigen *(21.09.2026)* | Dürfen **auch Mitarbeiter** — das ist Lagerarbeit, kein Dokument-Recht (Regel 9) |
| D22 | Teillieferung *(21.09.2026)* | Kommt weniger an als erwartet, bleibt die **Restmenge offen** („erwartet"), damit fehlende Ware sichtbar bleibt |
| D23 | Manuelle Erfassung, Pflichtfelder *(21.09.2026)* | **Marke + Bezeichnung + Menge + UVP** genügen. Alles andere (Lieferant, Kategorie, Farbe, Grösse, EAN) ist optional |
| D24 | Interne EAN *(21.09.2026)* | Wird **auf Knopfdruck** erzeugt (wenn ein Etikett gebraucht wird), nicht automatisch beim Import |
| D25 | Inhalt des Etiketts *(21.09.2026)* | **Jahrgang** (Jahr des Wareneingangs), **Lieferant**, **UVP** und die **Reduktionsstufe** (30 / 50 / 70 %). Ob zusätzlich der Barcode aufs Etikett soll, ist noch offen (siehe Abschnitt 10) |
| D26 | Wer auf welchen Lagerort bucht *(21.09.2026, bestätigt)* | **Wer Dokumente hochladen darf, darf auf jeden Lagerort buchen** (eigene Filiale zuoberst). Das Ziel bestimmt der Beleg über seine Lieferadresse, nicht die gerade aktive Filiale — sonst liesse sich eine Lieferung an eine andere Filiale oder an einen externen Standort gar nicht erfassen. Filialwechsel bleibt bei den zugewiesenen Filialen; Lesen ist gemäss Bestätigung vom 22.09.2026 für alle Filialen erlaubt |
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
| Z7 | **Filialen & Lagerorte** | SF1–SF4 plus GEWA, VEBO und Lager Dietikon; getrennte Bestände/Wareneingänge, gemeinsamer Artikelstamm, Filialwechsel, Umlagerung externer Standort → Filiale |
| Z8 | **Mehrsprachig** | DE / EN / FR |
| Z9 | **Kassenkategorien** | Jeder Artikel hat Hauptgruppe + Sportbereich wie in der Kasse; Vorschlag via FEDAS |
| Z10 | **Runterschreib-Hinweise** | Übersicht/Benachrichtigung je Filiale gemäss Regeln in 8.3 (18 / 36 Monate) |
| Z11 | **EAN nachtragen / generieren** | EAN jederzeit per Scan nachtragen; sonst interne EAN generieren und Etikett drucken |

### Bereits vorhanden und weiterhin gewünscht
Zweistufiger Import mit Vorschau & Korrektur, Stapel-Import, OCR für Papier-Scans, Artikelnotizen, Excel-Export, Kassennummer-Login, Hell-/Dunkelmodus, Barrierefreiheit (grosse Schrift/Spaltenwahl), Backups, Docker-Deployment.

### Später (Backlog, wird laufend ergänzt)
- [ ] **Kassenanbindung**: Scan an der Kasse liefert Kategorie, UVP, Reduktion; Verkauf bucht automatisch aus
- [ ] Preisschilddruck mit reduziertem Preis
- [ ] Umlagerungen zwischen Filialen (externer Standort → Filiale ist bereits MVP)
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
| **CMP 2** (AB 2026A-F30-246) | Auftragsbestätigung | Text | ❌ | ✅ (VK) | ✅ (EK) | ✅ **Grössen-Matrix** (92–176) | Lieferung an **GEWA** (externe Verarbeitung) |
| **CMP 1** (Bestellung 22065) | Bestellung | **Scan (Bild)** | ❌ | ✅ (VK) | ✅ (Preise) | ✅ Grössen-Matrix | Farbige Tabelle, OCR-Text unbrauchbar |

### Erkenntnisse & Konsequenzen

1. **Jedes Lieferanten-Layout ist anders** — 6 Beispiele, 6 Layouts, weitere folgen. Wegen D9 (Belegdaten bleiben lokal) → **regelbasierte Erkennung, komplett lokal** (siehe 8.4):
   - **Lieferanten-Erkennung** automatisch über Merkmale im Dokument (MwSt.-Nr., Firmenname, GLN, Tabellenkopf).
   - **Ein Parser pro Layout** als Plug-in; wiederkehrende Muster (Tabelle mit Kopfzeile, Farbe/Grösse in Folgezeile, Grössen-Matrix) als gemeinsame Bausteine, damit ein neues Layout meist nur eine kleine Konfiguration braucht.
   - **Ehrliche Einschränkung:** Ein Layout, das das System noch nie gesehen hat, kann ohne KI nicht automatisch gelesen werden. Ablauf dann: Dokument wird als „unbekanntes Layout“ markiert → Positionen manuell erfassen (Kopfdaten vorausgefüllt) → Beispiel an Fabian/Entwicklung → Parser ergänzen. Je mehr Beispiele, desto seltener passiert das.
2. **Viele Dokumente haben keine EAN** (4 von 6), und auch physisch hat nicht jeder Artikel einen Barcode. → Varianten müssen **ohne EAN** existieren können (Schlüssel: Lieferant + Artikelnummer + Farbe + Grösse). EAN jederzeit **per Scan nachtragen**; hat ein Artikel nie eine, **generiert das System eine interne EAN-13** (GS1-Bereich 20–29 für interne Nummern, mit Prüfziffer — kollidiert nie mit echten Hersteller-EANs) und druckt ein Etikett. So ist später **jeder** Artikel an der Kasse scanbar.
3. **UVP fehlt teilweise** (externer Händler) → in der Vorschau als Pflichtfeld nachfragen, sonst kein Verkaufspreis berechenbar. Bereits bekannter UVP derselben Artikelnummer wird vorgeschlagen.
4. **Auftragsbestätigung ≠ Wareneingang.** → Dokument erzeugt einen **erwarteten Wareneingang**; erst „Ware eingetroffen“ (mit Mengenkontrolle) bucht den **Lagerzugang** (D6).
5. **Lagerort aus Lieferadresse** erkennbar (SF1–SF4 oder einer der externen Standorte GEWA/VEBO/Dietikon, Adressen siehe oben) → automatische Vorauswahl beim Upload, manuell änderbar. Ware an einen externen Standort wird später an eine Filiale umgelagert.
6. **Grössen-Matrix** (CMP): eine Zeile = mehrere Grössen mit je eigener Menge → Parser muss in Einzelvarianten auflösen.
7. **ECOM** braucht keinen eigenen Parser: Intersport-Layout, Quelle über Referenzfeld erkennen.

## 7. Abgleich Zielbild ↔ aktuelles Repo

Momentaufnahme vom 24.09.2026: **Phase B abgeschlossen**, **Phase C
abgeschlossen** (C1–C5, 23.09.2026), dazu die Inbox-Anforderungen vom
23.09.2026 (umgesetzt am 24.09.2026). Massgeblich für den Stand der
Umsetzung ist Abschnitt 11; diese Tabelle fasst ihn nur gegenüber dem Zielbild
zusammen.

| Bereich | Heute im Repo | Lücke zum Ziel |
|---|---|---|
| Upload & Parsing | ✅ Intersport-PDF, OCR (Tesseract, lokal), Vorschau, Korrektur, Stapel, **Parser-Registry mit Lieferanten-/Dokumenttyp-Erkennung** (B1), **Lagerort aus der Lieferadresse** (B4), **erwartet→eingetroffen** (B5) | Bisher nur 1 Layout registriert (weitere in Phase E); keine Grössen-Matrix; OCR für farbige Tabellen-Scans zu schwach |
| Manuelle Erfassung | ✅ Seite `/erfassen` mit Scanner, ohne Beleg (B6) — inkl. Kategorie (B8) und Etikettendruck (B7) | — |
| Artikelstamm | ✅ `artikel` ↔ `varianten` als echte Beziehung, EAN optional (B3), interne EAN auf Knopfdruck (B7), Kassenkategorien mit FEDAS-Vorschlag und Wahl von Hand (B8), Lieferantengruppen mit Etikett-Code, von Hand erfasste Artikel löschbar (24.09.2026) | FEDAS-Tabelle erst teilweise bestätigt (6 von 11 Sportbereichen offen) — bis dahin wird von Hand gewählt |
| Preise | ✅ UVP und EK je Wareneingangsposition (EK optional, Regel 10), Preisverlauf je Variante, Reduktionsstufe als Baustein (`app/services/reduktion.py`, genutzt auf dem Etikett) | Reduktions-Hinweise als eigene Ansicht und die zentrale Empfehlung fehlen → Phase D |
| Lagerbestand | ✅ `lagerbewegungen` (append-only) + `bestand` je Lagerort; Zugang aus Import, bestätigter Ankunft und Erfassung; **Bestandsansicht** `/bestand` je Lagerort, alle Filialen lesbar (C2); **Ausbuchen per Scan** `/ausbuchen` (C3); **Umlagerung** `/umlagern` (C4); **Korrekturen** über „Zählen" in `/bestand` (C5) | Phase C fertig. Der migrierte Bestand bleibt kumulierter Wareneingang, bis er gezählt und korrigiert ist |
| Filialen | ✅ `lagerorte` (SF1–SF4 + GEWA, VEBO, Dietikon) + `benutzer_lagerorte` (m:n), Filialwechsel in der Oberfläche; Wareneingänge, Bestand und Reduktionsrechnung sind filialbezogen | Leserechte am 22.09.2026 geklärt (Abschnitt 10): Mitarbeiter und Filialleiter sehen Dokumente und Bestände **aller** Filialen. Alle Ansichten (Übersicht, Belege, Artikeldetails, Bestand, Ausbuchungen) tun das; der Filialwechsel bleibt bei den zugewiesenen Filialen (D26) |
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
| `lagerorte` | SF1–SF4 (Verkauf) + GEWA, VEBO, Dietikon (kein Verkauf), inkl. Adresse (für Auto-Erkennung) — **umgesetzt** | – |
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
- Ware ohne Eingangsdatum (z. B. noch bei GEWA/VEBO oder im Lager Dietikon) erzeugt **keine** Hinweise.
- Eine **Umlagerung Filiale → Filiale** ist kein Wareneingang und startet die Uhr der Zielfiliale **nicht** neu (bestätigt 22.09.2026, siehe Abschnitt 10). Nur der Weg von einem externen Standort in eine Filiale setzt das Datum erstmals (D13).
- Zentrale (Admin) sieht die Empfehlungen aller Filialen und kann eine **einheitliche Empfehlung** setzen; jede Filiale übernimmt oder weicht bewusst ab (Abweichungen sichtbar).
- Hinweise als Liste „Zum Runterschreiben fällig“ + Zähler im Dashboard; Schwellen (18/36 Monate) konfigurierbar.

### 8.4 Dokumenterkennung ohne KI (D9)
- **Text-PDFs** (5 von 6 Beispielen): Wortkoordinaten auslesen (PyMuPDF, wie heute) → Layout-Parser.
- **Scans** (z. B. CMP-Bestellung): lokale OCR mit **Tesseract** (bereits im Projekt) + Bildvorverarbeitung (Graustufen, Kontrast, Farbhintergründe entfernen) + Tabellen-/Linienerkennung (OpenCV). Qualität bei farbigen Tabellen begrenzt → Vorschau zeigt unsichere Felder markiert zur Korrektur.
- **Lieferanten-Erkennung** über Merkmale → passender Parser; nichts erkannt → „unbekanntes Layout“ → manuelle Erfassung.
- Alles läuft auf dem Server in Volketswil; keine Daten verlassen das Firmennetz.

### 8.5 Ablauf externer Standort → Filiale (D13)
Gilt gleichermassen für die Verarbeitungsstellen GEWA und VEBO und für das Lager Dietikon. Umbuchungen passieren spontan — deshalb bewusst einfach:

| Schritt | Im System | Eingangsdatum (Lagerdauer) |
|---|---|---|
| 1. Lieferung an den externen Standort | Wareneingang auf Lagerort **GEWA**, **VEBO** oder **DIETIKON** (Lieferadresse wird erkannt) | **leer** |
| 2. Aufbereitung bzw. Lagerung | Ware ist sichtbar unter „Extern“ (je Standort), kann aber nicht verkauft/ausgebucht werden | leer |
| 3. Ware geht in Filiale X | **Umlagerung → SFx**: Artikel/Positionen oder ganze Lieferung auswählen | – |
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
| **C — Lagerbestand** | Lagerbewegungen, Bestand je Lagerort, Umlagerung externer Standort → Filiale, Ausbuchen per Scan, Korrekturen | aktueller Bestand |
| **D — Preise & Reduktion** | UVP/EK-Verlauf, Reduktionsstufen, zentrale Empfehlung, 18-/36-Monats-Hinweise | Runterschreiben unterstützt |
| **E — Weitere Lieferanten** | Parser für Alpina, Chris Sports, CMP (Text + Scan), externer Händler; weitere laufend nach Beispielen | Upload für alle bekannten Lieferanten |
| **F — Betrieb** | Server Volketswil, VPN, externe Backups, Datenumzug | alle 4 Filialen produktiv |
| **G — Kasse** | Anbindung Intersport-Kasse (abhängig von Abklärung mit Intersport) | kein manuelles Eintippen mehr |

## 10. Offene Fragen

Alle Fragen aus Rev. 2 und Rev. 3 sind beantwortet (D1–D27). Noch offen:

1. ~~**Etikettengrösse** des Sato CL4NX Plus~~ — beantwortet am 23.09.2026: **84 × 47 mm**, jetzt Voreinstellung (siehe unten). Offen ist nur noch die Gestaltung: Fabian kann eine Vorlage des heutigen Etiketts nachreichen.
2. ~~**Barcode aufs Etikett?**~~ Vorläufig entschieden und so gebaut (B7): **ja** — ohne Strichcode bliebe genau der Artikel unscannbar, für den die interne EAN gedacht ist (D10). Falls das Etikett ihn doch nicht tragen soll, bitte melden.
3. **Kasse:** Ergebnis der Abklärung mit Intersport (Zugriff/Schnittstelle).
4. ~~**Manuelle Ausbuchung ausserhalb der Kasse:** Die Regel für negativen Bestand ist hierfür noch zu klären.~~ — beantwortet am 22.09.2026 (siehe unten): warnen, Buchung trotzdem zulassen, wie an der Kasse.

### Bestätigte Antworten vom 22.09.2026

Quelle: Fabians direkte Antworten, zusätzlich im Main-Vault unter „Sportfabrik Inventory Decisions“ festgehalten.

- **Leserechte:** Mitarbeiter und Filialleiter dürfen Dokumente und Bestände aller Filialen sehen. Schreibrechte bleiben unverändert.
- **Negativer Bestand:** Im Kassensystem mit Warnung erlauben; in einem späteren Onlineshop blockieren. Keine allgemeine Freigabe für andere Ausbuchungsarten.
- **Umlagerung:** Die empfangende Filiale bucht die Ware.
- **Mehrlieferung:** Warnung anzeigen, Buchung weiterhin zulassen. Umgesetzt als Phase C, Teilaufgabe C1.
- **Standorte:** GEWA und VEBO verarbeiten/entpacken Ware; Dietikon ist ein reines externes Lager ohne Verarbeitung.
- **Etikettenformat:** Fabian reicht die Informationen am 23.09.2026 nach.
- **Kassenschnittstelle:** Noch keine Rückmeldung von Intersport; Fabian ergänzt Neuigkeiten, sobald vorhanden.

Diese Antworten sind fachliche Entscheidungen, keine Bestätigung neu implementierter Funktionen.

### Bestätigte Antworten vom 22.09.2026 (zweite Runde, für Phase C)

- **Negativer Bestand beim Ausbuchen von Hand:** wie an der Kasse — das System **warnt**, bucht aber trotzdem. Der Bestand darf also ins Minus laufen; blockieren wird nur der spätere Onlineshop (F4). Hintergrund: der migrierte Bestand ist kumulierter Wareneingang ohne Verkäufe, Differenzen sind am Anfang der Normalfall.
- **Umlagerung Filiale → Filiale und die Reduktionsuhr:** Eine Umlagerung ist in der Zielfiliale **kein** Wareneingang. Die Uhr läuft dort unverändert weiter, die zugeschickte Ware wird auf dem Stand der Zielfiliale mitreduziert (D17: durch Umbuchen wird nichts verjüngt). Unverändert bleibt D13: nur der Weg von einem externen Standort (GEWA/VEBO/Dietikon) in eine Filiale setzt das Eingangsdatum erstmals und startet die Uhr.
- **Dazu noch offen:** Was gilt, wenn die Zielfiliale diese Lieferanten-Artikelnummer noch **nie** hatte? Dann gibt es dort kein Datum, an das sich die Uhr hängen könnte.

- **Belege für den Parserbau zeigen:** erlaubt. Ziel bleibt ein Parser, der die Dateien später **ohne Internet** liest; die Belege werden nirgends veröffentlicht und im Betrieb nicht über KI ausgelesen. Das ist die Ausnahme für die Entwicklung und kein automatischer Weg — Graphify läuft weiterhin nur mit `--code-only`.
- **Filialcodes korrigiert:** SF1 Volketswil, **SF2 Conthey**, **SF3 Regensdorf**, **SF4 Hägendorf**. Die bisherige Zuordnung in Doku, Seed-Daten und Tests war falsch (SF2 Regensdorf, SF3 Hägendorf, SF4 Conthey).

Auch diese Antworten sind fachliche Entscheidungen; gebaut ist davon noch nichts (Phase C).

### Bestätigte Antworten vom 23.09.2026 (dritte Runde)

- **Gründe beim Ausbuchen (F14):** wie vorgeschlagen — Verkauf, Bruch/Defekt, Diebstahl/Schwund, Eigenbedarf, Retoure an den Lieferanten, Sonstiges mit freiem Text.
- **Scan beim Ausbuchen (F15):** Ein Scan bucht **sofort ein Stück** aus. Mehrere Stück = mehrmals scannen; es gibt keine Mengenabfrage.
- **Umlagerung in eine Filiale ohne bisherigen Wareneingang (F11):** Die Uhr startet dort **ab Eintreffen der Ware** — das Eingangsdatum ist dann der Tag, an dem die Zielfiliale den Empfang bucht.
- **Etikettengrösse (F1):** 84 × 47 mm auf dem Sato CL4NX Plus (am Morgen zuerst 84 × 38 mm gemeldet, am selben Tag korrigiert). Eine Vorlage des heutigen Etiketts kann Fabian nachreichen.
- **Kassenschnittstelle (F2):** weiterhin keine Rückmeldung von Intersport.
- **FEDAS aus der Praxis lernen (F8):** ja. Es gibt keine FEDAS-Liste, und niemand weiss, ob die Sportfabrik eine hat. Kategorien, die von Hand gewählt werden, sollen deshalb als Vorschlag für die Zuordnungstabelle gesammelt werden — übernommen wird ein Code erst nach Prüfung, nicht automatisch.
- **Korrekturen (C5), Eingabe:** gezählt wird die **Menge im Regal**; das System rechnet die Differenz zum Bestand selbst aus und bucht sie (eine Mini-Inventur je Zeile).
- **Korrekturen, Gründe:** Inventur/Zählung, Falsch gebucht, Ware gefunden, Sonstiges mit freiem Text.
- **Korrekturen, Rechte:** alle Rollen (Regel 9 — nur Dokumente sind Filialleitern vorbehalten).
- **Begriff „Beleg" statt „Rechnung" in der Oberfläche:** hochgeladen werden nicht nur Rechnungen, sondern auch Lieferscheine und Auftragsbestätigungen. Oberbegriff überall „Beleg" (FR „justificatif", EN „document"); „Rechnung" bleibt nur, wo wirklich der Dokumenttyp gemeint ist.
- **Etikettengrösse korrigiert:** 84 × 47 mm (nicht 84 × 38 mm).
- **Kopfbereich:** aufräumen, hochwertiger und benutzerfreundlicher machen. Umgesetzt am 23.09.2026: eine Kopfzeile statt zwei, Navigation in Gruppen (Ware, Belege) mit Erklärung je Eintrag, Filial-Pille und Konto-Menü rechts, Menü-Knopf auf schmalen Bildschirmen.
- **Vorübergehender Test-Knopf im Bestand:** je Bestandszeile ein Knopf, der **ein Stück** abbucht (2 Shirts → 1 Shirt). Der Artikel bleibt im Stamm, die Buchung ist eine normale Zeile in `lagerbewegungen` (Regel 2). Sichtbar für alle Rollen. Wird wieder entfernt, sobald das Ausbuchen im Laden erprobt ist.

### Bestätigte Antworten vom 24.09.2026

- **Artikel löschen:** gebraucht vor allem für falsch **von Hand erfasste** Artikel. Löschen dürfen nur Filialleiter und Zentrale, und nur Artikel **ohne Beleg**; dann verschwinden Artikel, Bestand und Buchungen ganz (bewusste Ausnahme von Regel 2 und 4, protokolliert). Artikel aus Belegen bleiben im Stamm. Umgesetzt, siehe Abschnitt 11.
- Die übrigen Inbox-Anforderungen vom 23.09.2026 (Lieferantengruppen 111/555/333/999/444, Bedienung, Übersicht) stehen in [`anforderungen-inbox-2026-09-23.md`](anforderungen-inbox-2026-09-23.md).

### Weitere offene Produktfrage

8. ~~**FEDAS-Codes aus der Praxis lernen?**~~ — beantwortet am 23.09.2026: ja, als geprüfter Vorschlag (siehe oben). Umsetzung noch offen.

### Laufend
- Weitere Beispieldokumente sammeln (insb. Lieferscheine, Nike/adidas/Puma, ECOM) → Parser-Liste in Abschnitt 6 ergänzen.
- **FEDAS-Codes bestätigen**: 6 der 11 Sportbereiche und die Produktart-Ziffern für Velo/Food fehlen noch in `app/core/fedas.py` (siehe Abschnitt 11). Bis dahin wird in diesen Fällen von Hand gewählt.
- Funk-Scanner: 1 Testgerät beschaffen.

## 11. Stand der Umsetzung

| Phase | Status |
|---|---|
| Konzept (D1–D27) | ✅ abgeschlossen (D1–D17 am 20.09.2026, D18–D27 am 21.09.2026) |
| A — Fundament, Punkt 1 (Lagerorte, Rollen, Benutzer↔Lagerort, Filialwechsel) | ✅ abgeschlossen, Branch `feature/warenwirtschaft-v2` |
| A — Fundament, Punkt 2 (i18n DE/FR/EN, Sprachwahl pro Benutzer) | ✅ abgeschlossen, Branch `feature/warenwirtschaft-v2` |
| A — Fundament, Punkte 3–4 (neues Datenmodell, Migration Altdaten, Live-Import, Tests/Doku) | ✅ abgeschlossen, Branch `feature/warenwirtschaft-v2` |
| B — Wareneingang v2: FEDAS-Kategorievorschlag | ✅ Vorschlag und Auswahl von Hand fertig (B8); offen bleiben nur die noch nicht bestätigten FEDAS-Codes (siehe unten) |
| B — Wareneingang v2, Teilaufgabe 1 (Parser-Registry, Lieferanten- und Dokumenttyp-Erkennung) | ✅ abgeschlossen, Branch `claude/next-step-l8tzqq` |
| B — Wareneingang v2, Teilaufgabe 2 (Belegnummer je Lieferant eindeutig) | ✅ abgeschlossen, Branch `claude/next-step-l8tzqq` |
| B — Wareneingang v2, Teilaufgabe 3 (EAN wirklich optional) | ✅ abgeschlossen, Branch `claude/next-step-l8tzqq` |
| B — Wareneingang v2, Teilaufgabe 4 (Lagerort aus der Lieferadresse) | ✅ abgeschlossen, Branch `claude/next-step-l8tzqq` |
| B — Wareneingang v2, Teilaufgabe 5 (erwartet → eingetroffen) | ✅ abgeschlossen, Branch `claude/next-step-l8tzqq` |
| B — Wareneingang v2, Teilaufgabe 6 (manuelle Erfassung mit Scanner) | ✅ abgeschlossen, Branch `claude/next-step-l8tzqq` |
| B — Wareneingang v2, Teilaufgabe 7 (interne EAN + Etikett) | ✅ abgeschlossen, Branch `claude/next-step-l8tzqq` |
| B — Wareneingang v2, Teilaufgabe 8 (Kategorie von Hand wählen) | ✅ abgeschlossen, Branch `claude/awesome-lamport-tivaj9` |
| C — Lagerbestand | ✅ abgeschlossen: C1 (Warnung bei Mehrlieferung), C2 (Bestandsansicht), C3 (Ausbuchen per Scan), C4 (Umlagerung) und C5 (Korrekturen), Branch `feature/warenwirtschaft-v2` |
| Inbox-Anforderungen vom 23.09.2026 | ✅ abgeschlossen am 24.09.2026 (Lieferantengruppen-Codes, Bestandsspalten, Ausbuchungsliste, Artikelsuche, Übersicht, Artikel löschen), Branch `feature/warenwirtschaft-v2`; offen: Parser für die Beispielbelege, ECOM-Erkennung, Tests aufräumen |
| D–G | offen |
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
| B7 | **EAN nachtragen/generieren**: interne EAN-13 im GS1-Bereich 20–29 mit Prüfziffer (Regel 5/D10), **auf Knopfdruck** (D24) + Etikett als PDF für den Sato CL4NX Plus (D14/D25) | ✅ abgeschlossen |
| B8 | **Kategorie von Hand wählen**, wenn der FEDAS-Code fehlt oder unbekannt ist (danach dauerhaft gemerkt) — Rest des ersten Teilschritts | ✅ abgeschlossen |

Damit sind alle acht Teilaufgaben von Phase B abgeschlossen. Nächste Phase
gemäss Roadmap (Abschnitt 9): **C — Lagerbestand**. Innerhalb von Phase B
bleibt ein Punkt laufend offen: die FEDAS-Codes, die noch nicht aus echten
Rechnungen bestätigt sind (`app/core/fedas.py`) — bis dahin wird in diesen
Fällen von Hand gewählt, was seit B8 möglich ist.

**Phase C — Lagerbestand, Aufteilung in Teilaufgaben** (Roadmap Abschnitt 9;
die fachlichen Antworten dazu stehen in Abschnitt 10, Reihenfolge nach
Abhängigkeit und Risiko — eine Teilaufgabe = ein Commit):

| # | Teilaufgabe | Status |
|---|---|---|
| C1 | **Warnung bei Mehrlieferung**: kommt mehr an als erwartet, warnt das System und bucht trotzdem (bestätigt 22.09.2026). Rest aus B5, klein und fachlich entschieden — deshalb zuerst | ✅ abgeschlossen |
| C2 | **Bestandsansicht je Lagerort**: aktueller Bestand pro Variante × Lagerort, lesbar für **alle** Filialen (Leserechte 22.09.2026), mit eigener Sicht auf Ware an einem externen Standort (ohne Eingangsdatum). Bisher zeigt keine Seite den Bestand — ohne sie lässt sich alles Folgende nicht kontrollieren | ✅ abgeschlossen |
| C3 | **Ausbuchen per Scan** (Z6): Verkauf oder Abgang von Hand ausbuchen, `lagerbewegungen.typ = verkauf`/`ausbuchung` mit Grund und Benutzer. Reicht der Bestand nicht, **warnt** das System und bucht trotzdem (22.09.2026). Ein Scan = ein Stück (F15), Gründe gemäss F14 (23.09.2026) | ✅ abgeschlossen |
| C4 | **Umlagerung**: externer Standort → Filiale setzt das Eingangsdatum erstmals (D13), Filiale → Filiale behält es und startet die Uhr der Zielfiliale nicht neu (D17, 22.09.2026). Gebucht wird beim Empfang durch die **empfangende** Filiale (F5). Hatte die Zielfiliale die Artikelnummer noch nie, startet die Uhr ab Eintreffen (F11, 23.09.2026) | ✅ abgeschlossen |
| C5 | **Korrekturen**: Differenz von Hand buchen (`typ = korrektur`) — nur mit Grund, damit das Journal nachvollziehbar bleibt (Regel 2). Braucht es besonders am Anfang, weil der migrierte Bestand kumulierter Wareneingang ohne Verkäufe ist. Eingegeben wird die gezählte Menge, Gründe und Rechte gemäss 23.09.2026 | ✅ abgeschlossen |

Alle fünf buchen über dieselbe Stelle wie der Zugang (`buche_zugang()` bzw.
sein Gegenstück) und dieselbe Datenbank-Sperre, damit die Wege nicht
auseinanderlaufen — so wie Import, Ankunft und Erfassung in Phase B.

**Details zu Phase C, Teilaufgabe C1 — Warnung bei Mehrlieferung** (siehe
`docs/architektur.md`, Abschnitt „Erwartet → eingetroffen"):
- `bestaetige_ankunft()` bucht weiterhin die tatsächliche Menge und gibt neu
  `mehrlieferungen` zurück: je betroffene Position die Positions-Id, die
  erwartete und die eingetroffene Menge sowie die Differenz. Mengen als Text
  wie überall (kein `float`).
- Verglichen wird der **Gesamtstand** der Position (`menge_eingetroffen`) mit
  der erwarteten Menge, nicht die einzelne Buchung — sonst bliebe die
  Mehrlieferung unbemerkt, wenn sie erst mit einer Nachlieferung entsteht.
- Die Seite `/wareneingaenge` hängt einen Warnsatz an die Erfolgsmeldung
  („bei {anzahl} Position(en) ist mehr eingetroffen als erwartet"), neuer
  Übersetzungs-Key in DE/FR/EN (Regel 7). Blockiert wird nichts.
- Tests: drei neue Fälle in `tests/test_wareneingang_ankunft.py` (Mehrmenge
  gebucht und gemeldet, genaue Lieferung meldet nichts, Mehrlieferung entsteht
  erst durch die Nachlieferung). Gesamtsuite: 421 bestandene Tests
  (vorher 418).

**Details zu Phase C, Teilaufgabe C2 — Bestandsansicht** (siehe
`docs/architektur.md`, Abschnitt „Bestand ansehen"):
- Neu `app/services/bestand.py` (nur lesen, Regel 2), `app/routers/bestand.py`
  (`/bestand`, `/api/bestand`), Seite `app/templates/bestand.html` mit
  `app/static/js/bestand.js`, Navigationseintrag „Bestand" auf allen Seiten.
  Bis jetzt zeigte **keine** Seite den Bestand — die Artikelliste weist sogar
  ausdrücklich darauf hin, dass ihre Mengen gelieferte und nicht vorhandene
  Ware sind.
- Eine Zeile ist eine **Variante × Lagerort** mit Menge und ältestem
  Eingangsdatum; dieselbe Abfrage liefert Anzahl und Gesamtmenge der ganzen
  Auswahl. Mengen als Text, nie als `float`.
- Vorausgewählt ist die aktive Filiale; wählbar sind **alle** Standorte
  (Leserechte vom 22.09.2026), dazu „Alle Filialen und Standorte". Der
  Filialwechsel in der Sitzungsleiste bleibt unverändert bei den zugewiesenen
  Filialen — er entscheidet weiterhin, wohin gebucht wird.
- Zeilen mit Menge 0 sind ausgeblendet (umschaltbar), ein **negativer**
  Bestand wird immer gezeigt: er ist seit dem 22.09.2026 möglich und dann
  gerade das, was jemand sehen muss.
- Ware an einem Standort ohne Verkauf hat kein Eingangsdatum (Regel 6/D13);
  die Seite schreibt dort den Grund hin statt eines leeren Strichs.
- Suche über Marke, Bezeichnung, Lieferanten-Artikelnummer und EAN;
  Nachladen über `offset`, Obergrenze 500 Zeilen je Abfrage (Ladennetz).
- Tests: `tests/test_bestand.py` (16 Fälle: Filter je Lagerort, externer
  Standort ohne Datum, ausverkaufte und negative Zeilen, Suche über vier
  Felder, seitenweises Nachladen, API mit aktiver und fremder Filiale,
  unbekannte Filiale, Rechte ohne Anmeldung). Gesamtsuite: 438 bestandene
  Tests (vorher 421).
- Im Browser gegen eine SQLite-Testdatenbank durchgespielt: Vorauswahl der
  aktiven Filiale, Umschalten auf „Alle Filialen und Standorte", Suche,
  negativer Bestand, GEWA-Zeile mit Hinweis statt Datum. Dabei aufgefallen und
  behoben: die erste Abfrage schickte `alle=true`, weil die Auswahlliste vor
  der ersten Antwort nur den Eintrag „alle" kennt — gezeigt wurde also alles,
  obwohl die Sitzungsleiste SF1 anzeigte. Die Seite merkt sich die Wahl jetzt
  selbst und überlässt die erste Abfrage dem Server. Gegen PostgreSQL steht
  der Durchgang noch aus.

**Details zu Phase C, Teilaufgabe C3 — Ausbuchen per Scan** (siehe
`docs/architektur.md`, Abschnitt „Ausbuchen"):
- Neu `app/services/ausbuchung.py`, `app/routers/ausbuchung.py`
  (`/ausbuchen`, `/api/ausbuchen/stammdaten`, `/api/ausbuchen`,
  `/api/ausbuchen/{id}/storno`), Seite `app/templates/ausbuchen.html` mit
  `app/static/js/ausbuchen.js`, Navigationseintrag „Ausbuchen" auf allen
  Seiten. Kein Schema-Eingriff: `lagerbewegungen` kannte `verkauf` und
  `ausbuchung` schon.
- **Ein Scan = ein Stück** (F15): der Scan bucht sofort, ohne Mengenabfrage.
  Schnelle Scans werden im Browser gesammelt und der Reihe nach gebucht.
- **Gründe** (F14): Verkauf wird als `typ = verkauf` gebucht, Bruch/Defekt,
  Diebstahl/Schwund, Eigenbedarf, Retoure und Sonstiges als `ausbuchung`;
  der Grund steht in `lagerbewegungen.grund`, bei Sonstiges mit dem freien
  Text (`sonstiges: …`, Pflicht, höchstens 150 Zeichen).
- **Zu wenig Bestand** (F9): gebucht wird trotzdem, die Antwort meldet
  `bestand_reicht_nicht` und die Seite warnt. Fehlt die Bestandszeile ganz,
  entsteht sie mit negativer Menge und ohne Eingangsdatum. Ein Abgang ändert
  das Eingangsdatum nie.
- **Rückgängig** statt Löschen (Regel 2): eine Gegenbuchung `typ = korrektur`
  mit `grund = 'storno:<id>'`, je Ausbuchung höchstens einmal.
- Gebucht wird unter derselben Sperre wie der Zugang; welcher Lagerort
  gebucht werden darf, prüft der Server (`resolve_wareneingang_lagerort`,
  vorgewählt die aktive Filiale). Ausbuchen dürfen alle Rollen (Regel 9).
- **Vorübergehender Test-Knopf** (Wunsch vom 23.09.2026): in der
  Bestandsansicht je Zeile „−1", bucht über denselben Weg ein Stück ab
  (`grund = 'test'`, in der Ausbuchen-Seite nicht wählbar). Funktioniert auch
  für Varianten ohne EAN. Sichtbar für alle Rollen; wird entfernt, sobald das
  Ausbuchen im Laden erprobt ist.
- Tests: `tests/test_ausbuchung.py` (24 Fälle: ein Stück je Scan, Gründe und
  Typ, Pflichttext bei Sonstiges, unbekannte EAN/Grund buchen nichts,
  Variante ohne EAN, negativer Bestand mit Warnung, Eingangsdatum bleibt,
  Bestand = Summe der Bewegungen, Storno einmalig und nur für Abgänge, API
  inklusive Rechte). Gesamtsuite: 463 bestandene Tests (vorher 438).
- Im Browser gegen eine SQLite-Testdatenbank durchgespielt: Scan mit Enter,
  Scan ins Minus mit Warnung, Rückgängig, „−1" in der Bestandsansicht bis ins
  Minus. Gegen PostgreSQL steht der Durchgang noch aus.

**Details zu Phase C, Teilaufgabe C4 — Umlagerung** (siehe
`docs/architektur.md`, Abschnitt „Umlagern"):
- Neu `app/services/umlagerung.py`, `app/routers/umlagerung.py`
  (`/umlagern`, `/api/umlagerung/stammdaten`, `/api/umlagerung`), Seite
  `app/templates/umlagern.html` mit `app/static/js/umlagern.js`,
  Navigationseintrag „Umlagern". Migration `e1f2a3b4c5d6`:
  `lagerbewegungen.eingangsdatum`.
- **Die empfangende Filiale bucht beim Empfang** (F5): vorgewählt ist die
  aktive Filiale als Ziel, die Quelle wird gewählt. Eine Buchung erledigt
  Abgang und Zugang, ganz oder gar nicht; einen Zustand „unterwegs" gibt es
  nicht.
- Ware sammeln per Scan (jeder Scan +1) oder über die Suche im Bestand der
  Quelle — so gehen auch Varianten ohne EAN (Regel 5). Menge je Zeile
  änderbar.
- **Datumsregeln**, alle nur über `lagerorte.verkauf` entschieden:
  externer Standort → Filiale setzt das Eingangsdatum (auf Wunsch
  rückwirkend) und startet die Uhr (D13) — auch in einer Filiale, die den
  Artikel schon kannte, weil es eine Nachlieferung ist; Filiale → Filiale
  behält das Datum der Ware (D17) und lässt die Uhr des Ziels unverändert
  (F10), ausser das Ziel hatte den Artikel nie — dann startet sie ab
  Eintreffen (F11, geprüft je Artikel, nicht je Variante); Ziel ohne Verkauf
  bekommt kein Datum (Regel 6).
- `reduktion.letzter_wareneingang()` zählt neu auch Umlagerungen mit
  `eingangsdatum` — Etikett und später Phase D sehen die Uhr also richtig.
- **Annahme:** reicht der Bestand an der Quelle nicht, wird gewarnt und
  trotzdem gebucht (wie F9 beim Ausbuchen) — die Ware ist ja physisch
  angekommen, und der migrierte Bestand ist ungenau. Bitte melden, falls das
  anders sein soll.
- Tests: `tests/test_umlagerung.py` (24 Fälle: alle Datumsregeln inkl.
  rückwirkend und Zukunft, F11 je Artikel, Journalzeilen, Zusammenzählen,
  Fehlbestand, ungültige Positionen buchen nichts, ganz oder gar nicht, API
  inklusive Rechte). Gesamtsuite: 488 bestandene Tests (vorher 463).
- Im Browser gegen eine SQLite-Testdatenbank durchgespielt: GEWA → SF1 per
  Scan (2 Stück) und über die Bestandssuche (Variante ohne EAN), Bestand
  danach an beiden Orten kontrolliert. Gegen PostgreSQL steht der Durchgang
  noch aus; das SQL der Migration ist offline geprüft.

**Details zu Phase C, Teilaufgabe C5 — Korrekturen** (siehe
`docs/architektur.md`, Abschnitt „Korrigieren"):
- Neu `app/services/korrektur.py`, `app/routers/korrektur.py`
  (`/api/korrektur/gruende`, `/api/korrektur`). Keine eigene Seite: jede
  Zeile der Bestandsansicht hat einen Knopf „Zählen", der darunter ein
  kleines Formular öffnet. Kein Schema-Eingriff.
- **Gezählte Menge statt Differenz** (23.09.2026): die Differenz wird erst
  unter der Sperre gerechnet — wurde zwischen Zählen und Buchen verkauft,
  zählt der Stand von jetzt. Stimmt der Bestand schon, entsteht keine Zeile.
  Die gebuchte Zeile ist `typ = korrektur`, `menge` = Differenz.
- **Gründe:** `inventur`, `falsch_gebucht`, `gefunden`, `sonstiges: …`
  (Pflichttext). **Rechte:** alle Rollen (Regel 9).
- Eine Korrektur ist kein Wareneingang: das Eingangsdatum bleibt, auch wenn
  eine neue Bestandszeile entsteht.
- Tests: `tests/test_korrektur.py` (19 Fälle: Differenz minus/plus, nichts
  buchen bei gleichem Stand, 0 gezählt, aus negativem Bestand, neue
  Bestandszeile ohne Datum, Datum bleibt, Pflichttext, ungültige Mengen,
  unbekannter Grund/Variante, API inklusive Rechte). Gesamtsuite: 507
  bestandene Tests (vorher 488).
- Im Browser gegen eine SQLite-Testdatenbank durchgespielt (4 → 1 und
  2 → 5, auch mit Enter im Mengenfeld).

Damit ist **Phase C abgeschlossen**. Offen bleiben der Durchgang gegen
PostgreSQL und das Entfernen des Test-Knopfs „−1", sobald das Ausbuchen im
Laden erprobt ist.

**Details zu den Inbox-Anforderungen vom 23.09.2026** (umgesetzt am
24.09.2026; Anforderungen und Entscheid zur Löschung in
`docs/anforderungen-inbox-2026-09-23.md`):
- **Lieferantengruppen und Etikett-Codes:** Gruppe = `lieferanten.typ`
  (neu `intern` für Nike, adidas, The North Face), Code daraus abgeleitet
  (`app/core/lieferanten.py`: Intersport 111, ECOM 555, Händler 333,
  Dritte-Händler 999, Intern 444) und fett aufs Etikett. Je Gruppe ein
  Lieferant für die Erfassung von Hand. Migration `f2a3b4c5d6e7`.
  **Offen:** ECOM-Retouren kommen im Intersport-Layout und werden noch als
  Intersport (111) zugeordnet, bis der Parser die Referenz „ret.Ecom" erkennt.
- **Bestand:** Farbe, Grösse und Hauptgruppe in eigenen Spalten; Zeilen mit
  Menge 0 erscheinen nicht mehr (Schalter entfernt), der Artikel bleibt im Stamm.
- **Ausbuchungen als Liste:** Seite „Ausbuchen" zeigt alle Verkäufe und
  Abgänge aus dem Journal mit Zeit, Person und Grund, je Filiale filterbar
  (`GET /api/ausbuchungen`).
- **Artikelsuche:** „EAN scannen" (fokussiert, Scan + Enter sucht sofort) und
  „Schnellsuche" vorne, übrige Filter unter „Weitere Filter", dort auch „Nur
  von Hand erfasst".
- **Übersicht:** Begrüssung, Schnellzugriffe, Kennzahlen der aktiven Filiale,
  „Anstehend" (Lieferungen, negativer Bestand, Reduktionsalter −50/−70 % inkl.
  nächste 30 Tage, Artikel ohne Kategorie/EAN), „Aktuelles"
  (`app/services/uebersicht.py`, erweitertes `GET /api/dashboard`). Die
  Reduktionszahlen sind ein **Hinweis** nach Alter; ob schon reduziert wurde,
  weiss das System erst mit Phase D.
- **Artikel löschen:** `DELETE /api/articles/{id}` und Knopf auf der
  Artikelseite, nur Filialleiter/Zentrale, nur ohne Beleg
  (`app/services/artikel_loeschen.py`).
- Tests: `test_lieferantengruppen.py`, `test_uebersicht.py`,
  `test_artikel_loeschen.py`, Ergänzungen in `test_bestand.py`,
  `test_ausbuchung.py`, `test_ean_etikett.py`, `test_manuelle_erfassung.py`.
  Gesamtsuite: 533 bestanden, 20 übersprungen (vorher 507). Im Browser gegen
  eine SQLite-Testdatenbank angesehen: Übersicht, Bestand, Ausbuchen mit
  Liste, Artikelsuche mit Scan. Der Lösch-Knopf selbst wurde nur über die
  API-Tests geprüft (Filialleiter-Anmeldung braucht ein Passwort).

**Details zu Phase A, Punkt 1** (siehe `docs/datenmodell.md` für die Tabellen im Detail):
- Neue Tabellen `lagerorte` (Seed-Daten) und `benutzer_lagerorte` (m:n, mit `ist_primaer`) via Alembic-Migration `a1b2c3d4e5f6`; bestehende Benutzer auf SF1 zugeordnet. Migration `b8c9d0e1f2a3` ergänzt VEBO und das Lager Dietikon (Rev. 6), womit es sieben Lagerorte gibt: SF1–SF4 mit Verkauf, GEWA/VEBO/DIETIKON ohne.
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
- ~~Bewusst noch nicht gebaut: eine Oberfläche zur manuellen Kategorie-Wahl~~ — erledigt mit Teilaufgabe B8 (siehe unten): fehlt oder greift der Vorschlag nicht, wird die Kategorie auf der Artikelseite bzw. beim Erfassen von Hand gewählt und ist danach verbindlich.
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
  Lieferadresse erkannt: SF2 · Conthey") oder der Hinweis, dass nichts erkannt
  wurde. `/import-invoice` nimmt den gewählten Lagerort entgegen und prüft ihn
  serverseitig; ohne Angabe bleibt alles wie bisher.
- Buchbar sind **alle** Lagerorte (eigene Filiale zuerst). Sonst liesse sich
  eine Lieferung an eine andere Filiale oder an die GEWA gar nicht erfassen —
  D19 wäre für genau die Fälle wirkungslos, für die es gedacht ist. Wer hier
  hinkommt, darf ohnehin Dokumente hochladen (Regel 9); eine falsch gewählte
  Filiale ist über eine Umlagerung korrigierbar. **Von Fabian bestätigt**
  (21.09.2026) und als D26 festgehalten. Der Filialwechsel bleibt unverändert
  bei den zugewiesenen Filialen; lesen dürfen Mitarbeiter und Filialleiter
  gemäss Bestätigung vom 22.09.2026 alle Filialen (Abschnitt 10).
- Tests: `tests/test_lieferadresse.py` (24 Tests: jede Seed-Adresse,
  Lieferadresse schlägt Rechnungsadresse, Gleichstand ohne Vorschlag,
  Schreibweisen, „Lieferschein" ist kein Anker) und
  `tests/test_wareneingang_lagerort.py` (7 Tests über die echte App **mit
  Anmeldung**, also inklusive Rechteweg). Gesamtsuite: 213 bestandene Tests
  (vorher 182).
- Gegen echtes PostgreSQL 16 im Browser durchgespielt: Anmeldung, Upload einer
  Rechnung mit Lieferadresse Conthey, Vorauswahl SF2 mit Begründung,
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
- ~~**Offen geblieben:** Kommt *mehr* an als bestellt, bucht das System es
  (Bestand = was physisch da ist). Am 22.09.2026 bestätigt: zusätzlich warnen,
  Buchung weiterhin zulassen; die Warnung ist noch umzusetzen.~~ — erledigt mit
  Phase C, Teilaufgabe C1 (siehe unten).

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
- ~~**Offen geblieben:** Kategorie (B8) und interne EAN samt Etikett (B7)
  fehlen auch hier noch~~ — erledigt: B7 erzeugt die interne EAN und druckt
  das Etikett gleich nach dem Erfassen, B8 ergänzt die Kassenkategorie als
  freiwilliges Feld je Position.

**Details zu Phase B, Teilaufgabe B7 — interne EAN und Etikett** (Regel 5/6,
D10, D14, D24, D25; siehe `docs/architektur.md`, Abschnitt „Interne EAN und
Etikett"):
- `app/services/ean.py`: Prüfziffer nach GS1, strenge Prüfung nachgetragener
  EANs und die **interne EAN-13** nach dem Muster `20` + zehnstellige
  Varianten-Id + Prüfziffer. Kein Zähler nötig, für dieselbe Variante immer
  dieselbe Nummer, `varianten.ean_intern` markiert sie. Eine bestehende EAN
  wird **nie** überschrieben (Regel 4).
- Unterschied zum Import (bewusst): dort bleibt es beim Formatcheck (B3), weil
  die Nummer so im Lieferantendokument steht. Wer sie hier von Hand einträgt,
  bekommt auch die Prüfziffer geprüft — ein Zahlendreher bliebe sonst für
  immer im Artikelstamm.
- `app/services/barcode.py`: EAN-13/EAN-8 als Strichmuster, selbst gerechnet
  (keine zusätzliche Bibliothek, Regel 1). UPC-12 wird als EAN-13 mit
  führender Null gedruckt; eine EAN-14 (Umkarton, eigentlich ITF-14) oder eine
  falsche Prüfziffer ergibt bewusst **keinen** Strichcode, sondern nur die
  Zahl — lieber keiner als einer, den die Kasse nicht annimmt.
- `app/services/etikett.py`: Etikett als PDF in Etikettengrösse (eine Seite je
  Etikett, `anzahl` wiederholt sie), gezeichnet mit PyMuPDF und den im PDF
  eingebauten Schriften. Darauf: Jahrgang, Lieferant, UVP, Reduktionsstufe
  (D25) plus Marke, Bezeichnung, Farbe/Grösse und Strichcode.
- `app/services/reduktion.py`: Regel 6 als eigener, getesteter Baustein —
  letzter Wareneingang derselben Artikelnummer **in dieser Filiale**, daraus
  volle Monate und die Stufe (18 → 50 %, 36 → 70 %). Die Hinweise für die
  Filialen (Phase D) bauen darauf auf. Die 30 % aus D25 sind eine
  Entscheidung des Ladens und lassen sich beim Druck mitgeben.
- Oberfläche an zwei Stellen: auf der **Artikelseite** ein Abschnitt „EAN &
  Etikett" (EAN ansehen, erzeugen, nachtragen, Etikett mit Grösse/Reduktion/
  Anzahl öffnen) und direkt nach der **manuellen Erfassung** ein Knopf
  „Etiketten drucken" für den ganzen Wareneingang, ein Etikett je Stück.
  Beides auch für **Mitarbeiter** (Regel 9). Übersetzungen DE/FR/EN.
- **Annahmen, solange zwei Fragen offen sind:** Etikettengrösse einstellbar
  (`GROESSEN`), Voreinstellung damals 50 × 30 mm — seit 23.09.2026
  84 × 47 mm, die bestätigte Rollengrösse; der Strichcode ist drauf (siehe
  Abschnitt 10, Frage 2). Beides ist an einer Stelle änderbar.
- Kein Schema-Eingriff nötig: `varianten.ean`/`ean_intern` gab es schon, sie
  werden jetzt benutzt.
- Tests: `tests/test_ean_etikett.py` (72 Tests: Prüfziffern echter EANs,
  interne Nummern, Strichmuster gegen die Norm inkl. Selbsttest der
  Codetabellen, Reduktionsstufen an den Stichtagen, Etikettendaten aus der
  Datenbank, PDF-Grösse und -Inhalt, EAN setzen inkl. Konflikten und der
  ganze Weg über die API). Gesamtsuite: 360 bestandene Tests (vorher 288).
- Gegen echtes PostgreSQL 16 geprüft und im Browser durchgespielt: interne
  EAN erzeugen, EAN mit falscher Prüfziffer abgelehnt, Etikett-PDF (50 × 30
  und 100 × 50 mm) angesehen, Etiketten eines Wareneingangs gedruckt,
  Sprachwechsel DE/FR/EN.

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
- **Regel 6 (externe Standorte)**: Ware an einen Lagerort ohne Verkauf (`lagerorte.verkauf = false` — GEWA, VEBO, Dietikon) bekommt
  jetzt tatsächlich kein Eingangsdatum — weder am Wareneingang noch in
  `bestand.aeltestes_eingangsdatum`. Die Reduktionsuhr (18/36 Monate) startet damit erst bei
  Ankunft in einer Filiale.
- **`delete_invoice()`**: `first_seen`/`last_seen` wurden aus dem Eingangsdatum neu berechnet,
  der Import setzt sie aber aus dem Dokumentdatum — nach der Änderung oben wären sie für
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
  ältestes Eingangsdatum, Regel 6 je externem Standort, Neuberechnung beim Löschen — diese Kernlogik aus Regel 2
  hatte bis dahin keinen einzigen Test) und zwei Katalogtests in `tests/test_i18n.py`, die Keys
  und Platzhalter aller drei Sprachen vergleichen. Gesamtsuite: 145 bestandene Tests.

**Details zu Phase B, Teilaufgabe B8 — Kategorie von Hand wählen** (Regel 4/7/8,
Regel 9/D21; siehe `docs/architektur.md`, Abschnitt „Kassenkategorie: Vorschlag
und Wahl von Hand"):
- Ausgangslage: Den Vorschlag aus dem FEDAS-Code gab es seit dem ersten
  Teilschritt, aber keinen Weg, die Lücken zu füllen. Und Lücken sind der
  Normalfall: nur INTERSPORT liefert überhaupt einen FEDAS-Code, von Hand
  erfasste Ware hat gar keinen Beleg (D27), und von den elf Sportbereichen
  sind erst fünf Codes aus echten Rechnungen bestätigt.
- `app/services/kategorien.py`: Auswahlliste in der Reihenfolge der Kasse
  (Regel 8, nicht alphabetisch), Stand eines Artikels (gesetzte Kategorie,
  Herkunft, FEDAS-Code und aktueller Vorschlag), setzen und leeren. Dazu
  `merke_kategorie()` als gemeinsamer Baustein für nebenbei entstehende
  Artikel: füllt nur, was leer ist, und überschreibt nie.
- `artikel.kategorie_manuell` (Migration `c9d0e1f2a3b4`) merkt sich die
  Herkunft: `false` = Vorschlag aus dem FEDAS-Code, `true` = von Hand gewählt.
  Der Unterschied steht in der Oberfläche, denn die Zuordnungstabelle ist noch
  nicht vollständig bestätigt — wer die Kategorie von Hand gesetzt hat, soll
  das später erkennen. Bestehende Artikel bekommen `false` (Server-Default):
  sie können ihre Kategorie bisher nur vom Vorschlag haben.
- „Einmal pro Artikel, danach gemerkt" gilt jetzt in beide Richtungen: der
  Import füllt weiterhin nur eine leere Kategorie, eine Wahl von Hand
  überschreibt umgekehrt einen falschen Vorschlag. Leeren stellt den
  Ausgangszustand wieder her (Kategorie offen, `kategorie_manuell = false`) —
  ein späterer Beleg mit bekanntem Code darf dann wieder vorschlagen.
- Endpunkte: `GET /api/kategorien` (alle 35 Kategorien),
  `GET/PUT /api/articles/{id}/kategorie`. Angesprochen wird der Artikel wie
  bei Notizen und Preisen über die Varianten-Id; die Kategorie gilt für alle
  Farben und Grössen desselben Modells (Regel 4). Rechte: jede Anmeldung, auch
  Mitarbeiter — Artikelstamm pflegen ist kein Dokumenten-Upload (Regel 9/D21).
- Oberfläche an drei Stellen, i18n DE/FR/EN (Regel 7; die Kategorienamen selbst
  werden nicht übersetzt, sie stehen so in der Kasse):
  - Artikelseite: eigener Abschnitt „Kassenkategorie" mit aktueller Kategorie,
    Herkunft („von Hand gewählt" bzw. „Vorschlag aus dem FEDAS-Code") und der
    Auswahl. Fehlt die Kategorie, sagt die Seite auch warum — kein Code auf dem
    Beleg oder Code noch nicht zugeordnet.
  - Manuelle Erfassung: Kategorie je Position, freiwillig (D23), mit Hinweis,
    dass eine bestehende unverändert bleibt. Ein Scan zeigt die Kategorie des
    bekannten Artikels gleich mit.
  - Artikelsuche: neue Spalte (zuhinterst, damit die gemerkten Spaltennummern
    stimmen) und ein Filter mit „Ohne Kategorie" — erst damit findet man die
    Artikel, bei denen noch jemand wählen muss. `kategorie_fehlt=true` sticht
    `kategorie_id`, sonst käme eine leere Liste ohne erkennbaren Grund.
- Die Auswahllisten sind nach Hauptgruppe gruppiert (35 Einträge sind zu viele
  für eine flache Liste), tragen aber den vollen Namen („Textil · Winter"):
  zugeklappt zeigt ein `<select>` nur den Eintrag, und „Winter" allein gibt es
  dreimal. Gemeinsamer Baustein `app/static/js/kategorien.js`, damit
  Artikelseite, Erfassung und Suche dieselbe Beschriftung verwenden.
- Excel-Export bewusst unverändert: seine Spaltenüberschriften sind fest
  deutsch (offener Punkt, siehe Phase A Punkt 2) — eine neue Spalte gehört in
  denselben Schritt wie deren Übersetzung.
- Tests: `tests/test_kategorien.py` (46 Tests: Reihenfolge der Kasse, Vorschlag,
  setzen/leeren/korrigieren, gilt für alle Varianten des Artikels, nie
  überschreiben, API samt Rechten und Fehlerfällen, Erfassung mit und ohne
  Kategorie, Filter der Artikelsuche) und ein weiterer Fall in
  `tests/test_importer_fedas.py` (eine Wahl von Hand übersteht eine spätere
  Rechnung mit bekanntem Code). Gesamtsuite: 416 bestandene Tests (vorher 369).
- Gegen echtes PostgreSQL 16 geprüft: Migration vor und zurück, Auswahlliste,
  Stand, Setzen und Filter über die API; danach der ganze Ablauf im Browser
  (Artikel ohne Kategorie wählen und speichern, Artikel mit Vorschlag, Filter
  „Ohne Kategorie", Kategorie beim Erfassen).

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
- ~~Filialbezug der Ansichten: Dashboard, Rechnungsliste und Artikeldetails zeigen jedem
  angemeldeten Konto die Dokumente **aller** Filialen. Ob Regel 9 („Admin/Zentrale
  filialübergreifend") auch das Lesen einschränken soll, ist eine fachliche Frage an Fabian.~~
  — geklärt am 22.09.2026 (Abschnitt 10, Leserechte): Mitarbeiter und Filialleiter dürfen
  Dokumente und Bestände aller Filialen sehen, die Schreibrechte bleiben unverändert. Das
  bisherige Verhalten der Ansichten ist damit bestätigt, am Code war nichts zu ändern.

**Konzeptänderung Rev. 6** (21.09.2026): zwei externe Verarbeitungsstellen statt
einer, plus ein externes Lager.
- Neu neben GEWA: **VEBO** (fachlich gleichwertige Verarbeitungsstelle) und das
  **Lager Dietikon**. Alle drei mit `verkauf = false`, Migration `b8c9d0e1f2a3`
  (idempotent; der Downgrade löscht einen neuen Lagerort nur, solange nichts
  daran hängt). GEWA heisst jetzt „GEWA (externe Verarbeitung)“, damit der
  Unterschied zum reinen Lager im Namen sichtbar ist.
- Regel 6 gilt unverändert für alle drei: kein Eingangsdatum, die Reduktionsuhr
  startet erst in einer Filiale SF1–SF4. Der Code fragt dafür immer
  `lagerorte.verkauf` ab und nie einen einzelnen Code — ein weiterer externer
  Standort greift dadurch automatisch. Verarbeitungsstelle und Lager
  unterscheidet das Schema bewusst nicht (bestätigt am 21.09.2026).
- `app/services/lieferadresse.py`: Das Kennwort für die Lagerort-Erkennung ist
  jetzt das erste **unterscheidende** Wort des Namens. „Lager Dietikon“ hätte
  sonst „Lager“ als Kennwort bekommen und jeden Beleg mit diesem Wort dorthin
  gebucht; erkannt wird Dietikon über den Ortsnamen, VEBO über seinen Namen.
- Tests für Eingangsdatum und Bestand über alle drei Standorte parametrisiert
  (`tests/test_lagerbewegungen.py`: 10 → 16), dazu zwei neue Fälle in
  `tests/test_lieferadresse.py` (VEBO über den Namen, „Lager“ darf nicht
  treffen). Gesamtsuite: 297 bestandene Tests.
- **Offen**: die Adressen von VEBO und Dietikon fehlen noch und sind in
  `app/core/lagerorte.py` als offen markiert. Bis sie da sind, wird VEBO nur
  über seinen Namen erkannt und Dietikon nur über den Ortsnamen.

*Dieses Dokument wird bei jeder Entscheidung/Phase nachgeführt. Die Master-Kopie liegt im Claude-Projekt „Sportfabrik WarenWirtschaftsSystem“.*

## Lokaler Abgleich am 22.09.2026

**Abendstand:** Filialcodes korrigiert (SF2 Conthey, SF3 Regensdorf, SF4
Hägendorf, Migration `d0e1f2a3b4c5`), Belege dürfen für den Parserbau gezeigt
werden, Phase C geplant und die Teilaufgaben C1 und C2 gebaut. Lokale Suite:
438 bestanden, 20 übersprungen (SQLite). Gegen PostgreSQL ist davon noch
nichts gelaufen. Alles auf dem Branch `feature/warenwirtschaft-v2`, gepusht.

Cloud-main `d1c6533` übernommen. Lokale Suite mit `DATABASE_URL=sqlite:// .venv/bin/pytest -q`: 415 bestanden, 20 übersprungen. Kein neuer PostgreSQL- oder Produktivtest. Codegraph mit `--code-only` frisch aufgebaut und lokal als HTML und Obsidian-Vault exportiert; Graphdateien bleiben gitignored. Bestätigte Antworten aus dem Main-Vault in Abschnitt 10 übernommen.
