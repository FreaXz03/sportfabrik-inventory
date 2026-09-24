# Anforderungen aus der Obsidian-Inbox – 23.09.2026

Status: fachliche Anforderungen, keine Umsetzung durch diesen Dokumentationsabgleich.

- Header auf allen Seiten vereinheitlichen.
- Artikelsuche aufräumen und für Benutzer ohne PC-Erfahrung vereinfachen.
- EAN-Suchfeld beim Öffnen der Artikelseite automatisch fokussieren.
- Im Bestand Grösse und Farbe in getrennten Spalten sowie die Hauptgruppe anzeigen.
- Übersicht hochwertiger gestalten: Statistiken, bevorstehende Vorgänge und Aktuelles.
- Artikel mit Menge 0 aus der Bestandsansicht entfernen; im Artikelstamm erhalten.
- Ausbuchungen als Liste mit Zeitpunkt, ausführender Person und Grund anzeigen.
- Manuell einzeln importierte Artikel auflisten; gewünschte vollständige Löschung planen und Umgang mit Historie klären.
- Artikel im Stamm nur durch Filialleiter löschbar machen; Konflikt mit dauerhafter Stammhaltung vor Umsetzung klären.
- Parser für alle Beispielbelege im Vault ergänzen; siehe der lokalen Belegsammlung im Obsidian-Vault.
- Benutzerfreundlichkeit und gute Lesbarkeit für Mitarbeitende mit Brille oder wenig PC-Erfahrung durchgehend berücksichtigen.
- Lieferantengruppen und Codes gemäss der folgenden Tabelle umsetzen und Codes auf Etiketten drucken.

## Fachliche Vorgaben

Benutzerfreundlichkeit ist eine zentrale Projektanforderung: Mitarbeitende mit Brille und/oder wenig PC-Erfahrung sollen das System einfach bedienen können. Gute Lesbarkeit, klare Navigation und wenige übersichtliche Suchparameter sind entsprechend wichtig.

| Lieferantengruppe | Code für Etiketten | Bedeutung |
| --- | --- | --- |
| Intersport | 111 | Direkte Bestellung bei Intersport |
| ECOM | 555 | Onlineshop-Retouren vom Intersportshop |
| Händler | 333 | Verkaufsläden in der Umgebung, die Artikel nicht mehr brauchen |
| Dritte-Händler | 999 | Direktbestellungen bei Marken, z. B. Puma, Alpina, Columbia, Salomon; die unten genannten Intern-Marken sind ausgenommen |
| Intern | 444 | Direktbestellungen ausschliesslich bei Nike, Adidas und Northface |

Etikettengrösse erneut bestätigt: **8.4 cm × 4.7 cm = 84 × 47 mm**. Keine erneute Änderung erforderlich.

Gewünschtes Verhalten bei Menge 0: Artikel aus der Bestandsansicht entfernen, im Stamm erhalten. Separater Wunsch: manuell importierte Artikel vollständig löschbar machen und allgemeines Löschen im Stamm auf Filialleiter beschränken. **Offene fachliche Frage:** Wie soll die vollständige Löschung bei bereits vorhandenen Belegen und Lagerbewegungen funktionieren? Dies widerspricht der bisherigen Regel „Artikelstamm bleibt für immer“; noch keine Löschstrategie festgelegt.


Quellen im lokalen Obsidian-Vault Main: `01 Projekte/Sportfabrik Inventory/Sportfabrik Inventory – Anforderungen vom 23.09.2026.md` und `03 Ressourcen/Bilder Kassensystem Sportfabrik.md` (acht Screenshots). Originale bleiben lokal im Vault; keine Bilder oder Belege ins Repository kopiert.

## Umsetzung

- **Lieferantengruppen und Codes** (24.09.2026): Gruppe = `lieferanten.typ`, Code daraus abgeleitet (`app/core/lieferanten.py`), fett rechts neben dem Lieferanten auf dem Etikett und in der Lieferantenauswahl der Erfassung. Je Gruppe ein Lieferant für Ware von Hand. **Einschränkung:** ECOM-Retouren kommen im Intersport-Layout und werden vom Parser noch dem Lieferanten INTERSPORT zugeordnet (Code 111), bis der Parser sie erkennt (Referenz „ret.Ecom").
- **Bestandsansicht** (24.09.2026): Farbe und Grösse in eigenen Spalten, dazu die Hauptgruppe (unübersetzt wie in der Kasse). Zeilen mit Menge 0 erscheinen nicht mehr, der Schalter dafür ist weg; bucht man eine Zeile auf 0, verschwindet sie sofort. Der Artikel bleibt im Stamm, ein negativer Bestand bleibt sichtbar.
- **Liste der Ausbuchungen** (24.09.2026): auf der Seite „Ausbuchen" alle Verkäufe und Abgänge aus dem Journal, neueste zuerst, mit Zeit, Artikel, Filiale, Grund und Person; filterbar nach Filiale, mit „Rückgängig". API `GET /api/ausbuchungen`.
- **Artikelsuche** (24.09.2026): oben nur zwei grosse Felder — „EAN scannen" (beim Öffnen aktiv, Scan + Enter sucht sofort und markiert das Feld für den nächsten Scan) und „Schnellsuche"; Marke, Lieferanten-Artikelnummer, Bezeichnung, Kategorie und Lieferdatum stehen unter „Weitere Filter".
- **Übersicht** (24.09.2026): Begrüssung mit Filiale und Datum, grosse Schnellzugriffe (Ausbuchen, Erfassen, Umlagern, Lieferungen, Beleg hochladen), Kennzahlen der aktiven Filiale (Stück im Bestand, heute verkauft), „Anstehend" (angekündigte Lieferungen, negativer Bestand zum Zählen, Artikel im Alter für −50 %/−70 % oder in den nächsten 30 Tagen, Artikel ohne Kategorie, Varianten ohne EAN) und „Aktuelles" (letzte Buchungen mit Person). Service `app/services/uebersicht.py`.

## Entscheid vom 24.09.2026 zur Artikellöschung

Löschen braucht es vor allem für **von Hand erfasste** Artikel: trägt jemand einen Artikel falsch neu ein, muss ihn jemand wieder herausnehmen können. Umsetzung:

- Löschen dürfen nur **Filialleiter und Zentrale**.
- Gelöscht werden kann ein Artikel nur, wenn **kein Beleg** an ihm hängt (alle seine Wareneingänge sind manuelle Erfassungen ohne Dokument). Artikel aus Belegen bleiben im Stamm (Regel 4) — dort korrigiert man den Beleg bzw. löscht den Beleg.
- Beim Löschen verschwinden Artikel, Varianten, Preise, Notizen, die manuellen Wareneingangspositionen, Bestand und die zugehörigen Lagerbewegungen — der Fehleintrag soll keine Spuren im Bestand hinterlassen. Das ist eine bewusste Ausnahme von Regel 2 nur für diesen Fall; der Vorgang wird protokolliert (wer, wann, welcher Artikel).
