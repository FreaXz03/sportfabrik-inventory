# Artikeldetails und Auswertungen – Inbox vom 24.09.2026

## Verbindliche Priorität – 24.09.2026

Fabian hat entschieden: **Zuerst die neuen Wünsche aus der Inbox umsetzen, danach Phase D weiterführen.** Die bereits gebaute Runterschreiben-Seite bleibt bestehen; Phase D wird dadurch weder zurückgesetzt noch als abgeschlossen markiert.

Vorrang hat der gesamte neue Anforderungskatalog „Artikeldetails und Auswertungen“: Artikeldetails aufräumen, Listen und Arbeitsabläufe vereinfachen, Übersicht und Schnellzugriffe personalisieren, Statistik und Kontoverwaltung ergänzen. Auch die ausdrücklich gewünschten manuellen Reduktionen (alle Mitarbeitenden je Filiale, 30/50/70 %, Auswahl per EAN oder Bestand, Anzeige in Artikeldetails und Bestand) gehören zu diesem vorgezogenen Paket, obwohl sie fachlich Phase D berühren.

Erst danach folgen die übrigen Arbeiten und offenen Entscheidungen von Phase D. Die Handynutzung bleibt wie vereinbart für das Projektende geplant. Erforderliche Prüfungen vor dem Ladeneinsatz bleiben bestehen. Dies ist eine Prioritätsentscheidung, keine Implementierungsbestätigung.

Anforderungskatalog: [Artikeldetails und Auswertungen](anforderungen-artikeldetails-auswertungen-2026-09-24.md).


Status: Anforderungen integriert; keine Codeänderung durch diesen Abgleich. Vorhandene offene Änderungen im Projekt stammen aus anderer Arbeit und bleiben unberührt.

## Anforderungen

1. **Artikeldetails:** Kassenkategorie erst über „Editieren“ neben dem Artikelnamen öffnen; Box standardmässig nicht anzeigen.
2. **Artikeldetails:** EAN und Etikett erst über einen kleinen Knopf ausführlich öffnen; Box standardmässig nicht anzeigen.
3. **Artikeldetails:** UVP-Verlauf zuoberst und kompakter anzeigen; zugehörige kleine Liste ausklappbar, anfangs geschlossen.
4. **Artikeldetails:** Artikelnotizen aus der Oberfläche entfernen. Über eine Löschung vorhandener Notizdaten ist damit nichts entschieden.
5. **Artikeldetails:** Untere Liste als aktuellen Bestand dieses Artikels mit allen Grössen und Farben darstellen.
6. **Artikeldetails:** „Artikel löschen“ samt rotem Hinweistext ganz unten anordnen; bestehende Löschrechte und Einschränkungen beibehalten.
7. **Reduktion:** Aktuelle Reduktionsempfehlung in den Artikeldetails anzeigen, manuelle Anpassung durch alle Mitarbeitenden je Filiale auf 30/50/70 % ermöglichen und im Bestand unmittelbar anzeigen.
8. **Aktuelles:** Lieferankünfte als ganze Lieferung zusammenfassen; Umlagerungen und Abgänge mit anderem Grund als Verkauf zeigen, nicht jeden einzelnen Zu-/Abgang.
9. **Statistik:** Neue Statistikseite nur für Filialleiter und Zentrale: verkaufte Mengen nach Kategorie, ausdrücklich als Schätzung ausgewiesene Einnahmen auf Basis des damaligen reduzierten Verkaufspreises und Hinweise auf gut laufende Artikel/Nachbestellbedarf; tägliche, wöchentliche, monatliche, jährliche und gesamte Ansicht, mit leicht verständlichen Diagrammen. Weitere Kennzahlen dürfen bei der Planung vorgeschlagen werden.
10. **Bestand:** Artikelnamen auf die jeweilige Artikeldetailseite verlinken.
11. **Bestand:** Reduktionsstufe in der Bestandsliste anzeigen; in der Artikelsuchliste nicht erforderlich.
12. **Runterschreiben:** Manuelle Artikelauswahl sowohl per EAN als auch per Bestandsliste ermöglichen.
13. **Benutzerverwaltung:** Zentrale soll Mitarbeiter- und Filialleiterkonten hinzufügen und löschen können. Technische Behandlung historischer Buchungen beim Löschen noch festzulegen.
14. **Übersicht:** Fünf Schnellzugriffe pro Benutzer speichern, frei auswählbar und per Drag-and-drop sortierbar machen. Alle Knöpfe gleich hoch, anhand des höchsten benötigten Inhalts.
15. **Artikelsuche:** Liste optisch an Bestand angleichen; Kategorie zuerst, Marke und Bezeichnung zusammenführen, Lieferanten-Artikelnummer und EAN zusammenführen.
16. **Ausbuchen:** Neben EAN-Eingabe eine Bestandsliste zum Durchsehen und Auswählen anbieten; bestehende Ausbuchungsrechte beibehalten.
17. **Erfassen:** Lieferantenauswahl auf fünf Gruppen beschränken: 111 Intersport, 333 Händler, 444 Intern, 555 ECOM, 999 Dritt-Händler. Keine einzelnen Markenlieferanten in diesem Auswahlfeld.

## Bestätigte Antworten vom 24.09.2026

- **Einnahmen:** Vor der Kassenanbindung als geschätzte Einnahmen aus als „Verkauf“ ausgebuchten Artikeln und ihrem damaligen reduzierten Verkaufspreis berechnen; ausdrücklich als Schätzung anzeigen. Keine Gleichsetzung mit echten Kasseneinnahmen.
- **Manuelle Reduktion:** Alle Mitarbeitenden dürfen je Filiale zwischen **30 %, 50 % und 70 %** wechseln. Die Entscheidung erweitert nicht die bestehenden Filialzuordnungen; keine freien Prozentsätze. Empfehlung und manuell gewählte Stufe getrennt behandeln; Bestand zeigt die wirksame Stufe.
- **Schnellzugriffe:** Fünf Funktionen und ihre Reihenfolge **pro Benutzer** speichern.

Die drei Rückfragen sind beantwortet. Anforderungen noch nicht implementiert; dieser Auftrag betrifft die Dokumentation.

## Referenzen

Originalformulierungen und Screenshots liegen lokal im Vault Main unter `01 Projekte/Sportfabrik Inventory/Sportfabrik Inventory – Artikeldetails und Auswertungen.md`. Keine privaten Screenshots ins Repository kopiert.
