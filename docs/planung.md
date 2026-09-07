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
| F5 | Artikelsuche über Marke, EAN, Artikelnummer, Bezeichnung, Farbe, Grösse, Lieferdatum-Bereich | `app/routers/catalog.py` |
| F6 | Vollständige Lieferhistorie je Artikel(-Variantengruppe) und je Rechnung, inkl. Original-Rechnungstext | `app/routers/history.py`, `InvoiceItemSource`, `app/services/article_groups.py` |
| F7 | Rechnung nachträglich vollständig löschen können, mit korrekter Neuberechnung betroffener Artikeldaten | `delete_invoice()` in `app/services/importer.py` |
| F8 | Gleichzeitiger Zugriff von vier Laden-PCs, ohne inkonsistente Daten bei zeitgleichem Import | Advisory Lock (`pg_advisory_xact_lock`) |
| F9 | Anmeldung analog zum bestehenden Kassensystem: Mitarbeiter nur mit Kassennummer, Filialleiter zusätzlich mit Passwort | `app/routers/auth.py` |
| F10 | Nur Filialleiter dürfen Rechnungen hochladen, importieren und löschen; Mitarbeiter dürfen nur ansehen/suchen | RBAC-Dependencies (`require_chef_*` / `require_login_*`) |
| F11 | Nachvollziehbar, welche Person (Kassennummer/Name) eine Rechnung importiert hat | `imported_by_kassennummer`/`imported_by_name` auf `Invoice` |
| F12 | Betrieb auf einem Linux-Server im Geschäft, Zugriff über das lokale Netz | Docker/Compose, `SERVER-SETUP.md` |
| F13 | Eingescannte Papierrechnungen ohne digitale Textebene (Ausnahmefall: Rechnung liegt nur auf Papier im Paket, kein Mail-PDF) per OCR lesbar machen | `app/services/ocr.py`, `parser.page_content()` |
| F14 | Erkannte Positionen vor dem Import direkt in der Vorschau korrigieren können, statt die ganze Rechnung abzulehnen | `app/services/corrections.py`, `/validate-preview` |
| F15 | Mehrere Rechnungen nacheinander hochladen und importieren, ohne nach jeder Datei neu zu starten | `app/static/js/preview.js` (Warteschlange), `/invoice-import-status` |
| F16 | Freitext-Notizen je Artikel(-Gruppe) hinterlegen (z. B. Verkaufsbeobachtungen), mit Autor und Änderungsverlauf | `ArticleNote`-Modell, `app/routers/article_details.py` |
| F17 | Preisverlauf (UVP über Zeit) je Artikel(-Gruppe) einsehen | `/api/articles/{id}/prices` |
| F18 | Farb-/Grössenvarianten desselben Artikels in Historie/Notizen/Preisverlauf gemeinsam statt einzeln anzeigen | `app/services/article_groups.py` |
| F19 | Gefilterte Artikelliste als Excel-Datei exportieren (z. B. für Bestelllisten) | `app/services/article_export.py`, `/api/articles/export` |
| F20 | Rechnungs- und Artikelhistorie-Tabellen nach beliebiger Spalte sortieren können | `sort_by`/`sort_dir` in `app/routers/history.py` und `app/routers/catalog.py` |
| F21 | Oberfläche für Mitarbeitende mit eingeschränktem Sehvermögen vereinfachen (Spalten ein-/ausblenden, grössere Schrift) und seitenübergreifend Hell-/Dunkelmodus anbieten | `app/static/js/theme.js`, Spalten-Auswahl in `articles.html` |
| F22 | Regelmässige, geprüfte Backups von Datenbank und Original-PDFs | `scripts/backup_inventory.py`, `docs/BACKUPS.md` |

F9–F11 und F13 wurden erst nachträglich in der ersten Projektanalyse-Session
ergänzt; F1–F8 und F12 waren zu diesem Zeitpunkt bereits umgesetzt. F14–F22
wurden in einer zweiten, umfangreichen Ausbaustufe danach ergänzt (siehe
Entwicklungsphasen).

## Nicht-funktionale Anforderungen (rekonstruiert)

- **Sprache/Zielgruppe**: Durchgängig deutsche Oberfläche und Fehlermeldungen; Zielgruppe ist Ladenpersonal ohne IT-Hintergrund, inkl. Mitarbeitenden mit eingeschränktem Sehvermögen (siehe F21).
- **Robustheit vor Bequemlichkeit**: Bei Unklarheiten (unbekanntes Layout, fehlende Pflichtfelder, uneindeutige Farbe/Grösse) wird die Zeile mit Warnung markiert statt geraten — Korrekturen sind möglich (F14), aber immer explizit und serverseitig nachgeprüft.
- **Keine stille Datenkorruption**: Hash-Prüfung zwischen Vorschau und Import, Transaktionen mit Rollback bei Fehlern, Advisory Lock gegen Race Conditions, optimistisches Sperren bei Notizen (Version-Konflikt statt stillem Überschreiben).
- **Unabhängig vom Internet**: Kein Frontend-Framework, keine Build-Pipeline, keine externen Skript-Abhängigkeiten im Browser — muss im Ladennetz ohne Internetzugriff funktionieren.
- **Nachvollziehbarkeit**: Audit-Trail auf Positionsebene (`InvoiceItemSource`, inkl. `correction_audit`) bleibt auch erhalten, wenn sich Artikel-Stammdaten später ändern.
- **Erweiterbarkeit**: Architektur soll weitere Lieferanten-Layouts und Endpunkte aufnehmen können, ohne unübersichtlich zu werden (siehe Ordnerstruktur in `docs/architektur.md`).

## Bewusst ausserhalb des Umfangs (Stand heute)

- Weitere Lieferanten-Layouts ausser INTERSPORT (zurückgestellt, bis eine Beispielrechnung eines weiteren Lieferanten vorliegt).
- Echte Lagerbestandsführung — die App zeigt gelieferte Mengen, keinen aktuellen Lagerbestand.
- Admin-Oberfläche für Benutzerverwaltung (bewusst als einfaches CLI-Skript umgesetzt, siehe Entscheidung E10).
- Externer Backup-Speicherort (Backup-Automatisierung selbst ist umgesetzt, siehe F22 und `docs/BACKUPS.md`; eine Kopie ausserhalb des PCs steht noch aus).

## Entwicklungsphasen (Zeitleiste)

| Phase | Zeitpunkt | Inhalt |
|---|---|---|
| 0 | vor der ersten Projektanalyse (genaues Datum nicht dokumentiert, da noch kein Git-Repository bestand) | Kernentwicklung durch Fabian: FastAPI-Backend, PostgreSQL-Datenmodell, PDF-Parser für das INTERSPORT-Layout, zweistufiger Upload-/Import-Workflow, durchsuchbarer Artikelkatalog mit Lieferhistorie, Docker-/Server-Vorbereitung, Testsuite (29 Tests) |
| 1 | 2026-09-06, 12:33 | Projektanalyse; Git-Repository eingerichtet, erster Commit, öffentliches GitHub-Repo (`github.com/FreaXz03/sportfabrik-inventory`), SSH-Zugang eingerichtet |
| 2 | 2026-09-06, 12:57 | Alembic-Datenbankmigrationen eingeführt (statt `Base.metadata.create_all()`); Entwicklungs-Endpunkt `/upload-test` entfernt; ungenutzte, leere `navigation.js` aufgeräumt |
| 3 | 2026-09-06, 13:28 | Anmeldung und rollenbasierte Zugriffsrechte umgesetzt (Kassensystem-Muster); Benutzerverwaltung per CLI-Skript (`scripts/manage_users.py`) |
| 4 | 2026-09-06, 13:59 | UI-Korrekturen: defekter „Zurücksetzen"-Knopf repariert (ID-Namenskollision mit `HTMLFormElement.reset`), Upload-Hinweis für Mitarbeiter ausgeblendet, Nachvollziehbarkeit ergänzt (wer hat eine Rechnung importiert) |
| 5 | 2026-09-06, 14:13 | Ordnerstruktur aufgeräumt (`app/` in `core/`, `routers/`, `services/` gegliedert; `static/` nach Dateityp sortiert); `README.md` ergänzt |
| 6 | 2026-09-06, 15:20 | Erste Gesamtdokumentation (`planung.md`, `architektur.md`, `datenmodell.md`, `api-referenz.md`, sowie ein zusammengefasstes Word-Dokument) |
| 7 | 2026-09-06, 16:15 | OCR-Fallback für eingescannte Papierrechnungen ohne Textebene (`app/services/ocr.py`), inkl. Testabdeckung (`tests/test_ocr.py`) und Migration für `Invoice.ocr_used`; danach zwei reale Parsing-Bugs anhand einer echten gescannten Beispielrechnung behoben |
| 8 | 2026-09-06, 17:30–19:56 | UI-Politur in mehreren Runden: sortierbare Artikelsuche, breiteres Layout, Seitengrösse 100, Spalten-Auswahl + grössere Schrift für Mitarbeitende mit eingeschränktem Sehvermögen (F21), „Chef" in der Oberfläche zu „Filialleiter" umbenannt, Login-Seite korrigiert, seitenübergreifender Dark Mode mit Einstellungen-Menü; danach Login-Redirect gegen offene Weiterleitungen abgesichert, `migrations/env.py` robuster gegen Sonderzeichen im Passwort gemacht, automatisierte, geprüfte Backups eingerichtet (F22, `scripts/backup_inventory.py`, `docs/BACKUPS.md`) |
| 9 | danach | Grössere fachliche Erweiterung: Korrekturen direkt in der Vorschau (F14), Stapel-Import mehrerer Rechnungen (F15), Preisverlauf und Freitext-Notizen je Artikel (F16/F17), Excel-Export der Artikelliste (F19) |
| 10 | danach | Artikel-Varianten (gleiche Marke + Lieferanten-Artikelnummer) für Historie/Notizen/Preisverlauf gruppiert (F18), Spaltenauswahl in der Artikelhistorie vereinfacht |
| 11 | danach | Weitere Politur an Übersicht, Rechnungs-/Artikelhistorie (Sortierung, F20) und dem Stapel-Import-Ablauf |

Phasen 9–11 wurden grösstenteils unabhängig von den UI-Politur-Sessions
(Phase 8) parallel erarbeitet; die genauen Zeitstempel dieser Commits liegen
nicht vor, die Reihenfolge ergibt sich aus der Commit-Historie
(`df99ebc`, `b15774d`, `94e5085`).

## Zentrale Entscheidungen (mit Begründung)

**E1 — Kassennummer-Login statt klassischem Benutzerkonto für alle.**
Mitarbeiter melden sich nur mit ihrer Kassennummer an (kein Passwort),
Filialleiter zusätzlich mit Passwort. Begründung: entspricht dem bestehenden
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
`Invoice.imported_by_kassennummer`/`imported_by_name` und
`ArticleNote.author_name`/`author_number` speichern eine Momentaufnahme
statt (nur) eines Fremdschlüssels. Begründung: historische Korrektheit
bleibt erhalten, selbst wenn sich Artikel-Stammdaten später ändern oder ein
Benutzerkonto gelöscht wird.

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
weitere Endpunkte), klare Verantwortlichkeiten statt vieler gleichrangiger
Dateien auf einer Ebene.

**E10 — Einfaches CLI-Skript statt Admin-Oberfläche für Benutzerverwaltung.**
Begründung: Benutzerkonten ändern sich selten (neue Mitarbeiter, neue
Filialleiter); eine eigene Weboberfläche dafür stünde in keinem Verhältnis
zum Nutzen bei vier PCs und einer Handvoll Konten.

**E11 — OCR-Fallback statt eigenem Bild-Parser für gescannte Rechnungen.**
Fehlt einer PDF-Seite jede Textebene (Papierrechnung eingescannt statt
digital per Mail erhalten), rendert `app/services/ocr.py` die Seite und
liest sie per Tesseract OCR; die erkannten Wörter werden exakt wie
PyMuPDF-Wortkoordinaten aufbereitet, sodass die bestehende
Tabellenerkennung in `parser.py` unverändert weiterverwendet werden kann.
Begründung: eine eigene, parallele Bild-Parsing-Logik hätte dieselbe
Spaltenerkennung ein zweites Mal, fehleranfällig, nachbauen müssen. OCR
ist grundsätzlich weniger zuverlässig als eine native Textebene; Positionen
und Rechnungen aus OCR werden deshalb explizit markiert (`ocr_used`) und
in der Vorschau mit einem Hinweis zur besonders sorgfältigen Prüfung
versehen — der Import bleibt aber möglich, solange keine echten
Datenprobleme vorliegen (OCR-Nutzung allein blockiert den Import nicht).

**E12 — Korrekturen serverseitig neu validieren statt Client-Werten zu vertrauen.**
`apply_corrections()` nimmt nie ungeprüft an, was der Browser schickt: jede
korrigierte Position durchläuft dieselbe Validierung wie eine frisch
geparste. Begründung: eine falsch korrigierte Position (z. B. eine ungültige
EAN) darf nicht versehentlich zu einer schlechteren Datenqualität führen als
eine unkorrigierte Warnung.

**E13 — Artikel-Varianten über Marke + Lieferanten-Artikelnummer gruppieren, nicht per eigener Gruppentabelle.**
`app/services/article_groups.py` berechnet die Zusammengehörigkeit von
Farb-/Grössenvarianten bei jeder Abfrage neu, statt eine feste
Gruppen-Fremdschlüssel-Beziehung in der Datenbank zu pflegen. Begründung:
Lieferanten-Artikelnummer und Marke sind bereits vorhandene, verlässliche
Felder; eine zusätzliche Tabelle müsste bei jeder Korrektur dieser Felder
nachgepflegt werden und könnte veralten.

**E14 — Optimistisches Sperren (Versionsfeld) statt Locking bei Notizen.**
Begründung: Notizen werden selten gleichzeitig von zwei Personen bearbeitet;
ein Versions-Konflikt (HTTP 409) mit der Bitte, neu zu laden, ist einfacher
und für dieses Nutzungsmuster ausreichend robust, ohne eine dauerhafte
Sperre verwalten zu müssen.

**E15 — Stapel-Import als reine Frontend-Warteschlange statt Server-Batch-Endpunkt.**
Begründung: Server-seitig ändert sich am Import nichts (jede Datei bleibt
für sich atomar und geprüft); eine serverseitige Batch-API hätte dieselbe
Logik ein zweites Mal abbilden müssen, ohne echten Mehrwert gegenüber
mehreren Einzel-Importen, die der Browser automatisch nacheinander anstösst.

**E16 — Login-Redirect-Ziel gegen eine feste Whitelist statt beliebiger URLs.**
Begründung: `next` kommt aus der URL und ist damit potenziell manipulierbar;
eine Whitelist bekannter, ungefährlicher Zielrouten schliesst offene
Redirects zuverlässig aus, ohne die Komfortfunktion (nach Login zur
ursprünglich angeforderten Seite zurückkehren) einzuschränken.

## Offene Punkte

- Externer Backup-Speicherort ausserhalb des PCs — Backup-Erstellung und -Prüfung selbst sind bereits automatisiert (siehe `docs/BACKUPS.md`).
- Zweites Lieferanten-Layout, sobald eine Beispielrechnung vorliegt.
- Neues, langes Passwort für `.env.server` (nicht das lokale Windows-Passwort wiederverwenden).
- Docker-Build und Datenumzug auf den Linux-Server im Geschäft (Testlauf lokal via `docker compose --env-file .env.server up -d --build` bereits möglich; produktiver Umzug steht noch aus).
