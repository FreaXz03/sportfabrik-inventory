# Sportfabrik Inventory — Arbeitsregeln

## Einstieg und gezieltes Lesen

- Für Projektarbeit zuerst nur `docs/start.md` lesen (kurze Orientierung). Nicht pauschal Projektkontext, Architektur, Vault oder Historie vollständig laden.
- Bekannte Datei/konkreter Fehler: direkt die relevante Stelle lesen. Unbekannte Zusammenhänge: `python3 scripts/projektwissen.py query "<Begriff>"` (begrenzte Graphify-Abfrage über Code und Dokumentabschnitte).
- Anschliessend nur passende Originalabschnitte und betroffene Quelldateien prüfen. Der Dokumentindex zeigt Fundstellen, er ersetzt keine fachlichen Regeln.
- Bei fehlendem/veraltetem Graph oder leerem Treffer einmal gezielt mit `rg` suchen; keine wiederholten Vollscans oder automatischen KI-Neuaufbauten.
- Graph und Statusnotizen sind Orientierung. Technische Tatsachen am aktuellen Code prüfen; für Soll-Verhalten gelten die neuesten ausdrücklichen Entscheidungen. Widersprüche benennen.
- Aktuellen Branch und offene Änderungen vor Edits prüfen; fremde Änderungen erhalten.

## Harte Regeln

1. **Belegdaten bleiben lokal — sonst ist KI erlaubt.** Rechnungen, Lieferscheine und Auftragsbestätigungen werden von **eigenen Parsern** gelesen, die vollständig auf dem Server laufen (PyMuPDF, Tesseract, OpenCV o. ä.): kein Sprachmodell, kein Cloud-Dienst bekommt Belegdaten zu sehen, und ein unbekanntes Layout wird gemeldet statt geraten. Das gilt für den **Betrieb**. Für den **Parserbau** darf Fabian einzelne Belege bewusst zeigen (Entscheid 22.09.2026) — der Inhalt geht damit an den Modellanbieter, dient nur diesem Zweck und wird nirgends veröffentlicht. Belege massenhaft oder unbemerkt einlesen bleibt verboten (siehe Graphify). Ausserhalb der Belegverarbeitung ist KI zulässig, auch extern. Entwicklungswerkzeuge nach demselben Kriterium: Graphify darf Code und ausdrücklich ausgewählte Projektdokumentation analysieren; `--code-only` ist optional. Keine automatische Analyse von Belegen, Uploads, Zugangsdaten oder persönlichen Vault-Bereichen. Auswahl und Verfahren: `docs/obsidian-graphify.md`. Unabhängig von KI bleibt das Frontend **ohne externe CDNs** — es muss im Ladennetz ohne Internet laufen.
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
9. **Rechte (24.09.2026):** Mitarbeiter dürfen manuell einbuchen und Bestände korrigieren, jedoch nur in ihren zugewiesenen Filialen. Verkauf/Abgang ausbuchen, Stornieren und Umlagern sind Filialleitern und Zentrale vorbehalten. Deren bisherige filialübergreifende Buchungsrechte bleiben erhalten; Leserechte bleiben unverändert. Dokumente hochladen/bearbeiten/löschen bleibt Filialleitern/Zentrale vorbehalten. „Ware eingetroffen“ bestätigen bleibt erlaubt (D21).
10. **Einkaufspreis (EK)** optional speichern, wenn im Dokument vorhanden — nie Pflicht.


## Entwicklung und Prüfung

- Python/FastAPI, SQLAlchemy, PostgreSQL, Jinja und Vanilla JS/CSS; bestehende Struktur und Parser weiterverwenden. Schemaänderungen über Alembic; vorhandene Daten erhalten. Mengen/Geld als Numeric, serverseitig validieren.
- Oberfläche einfach und gut lesbar, für Scanner und Mitarbeitende mit wenig PC-Erfahrung. Details nur bei Bedarf aus den Anforderungskatalogen laden.
- Neue Geschäftslogik: zuerst einen aussagekräftigen fehlschlagenden Test, dann Umsetzung. Wenige Ablauf-Tests; Einzeltests für harte Regeln. Keine Tests für reine Textänderungen.
- Vor Code-Commits: `DATABASE_URL=sqlite:// .venv/bin/pytest -q`. Bei reiner Doku-/Werkzeugpflege passende gezielte Prüfungen; kein unnötiger Anwendungstestlauf. PostgreSQL-/Produktivprüfung separat ausweisen.
- Belege bleiben ausserhalb des öffentlichen Repos. Parser-Tests mit Belegen nur über explizite lokale Pfade/Umgebungsvariablen.
- Auf Arbeitsbranch `feature/warenwirtschaft-v2` arbeiten, nicht direkt auf main. Kleine nachvollziehbare Commits; kein Push ohne Auftrag.
- Fragen zu fachlich offenen Filialabläufen nicht erfinden. Sicherheitsstatus: `docs/sicherheit.md`; vor Ladeneinsatz offene Pflichtmassnahmen prüfen.

## Wissen aktuell halten, Kontext klein halten

- `docs/start.md`: kurze aktuelle Orientierung und nächste Priorität. Bei einem abgeschlossenen Meilenstein aktualisieren; kein fortlaufendes Protokoll anhängen.
- `docs/projekt-kontext.md`: fachliche Entscheidungen und detaillierter Umsetzungsverlauf. Architektur, Datenmodell und API nur bei entsprechenden Änderungen nachführen.
- Vault: Ideen und ursprüngliche Anforderungen; Status und technische Details verlinken statt dieselben Absätze in mehreren Notizen zu kopieren. Bei Dokuänderungen die beiden Sportfabrik-HTML-Übersichten im Vault auf betroffene Inhalte prüfen.
- Automatischer Codegraph-Hook bleibt lokal und ohne KI. Der Dokumentabschnittsindex wird bei jeder Abfrage lokal erneuert. Semantische Dokumentanalyse ist optional, nur für die explizite Auswahl; kein kompletter Vault-Scan. Details: `docs/obsidian-graphify.md`.
- Nach abgeschlossener Aufgabe Ergebnis, offene Punkte und betroffene Dateien kurz festhalten. Bei unabhängigem Aufgabenwechsel neue Sitzung empfehlen; laufende Arbeit nicht selbst abbrechen. Lange Sitzungen bei Bedarf mit kompakter Übergabe verdichten.
- Keine routinemässigen Graph-/Obsidian-Exporte oder parallelen Agenten pro Kleinigkeit. Export nur wenn die Ansicht gebraucht wird; Modellwahl und Sitzungen nicht ungefragt ändern.
