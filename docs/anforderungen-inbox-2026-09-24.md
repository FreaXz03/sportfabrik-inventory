# Inbox-Ergänzungen vom 24.09.2026

Status: Dokumentationsabgleich; keine Code-, Parser- oder Teständerung.

## Etiketten – aktuelle Vorgabe

Fabians neueste ausdrückliche Angabe: **Breite 47 mm, Höhe 83 mm** (Hochformat). Dies ersetzt die bisherige Zielangabe 84 × 47 mm. Die dokumentierte bisherige Code-Voreinstellung ist dadurch nicht automatisch geändert.

Drei wechselbare Rollen sind bereits vorgedruckt: 30 % mit gelbem Punkt, 50 % mit rotem Punkt, 70 % mit grünem Punkt. Der Scan zeigt eine leere 30%-Vorlage und zwei bedruckte Beispiele: durchgestrichener Preis 333.00 / Lieferant 111 / Jahrgang 25 sowie 499.00 / Lieferant 999 / Jahrgang 27. Drucklayout auf vorgedruckte Elemente abstimmen; Barcodeposition und Druckausrichtung am Muster klären.

Lokale Quelle im Obsidian-Vault Main: `03 Ressourcen/Sportfabrik Inventory – Etikettenbeispiele.md`.

## FEDAS-Quelle

Fabian hat die deutsche Übersicht nachgereicht: http://download.fedas.com/actualversion/download/pdf/ger_pdf_overview.pdf . Er bezeichnet sie als Liste mit allen Codes. Abruf am 24.09.2026 fehlgeschlagen (HTTP 502); Version, Vollständigkeit und konkrete Codes noch nicht geprüft. Die bisherige Aussage, dass keine Liste bekannt sei, ist damit überholt; der geprüfte Import und die Zuordnung zu Kassenkategorien bleiben offen. Keine ungeprüften Codes übernehmen.

Lokale Quelle: `03 Ressourcen/Sportfabrik Inventory – FEDAS-Liste.md`.

## Alpina-Papierscan

Zusätzliches lokales Parserbeispiel: Lieferschein 119719, Versanddatum 01.09.2026, Auftrag 151850, SF1 Volketswil, eine Seite, vier Positionen, 29 Stück, offene Menge 0. JPEG-Scan mit EAN-Barcodes, UVP, Mengen und handschriftlicher Markierung. Keine Bestandsbuchung oder Parserimplementierung durch diesen Abgleich.

Lokale Quelle: `03 Ressourcen/Sportfabrik Inventory – Alpina-Lieferschein 119719.md`. Scan bleibt im lokalen Vault und wird nicht in das öffentliche Repository kopiert.

## Testbereinigung – gewünschte Arbeit

Fabians Wunsch: alle Tests aufräumen, nur wichtigste Tests behalten, weniger wichtige Grundfeature-Tests zur Löschung prüfen und grosse aktuelle Hauptfeature-Tests bauen. Ziel: geringerer Tokenverbrauch. Auswahl und Umfang noch offen; keine pauschale Testlöschung und keine Behauptung, dies sei bereits umgesetzt. Die Projektregel zum grünen Testlauf vor Commits bleibt bestehen.

Lokale Quelle: `01 Projekte/Sportfabrik Inventory/Sportfabrik Inventory Tests aufräumen.md`.
