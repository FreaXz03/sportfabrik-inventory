# CLAUDE.md — Sportfabrik Warenwirtschaftssystem

Anleitung für Claude Code in diesem Repo. **Zuerst `docs/projekt-kontext.md` lesen** — dort stehen Zielbild, alle Entscheidungen (D1–D27), Datenmodell-Vorschlag und Roadmap. Bei Widerspruch zwischen altem Code/alter Doku und `projekt-kontext.md` gilt `projekt-kontext.md`.

## Worum es geht

Warenwirtschaftssystem für die **Sportfabrik** (Intersport-Outlet, 4 Filialen in der Schweiz: SF1 Volketswil, SF2 Conthey, SF3 Regensdorf, SF4 Hägendorf). Dazu drei externe Standorte ohne Verkauf: die Verarbeitungsstellen **GEWA** und **VEBO** (fachlich gleichwertig) und das **Lager Dietikon**.
Ware wird per Upload (Rechnung / Lieferschein / Auftragsbestätigung) oder manuell erfasst, der Artikelstamm bleibt für immer, Bestand wird pro Filiale geführt, Filialen bekommen Runterschreib-Hinweise (30/50/70 %). Später Anbindung an die Intersport-Kasse.

Das bestehende Repo (FastAPI-App für Intersport-Rechnungen) ist die Ausgangsbasis und wird **umgebaut**, nicht neu geschrieben: Parser, zweistufiger Import, Hash-Prüfung, Audit-Snapshot, Advisory-Lock, Auth und Tests weiterverwenden.

## Harte Regeln

1. **Belegdaten bleiben lokal — sonst ist KI erlaubt.** Rechnungen, Lieferscheine und Auftragsbestätigungen werden von **eigenen Parsern** gelesen, die vollständig auf dem Server laufen (PyMuPDF, Tesseract, OpenCV o. ä.): kein Sprachmodell, kein Cloud-Dienst bekommt Belegdaten zu sehen, und ein unbekanntes Layout wird gemeldet statt geraten. Das gilt für den **Betrieb**. Für den **Parserbau** darf Fabian einzelne Belege bewusst zeigen (Entscheid 22.09.2026) — der Inhalt geht damit an den Modellanbieter, dient nur diesem Zweck und wird nirgends veröffentlicht. Belege massenhaft oder unbemerkt einlesen bleibt verboten (siehe Graphify). Ausserhalb der Belegverarbeitung ist KI zulässig, auch extern. Entwicklungswerkzeuge nach demselben Kriterium: Graphify nur mit `--code-only` laufen lassen, sonst gehen Rechnungen aus `uploads/` bzw. `Rechnungen/` an ein Sprachmodell (siehe `docs/obsidian-graphify.md`). Unabhängig von KI bleibt das Frontend **ohne externe CDNs** — es muss im Ladennetz ohne Internet laufen.
2. **Bestand nie direkt überschreiben** — jede Änderung ist eine Zeile in `lagerbewegungen` (Zugang, Verkauf, Ausbuchung, Korrektur, Umlagerung). Bestand wird daraus abgeleitet bzw. konsistent mitgeführt.
3. **Bestand erst buchen, wenn Ware eingetroffen ist** — Auftragsbestätigungen erzeugen nur einen *erwarteten* Wareneingang.
4. **Artikelstamm ist filialübergreifend**, Bestand / Wareneingänge / Reduktionen sind filialbezogen (`lagerort_id`). Der Stamm bleibt — einzige Ausnahme: einen von Hand erfassten Artikel ohne Beleg dürfen Filialleiter/Zentrale ganz löschen (Fehleintrag, Entscheid 24.09.2026).
5. **EAN ist optional.** Varianten ohne EAN müssen funktionieren (Schlüssel: Lieferant + Artikelnr. + Farbe + Grösse). Interne EANs: EAN-13 im GS1-Bereich 20–29 mit korrekter Prüfziffer, als intern markiert.
6. **Eingangsdatum-Regeln** (für Lagerdauer / Reduktion):
   - Ware an einen externen Standort (GEWA, VEBO, Dietikon — alle `verkauf = false`): noch **kein** Eingangsdatum; gesetzt bei Ankunft in einer Filiale SF1–SF4 (auch rückwirkend). Massgeblich ist immer `lagerorte.verkauf`, nie der einzelne Code.
   - Umlagerung Filiale → Filiale: **ursprüngliches Datum bleibt**.
   - Reduktions-Hinweise pro Filiale: 18 Monate → 50 %, 36 Monate → 70 %, gerechnet ab letztem Wareneingang derselben Lieferanten-Artikelnummer **in dieser Filiale**; Nachlieferung startet die Uhr neu.
7. **Mehrsprachig DE / FR / EN.** Keine neuen hartcodierten UI-Texte — immer Übersetzungs-Keys (Templates + JS + Fehlermeldungen). Deutsch ist Standard. Artikeldaten aus Lieferantendokumenten werden nicht übersetzt.
8. **Kassenkategorien** exakt wie in der Kasse: Hauptgruppe (Textil, Hartware, Schuhe, Velo, Food) × Sportbereich (Velo, Freizeit, Tennis, Winter, Outdoor, Fussball, Kids, Baden, Indoor, Running, Rollsport); Velo und Food ohne Sportbereich.
9. **Rechte (vorerst):** Mitarbeiter dürfen alles **ausser Dokumente hochladen/bearbeiten/löschen** — Lagerarbeit wie „Ware eingetroffen" bestätigen ist ausdrücklich erlaubt (D21). Filialleiter zusätzlich Dokumente. Admin/Zentrale filialübergreifend.
10. **Einkaufspreis (EK)** optional speichern, wenn im Dokument vorhanden — nie Pflicht.

## Ergänzende Produktanforderungen vom 23.09.2026

Benutzerfreundlichkeit und gute Lesbarkeit sind besonders wichtig: mehrere Mitarbeitende nutzen eine Brille und/oder haben wenig PC-Erfahrung. Oberflächen übersichtlich halten, Suche vereinfachen und Scanner-Abläufe unterstützen. Die neuen Anforderungen und Lieferantencodes stehen in `docs/anforderungen-inbox-2026-09-23.md`. Die Artikellöschung ist am 24.09.2026 geklärt und umgesetzt (nur von Hand erfasste Artikel ohne Beleg, nur Filialleiter/Zentrale — siehe Regel 4).

## Technik & Konventionen

- Python 3.10+, FastAPI, SQLAlchemy 2.0, PostgreSQL, Jinja-Templates, Vanilla JS/CSS (kein Framework, keine Build-Pipeline).
- **Schema-Änderungen nur über Alembic** (`alembic revision --autogenerate`, danach Migration prüfen). Bestehende Daten migrieren (Altdaten → Lagerort SF1), nie verwerfen.
- Beträge/Mengen als `Numeric`, nie `float`.
- Serverseitig validieren — Client-Werten nie vertrauen (siehe `app/services/corrections.py`).
- Struktur beibehalten: `app/core/` (DB, Modelle, Security), `app/routers/` (Endpunkte), `app/services/` (Logik), `app/static/`, `app/templates/`. Neue Lieferanten-Parser als eigene Module (z. B. `app/services/parsers/<lieferant>.py`) mit gemeinsamer Schnittstelle + automatischer Lieferanten-Erkennung.
- Code und Bezeichner Englisch oder Deutsch wie im bestehenden Code; UI-Texte über i18n; Commit-Messages kurz und aussagekräftig.

## Wissensgraph (Graphify)

Liegt lokal ein `graphify-out/graph.json`, zuerst dort nachschlagen (Module,
Funktionen, Aufrufbeziehungen), dann `docs/projekt-kontext.md` /
`docs/architektur.md` für das Warum, und erst zuletzt einzelne Quelldateien
öffnen. Der Graph ist eine Momentaufnahme — **bei Widerspruch gilt der
Quellcode**.

`graphify-out/` ist bewusst gitignored: das Repo ist öffentlich, und ein ohne
`--code-only` gebauter Graph enthält Inhalte aus Lieferantenrechnungen.
Cloud-Sessions haben den Graphen deshalb nicht. Details:
`docs/obsidian-graphify.md`.

## Tests

- `pytest` im Projektordner; Tests für jede neue Logik (Lagerbewegungen, Reduktionsregeln, EAN-Prüfziffer, Parser, Rechte).
- Vor jedem Commit: alle Tests grün.

## Arbeitsweise

- Arbeits-Branch: `feature/warenwirtschaft-v2`. Nicht direkt auf `main` committen.
- In kleinen, nachvollziehbaren Commits arbeiten (eine Teilaufgabe = ein Commit).
- Nach jeder abgeschlossenen Phase: `docs/projekt-kontext.md` (Abschnitt „Stand der Umsetzung“), `README.md` und `docs/datenmodell.md` / `docs/api-referenz.md` nachführen.
- Bei fachlichen Unklarheiten (Filialabläufe, Preise, Kasse) nachfragen statt raten — Fabian arbeitet im Laden und kennt die Abläufe.

## Abgeschlossen: Phase A — Fundament

1. Lagerorte SF1–SF4 + GEWA/VEBO/DIETIKON (Seed-Daten), Benutzer ↔ Lagerort, Rollen gemäss Regel 9, Filialwechsel in der Oberfläche. ✅ abgeschlossen — siehe `docs/projekt-kontext.md` Abschnitt 11.
2. i18n-Grundgerüst (DE/FR/EN), Sprachwahl pro Benutzer, bestehende Seiten auf Keys umstellen. ✅ abgeschlossen (inkl. Backend-Fehlermeldungen) — siehe `docs/projekt-kontext.md` Abschnitt 11 und `docs/architektur.md` Abschnitt „Mehrsprachigkeit (i18n)".
3. Neues Datenmodell gemäss `docs/projekt-kontext.md` Abschnitt 8.2 (Lieferanten, Kategorien, Artikel/Varianten, Preise, Dokumente, Wareneingänge, Lagerbewegungen, Bestand) + Alembic-Migration der bestehenden Daten. ✅ abgeschlossen, inkl. Umstellung des Live-Imports (nicht nur der Migration) — siehe `docs/projekt-kontext.md` Abschnitt 11.
4. Tests + Doku nachführen. ✅ abgeschlossen — siehe `docs/projekt-kontext.md` Abschnitt 11.

Phase A ist damit vollständig abgeschlossen.

## Abgeschlossen: Phase B — Wareneingang v2

Teilaufgaben (Details und Begründung der Reihenfolge: `docs/projekt-kontext.md`
Abschnitt 11, „Phase B — Aufteilung in Teilaufgaben"):

1. **Parser-Registry**: ein Modul je Lieferanten-Layout (`app/services/parsers/`)
   mit gemeinsamer Schnittstelle, automatische Lieferanten- und
   Dokumenttyp-Erkennung, unbekanntes Layout klar melden. ✅ abgeschlossen —
   siehe `docs/architektur.md`, Abschnitt „PDF-Parsing".
2. Belegnummer nur **je Lieferant** eindeutig (`UNIQUE (lieferant_id,
   dokumentnummer)`) inkl. Duplikatsprüfung im Importer. ✅ abgeschlossen —
   Migration `e5f6a7b8c9d0`.
3. **EAN wirklich optional** (Regel 5) auch in Parser/Korrekturen.
   ✅ abgeschlossen — fehlende EAN ist ein Hinweis (sperrt den Import nicht),
   eine unleserliche EAN bleibt eine Warnung.
4. **Lagerort aus der Lieferadresse** erkennen und beim Upload vorschlagen.
   ✅ abgeschlossen — Vorschlag (D19), änderbar; ein Beleg = ein Lagerort (D20);
   buchbar sind alle Lagerorte (D26).
5. **Erwartet → eingetroffen** (Regel 3, D6): Auftragsbestätigung/Bestellung
   erzeugen nur einen erwarteten Wareneingang; auch Mitarbeiter dürfen die
   Ankunft bestätigen (D21), Restmengen bleiben offen (D22).
   ✅ abgeschlossen — Seite `/wareneingaenge`, Migration `f6a7b8c9d0e1`.
6. **Manuelle Erfassung** mit Scanner (Z2), auch als Weg für unbekannte Layouts.
   Pflicht sind nur Marke + Bezeichnung + Menge + UVP (D23); es entsteht **kein
   Beleg** — direkter Wareneingang (D27). ✅ abgeschlossen — Seite `/erfassen`,
   Migration `a7b8c9d0e1f2`; erfassen dürfen auch Mitarbeiter (Regel 9/D21).
7. **EAN nachtragen/generieren** (interne EAN-13, GS1 20–29) + Etikett als PDF.
   ✅ abgeschlossen — auf Knopfdruck (D24), Etikett mit Jahrgang, Lieferant,
   UVP, Reduktionsstufe und Strichcode (D25); Etikettengrösse einstellbar
   (Voreinstellung 50 × 30 mm, echte Rollengrösse noch offen).
8. **Kategorie von Hand wählen**, wenn der FEDAS-Code fehlt oder unbekannt ist.
   ✅ abgeschlossen — Artikelseite, Erfassung und Filter „Ohne Kategorie" in der
   Artikelsuche, Migration `c9d0e1f2a3b4`; eine Wahl von Hand überschreibt kein
   Import mehr (`artikel.kategorie_manuell`).

Phase B ist damit vollständig abgeschlossen. Nächste Phase gemäss Roadmap
(`docs/projekt-kontext.md` Abschnitt 9): **C — Lagerbestand**.

## Abgeschlossen: Phase C — Lagerbestand

Teilaufgaben und Begründung der Reihenfolge: `docs/projekt-kontext.md`
Abschnitt 11, „Phase C — Lagerbestand, Aufteilung in Teilaufgaben". Kurz:

1. **Warnung bei Mehrlieferung** — mehr eingetroffen als erwartet: warnen, trotzdem buchen. ✅ abgeschlossen
2. **Bestandsansicht je Lagerort** — alle Filialen lesbar, externe Standorte separat sichtbar. ✅ abgeschlossen
3. **Ausbuchen per Scan** — Verkauf/Abgang von Hand; reicht der Bestand nicht: warnen, trotzdem buchen. ✅ abgeschlossen (ein Scan = ein Stück)
4. **Umlagerung** — extern → Filiale setzt das Eingangsdatum (D13), Filiale → Filiale behält es und startet die Reduktionsuhr der Zielfiliale nicht neu; hatte die Zielfiliale die Artikelnummer nie, startet die Uhr ab Eintreffen (F11). ✅ abgeschlossen
5. **Korrekturen** — Differenz mit Grund buchen. ✅ abgeschlossen (gezählte Menge eingeben, System bucht die Differenz)

Phase C ist damit vollständig abgeschlossen (23.09.2026). Vorübergehend hat die
Bestandsansicht einen Test-Knopf „−1"; er wird entfernt, sobald das Ausbuchen
im Laden erprobt ist. Nächste Phase gemäss Roadmap: **D — Preise & Reduktion**.

Jede Buchung bleibt eine Zeile in `lagerbewegungen` (Regel 2) und läuft über
dieselbe Sperre wie der Zugang.

Laufend offen bleibt der FEDAS-Kategorievorschlag selbst: `app/core/fedas.py`
kennt nur die aus echten Rechnungen bestätigten Codes (6 von 11 Sportbereichen
fehlen, ebenso die Produktart-Ziffern für Velo/Food). Bis sie bestätigt sind,
wird in diesen Fällen von Hand gewählt — die Kategorie bleibt also nie
zwangsläufig leer.
