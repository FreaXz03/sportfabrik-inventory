# Sportfabrik Inventory — Einstieg

Stand: 25.09.2026. Diese Übersicht ist Orientierung, keine Bestätigung eines Produktivdeployments.

## Ziel und aktueller Schwerpunkt

Warenwirtschaft für vier Sportfabrik-Filialen; GEWA, VEBO und Dietikon sind externe Lagerorte ohne Verkauf. Belege werden im Betrieb lokal geparst. Artikelstamm gemeinsam, Bestand und Buchungsrechte filialbezogen. Später Kassenanbindung und Onlineshop.

Phasen A–C sind laut Projektdokumentation abgeschlossen. Phase D ist teilweise umgesetzt (Runterschreiben und manuelle Reduktionen), nicht abgeschlossen. Der Katalog **Artikeldetails und Auswertungen** (alle 17 Punkte) ist am 25.09.2026 umgesetzt, nur lokal geprüft (kein PostgreSQL-Durchgang, kein Ladeneinsatz). Nächster Schwerpunkt: restliche Phase D (offene Fragen D-F1 bis D-F4, Abschnitt 10) oder Ladeneinsatz vorbereiten (`docs/sicherheit.md`). Vor Umsetzung den aktuellen Code und das Ende von Abschnitt 11 im Projektkontext abgleichen. Handynutzung folgt am Projektende.

Arbeitsbranch: `feature/warenwirtschaft-v2`; tatsächlichen Branch und offene Änderungen prüfen. Dokumentierte lokale Tests sind keine Aussage über PostgreSQL oder den laufenden Ladenserver.

## Nur die zur Aufgabe passende Quelle öffnen

| Frage | Hauptquelle |
|---|---|
| Aktuelle Anforderungen, Punkte 1–17 | `docs/anforderungen-artikeldetails-auswertungen-2026-09-24.md`; Umsetzungsnachtrag am Ende von `docs/projekt-kontext.md` |
| Fachliche Entscheidungen, Roadmap, offene Fragen | `docs/projekt-kontext.md`, Abschnitte 4, 9, 10; neuesten datierten Nachtrag beachten |
| Umsetzung und historische Meilensteine | `docs/projekt-kontext.md`, Abschnitt 11 und Nachträge; aktuellen Code gegenprüfen |
| Architektur und Abläufe | passender Abschnitt von `docs/architektur.md` |
| Tabellen, Migrationen, API | `docs/datenmodell.md`, `docs/api-referenz.md` und betroffene Quelldateien |
| Sicherheit / Ladeneinsatz | `docs/sicherheit.md`, bei Deployment `docs/SERVER-SETUP.md` |
| Ursprüngliche Bedienungswünsche / Etiketten | `docs/anforderungen-inbox-2026-09-23.md`, `docs/anforderungen-inbox-2026-09-24.md` |
| Graphify, Auswahl, lokale Suche | `docs/obsidian-graphify.md` |

Unbekannte Zusammenhänge: `python3 scripts/projektwissen.py query "Umlagerung"` oder `"reduktionen_manuell"`. Liefert Codebeziehungen und Dokumentfundstellen mit begrenzter Ausgabe. Danach gezielt Originalstellen lesen, nicht den gesamten Graphen.

Der Main-Vault bewahrt Ideen und Anforderungen; der generierte Sportfabrik-Graph ist eine optionale Ansicht. Historische Statusnotizen sind keine zusätzliche aktuelle Quelle. Cloud-Sessions ohne lokalen Graph suchen gezielt in den Originaldateien.
