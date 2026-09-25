# Handynutzung – Planung

## Abgestimmter Plan zur Handynutzung – 24.09.2026

**Status: ausschliesslich Planung. Umsetzung erst gegen Ende des Projekts; jetzt keine Implementierung.** Ein genauer Termin und die Einordnung relativ zu den Phasen F/G sind noch nicht festgelegt.

- **App-Form:** bestehendes Sportfabrik Inventory als handytaugliche Web-App erweitern, über einen Link öffnen und als Symbol auf dem Startbildschirm ablegen. Keine separate native App oder App-Store-Veröffentlichung eingeplant.
- **Geräte:** private Handys der Mitarbeitenden, Filialleiter und Geschäftsleitung; persönliche Logins und bestehende Rollen/Berechtigungen bleiben erhalten.
- **Funktionen:** Artikel suchen oder EAN/Barcode mit der Handykamera scannen; Preis, Grösse, Farbe und Bestände der Filialen ansehen; Ware zählen und Bestände korrigieren; Wareneingänge bestätigen, umlagern und ausbuchen. Grosse, einfach bedienbare Schaltflächen vorsehen.
- **Mitarbeitende:** Zugriff ausschliesslich über das freigegebene Geschäfts-WLAN. Von ausserhalb weder Datenzugriff noch Buchungen. „Im Geschäft“ wird über den erlaubten Netzwerkzugang bestimmt, nicht über GPS.
- **Filialleiter und Geschäftsleitung/Zentrale:** zusätzlich geschützter Zugriff von unterwegs und zu Hause, auch über Mobilfunk. Der externe Zugang erweitert die bestehenden Bearbeitungsrechte nicht.
- **Zugriffsschutz:** der Server muss Netzwerkzugang und Rolle prüfen; ausgeblendete Bedienelemente allein genügen nicht. Konkrete VPN-Lösung, erlaubte WLANs und Netztrennung sind noch festzulegen; Tailscale ist höchstens ein Beispiel, keine beschlossene Lösung.
- **Daten und Verbindung:** Handy und PC verwenden dieselbe zentrale Datenbank auf dem Sportfabrik-Server. Zunächst ist eine Verbindung zum Server erforderlich; Offline-Buchungen und spätere Synchronisierung sind nicht eingeplant.
- **Spätere Umsetzung:** zuerst mobile Suche und Kamera-Scan auf Fabians iPhone erproben, anschliessend die Buchungsabläufe ergänzen und auf iPhone/Android testen. Kamera-Scan mit echten Etiketten prüfen; unbeabsichtigte Mehrfachbuchungen desselben Barcodes verhindern.

Quelle: Fabians Bestätigung im Gespräch vom 24.09.2026. Dieser Plan ist kein Auftrag, die mobile Nutzung jetzt zu bauen.
