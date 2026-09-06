# Anforderungen & Planung (rückwirkend rekonstruiert)

Dieses Dokument beschreibt Auftrag, Anforderungen, Entwicklungsphasen und
zentrale Entscheidungen des Sport-Fabrik Inventory Systems. Es wurde
**rückwirkend** erstellt: Ein grosser Teil der App existierte bereits, bevor
ein Git-Repository oder eine formale Anforderungsliste angelegt wurde. Die
folgenden Anforderungen sind deshalb aus dem ursprünglichen, informellen
Auftrag und aus der tatsächlich gebauten Lösung rekonstruiert — nicht aus
einem vorab existierenden Lastenheft.

## Ausgangslage

Ursprünglicher Auftrag (sinngemäss, wie zu Beginn formuliert):

> Ein Inventory-System für die Sport-Fabrik (Kleiderladen). Eine Seite, auf
> der man Rechnungen hochladen und verwalten sowie alle Artikel darin
> extrahieren und in eine PostgreSQL-Datenbank speichern kann. Das Ganze
> soll danach auf einem Linux-Server im Geschäft laufen, vier PCs sollen
> darauf Zugriff haben.

Der Laden führt Ski-, Bike-, Wander-, Lauf- und Tennisausrüstung; Lieferungen
kommen aktuell primär von INTERSPORT Schweiz AG per PDF-Rechnung.

## Funktionale Anforderungen (rekonstruiert)

| # | Anforderung | Umgesetzt in |
|---|---|---|
| F1 | PDF-Rechnungen hochladen und Positionen automatisch auslesen | `app/services/parser.py` |
| F2 | Vorschau der erkannten Positionen vor dem Speichern; nichts wird ungeprüft übernommen | `app/routers/preview.py` (`/upload-preview`) |
| F3 | Import erst nach expliziter Bestätigung, und nur exakt der geprüften Datei | `app/routers/preview.py` (`/import-invoice`), Hash-Abgleich |
| F4 | Zentrale Artikeldatenbank; mehrfach gelieferte Artikel (gleiche EAN) zusammenführen statt duplizieren | `app/services/importer.py`, `Product`-Modell |
| F5 | Artikelsuche über Marke, EAN, Artikelnummer, Bezeichnung, Farbe, Grösse | `app/routers/catalog.py` |
| F6 | Vollständige Lieferhistorie je Artikel und je Rechnung, inkl. Original-Rechnungstext | `app/routers/history.py`, `InvoiceItemSource` |
| F7 | Rechnung nachträglich vollständig löschen können, mit korrekter Neuberechnung betroffener Artikeldaten | `delete_invoice()` in `app/services/importer.py` |
| F8 | Gleichzeitiger Zugriff von vier Laden-PCs, ohne inkonsistente Daten bei zeitgleichem Import | Advisory Lock (`pg_advisory_xact_lock`) |
| F9 | Anmeldung analog zum bestehenden Kassensystem: Mitarbeiter nur mit Kassennummer, Chefs zusätzlich mit Passwort | `app/routers/auth.py` |
| F10 | Nur Chefs dürfen Rechnungen hochladen, importieren und löschen; Mitarbeiter dürfen nur ansehen/suchen | RBAC-Dependencies (`require_chef_*` / `require_login_*`) |
| F11 | Nachvollziehbar, welche Person (Kassennummer/Name) eine Rechnung importiert hat | `imported_by_kassennummer`/`imported_by_name` auf `Invoice` |
| F12 | Betrieb auf einem Linux-Server im Geschäft, Zugriff über das lokale Netz | Docker/Compose, `SERVER-SETUP.md` |

F9–F11 wurden erst nachträglich in dieser Session ergänzt; F1–F8 und F12
waren zu Beginn der Session bereits umgesetzt.

## Nicht-funktionale Anforderungen (rekonstruiert)

- **Sprache/Zielgruppe**: Durchgängig deutsche Oberfläche und Fehlermeldungen; Zielgruppe ist Ladenpersonal ohne IT-Hintergrund.
- **Robustheit vor Bequemlichkeit**: Bei Unklarheiten (unbekanntes Layout, fehlende Pflichtfelder, uneindeutige Farbe/Grösse) wird die Zeile mit Warnung markiert statt geraten.
- **Keine stille Datenkorruption**: Hash-Prüfung zwischen Vorschau und Import, Transaktionen mit Rollback bei Fehlern, Advisory Lock gegen Race Conditions.
- **Unabhängig vom Internet**: Kein Frontend-Framework, keine Build-Pipeline, keine externen Skript-Abhängigkeiten im Browser — muss im Ladennetz ohne Internetzugriff funktionieren.
- **Nachvollziehbarkeit**: Audit-Trail auf Positionsebene (`InvoiceItemSource`) bleibt auch erhalten, wenn sich Artikel-Stammdaten später ändern.
- **Erweiterbarkeit**: Architektur soll weitere Lieferanten-Layouts und Endpunkte aufnehmen können, ohne unübersichtlich zu werden (siehe Ordnerstruktur in `docs/architektur.md`).

## Bewusst ausserhalb des Umfangs (Stand heute)

- Automatisiertes Backup (nur als offener Punkt dokumentiert, siehe `SERVER-SETUP.md`).
- Weitere Lieferanten-Layouts ausser INTERSPORT (zurückgestellt, bis eine Beispielrechnung eines weiteren Lieferanten vorliegt).
- Echte Lagerbestandsführung — die App zeigt gelieferte Mengen, keinen aktuellen Lagerbestand.
- Admin-Oberfläche für Benutzerverwaltung (bewusst als einfaches CLI-Skript umgesetzt, siehe Entscheidung E1).

## Entwicklungsphasen (Zeitleiste)

| Phase | Zeitpunkt | Inhalt |
|---|---|---|
| 0 | vor dieser Session (genaues Datum nicht dokumentiert, da noch kein Git-Repository bestand) | Kernentwicklung durch Fabian: FastAPI-Backend, PostgreSQL-Datenmodell, PDF-Parser für das INTERSPORT-Layout, zweistufiger Upload-/Import-Workflow, durchsuchbarer Artikelkatalog mit Lieferhistorie, Docker-/Server-Vorbereitung, Testsuite (29 Tests) |
| 1 | 2026-09-06, 12:33 | Projektanalyse; Git-Repository eingerichtet, erster Commit, öffentliches GitHub-Repo (`github.com/FreaXz03/sportfabrik-inventory`), SSH-Zugang eingerichtet |
| 2 | 2026-09-06, 12:57 | Alembic-Datenbankmigrationen eingeführt (statt `Base.metadata.create_all()`); Entwicklungs-Endpunkt `/upload-test` entfernt; ungenutzte, leere `navigation.js` aufgeräumt |
| 3 | 2026-09-06, 13:28 | Anmeldung und rollenbasierte Zugriffsrechte umgesetzt (Kassensystem-Muster); Benutzerverwaltung per CLI-Skript (`scripts/manage_users.py`) |
| 4 | 2026-09-06, 13:59 | UI-Korrekturen: defekter „Zurücksetzen"-Knopf repariert (ID-Namenskollision mit `HTMLFormElement.reset`), Upload-Hinweis für Mitarbeiter ausgeblendet, Nachvollziehbarkeit ergänzt (wer hat eine Rechnung importiert) |
| 5 | 2026-09-06, 14:13 | Ordnerstruktur aufgeräumt (`app/` in `core/`, `routers/`, `services/` gegliedert; `static/` nach Dateityp sortiert); `README.md` ergänzt |
| 6 | 2026-09-06, laufend | Vorliegende Gesamtdokumentation (dieses Dokument, `architektur.md`, `datenmodell.md`, `api-referenz.md`, sowie ein zusammengefasstes Word-Dokument) |

## Zentrale Entscheidungen (mit Begründung)

**E1 — Kassennummer-Login statt klassischem Benutzerkonto für alle.**
Mitarbeiter melden sich nur mit ihrer Kassennummer an (kein Passwort), Chefs
zusätzlich mit Passwort. Begründung: entspricht dem bestehenden
Kassensystem im Laden, senkt die Hürde für Mitarbeiter im Alltag, während
sensible Aktionen (Hochladen, Löschen) zusätzlich abgesichert sind.

**E2 — Zweistufiger Upload/Import statt direktem Speichern.**
`/upload-preview` schreibt nichts in die Datenbank; erst `/import-invoice`
mit bestätigtem Hash speichert. Begründung: Der Parser kann Sonderfälle
(fehlende EAN, uneindeutige Farbe/Grösse, unbekanntes Layout) nicht immer
sicher automatisch auflösen — Fehler sollen vor dem Speichern aufgefallen,
nicht danach mühsam korrigiert werden.

**E3 — Hash-Abgleich zwischen Vorschau und Import.**
`/import-invoice` verlangt den SHA-256-Hash der zuvor geprüften Datei.
Begründung: verhindert, dass zwischen Prüfung und Bestätigung eine andere
Datei importiert wird als die tatsächlich kontrollierte.

**E4 — `pg_advisory_xact_lock` statt feingranularem Row-Locking.**
Import und Löschung serialisieren sich über eine PostgreSQL-Advisory-Lock.
Begründung: einfache, robuste Lösung für Mehrplatzbetrieb (vier PCs), ohne
ein komplexes Locking-Schema entwerfen zu müssen.

**E5 — Denormalisierte Audit-Felder statt reiner Fremdschlüssel-Verknüpfung.**
`InvoiceItemSource` speichert die Original-Positionsdaten dauerhaft;
`Invoice.imported_by_kassennummer`/`imported_by_name` speichern eine
Momentaufnahme statt eines Fremdschlüssels auf `users`. Begründung:
historische Korrektheit bleibt erhalten, selbst wenn sich Artikel-Stammdaten
später ändern oder ein Benutzerkonto gelöscht wird.

**E6 — Alembic-Migrationen statt weiterhin `create_all()`.**
Begründung: Schemaänderungen müssen nachvollziehbar, versioniert und auf
allen vier PCs reproduzierbar sein — reines `create_all()` bietet das nicht.

**E7 — Session-Cookie ohne automatisches Ablaufen.**
Begründung: entspricht dem Verhalten des bestehenden Kassensystems; niemand
muss sich im Ladenalltag ständig neu anmelden.

**E8 — Kein Frontend-Framework, keine Build-Pipeline.**
Begründung: muss auf einfachen Laden-PCs ohne Internetzugriff laufen; ein
Build-Schritt wäre zusätzliche, unnötige Komplexität für ein internes Tool
dieser Grösse.

**E9 — Ordnerstruktur `core/` / `routers/` / `services/` statt flacher Liste.**
Begründung: Vorbereitung auf Wachstum (z. B. weitere Lieferanten-Parser,
weitere Endpunkte), klare Verantwortlichkeiten statt elf gleichrangiger
Dateien auf einer Ebene.

**E10 — Einfaches CLI-Skript statt Admin-Oberfläche für Benutzerverwaltung.**
Begründung: Benutzerkonten ändern sich selten (neue Mitarbeiter, neue
Chefs); eine eigene Weboberfläche dafür stünde in keinem Verhältnis zum
Nutzen bei vier PCs und einer Handvoll Konten.

## Offene Punkte

- Backup-Strategie (automatisiertes `pg_dump`, externer Speicherort) — siehe `SERVER-SETUP.md`.
- Zweites Lieferanten-Layout, sobald eine Beispielrechnung vorliegt.
- Neues, langes Passwort für `.env.server` (nicht das lokale Windows-Passwort wiederverwenden).
- Docker-Build und Datenumzug auf den Linux-Server (Testlauf lokal noch ausstehend).
