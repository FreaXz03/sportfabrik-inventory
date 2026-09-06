# Automatische Sicherungen

Die tägliche Ausführung ist in Codex für 20:00 Uhr (Europe/Zurich) eingerichtet.
Sie ist an diesen lokalen Codex-Task gebunden, kein Windows- oder Linux-Systemdienst.
Der PC, Codex und Docker müssen für die Ausführung verfügbar sein. Beim Umzug auf
Linux muss ein eigener Serverzeitplan eingerichtet und getestet werden.

Manuell im Projektordner:

```powershell
.\.venv\Scripts\python.exe scripts/backup_inventory.py
```

Ziel: `backups/automatic/inventory-ZEITSTEMPEL/` (Zeitstempel in UTC).
Jeder vollständige Ordner enthält `database.dump`, `original-pdfs.zip`,
`archive-contents.txt` und `manifest.json` mit SHA-256-Prüfsummen.

Die Datenbanksicherung umfasst auch Benutzer und Passwort-Hashes. Die PDF-Sicherung
nimmt Dateien aus `Recchnungen/` und `uploads/` auf; nur hochgeladene, dort nicht
abgelegte PDF-Dateien können nicht mitgesichert werden. Konfigurationsgeheimnisse
wie `.env.server` werden nicht ins Backup kopiert und müssen separat sicher
aufbewahrt werden.

Prüfungen: erfolgreicher pg_dump, lesbares Inhaltsverzeichnis mit pg_restore --list,
ZIP-CRC. Diese Prüfungen ersetzen keinen regelmässigen vollständigen Restore-Test.
Bei Fehlern wird kein unvollständiger Ordner als fertiges Backup veröffentlicht.

Es gibt vorerst keine automatische Löschung. Speicherbelegung kontrollieren.
Eine Kopie ausserhalb des PCs ist noch nicht eingerichtet (Benutzer: später).
Wenn ein Ziel bereitsteht:

```powershell
.\.venv\Scripts\python.exe scripts/backup_inventory.py --external "E:\InventoryBackups"
```

Der externe Ordner muss existieren. Nach dem Kopieren werden die Prüfsummen
verglichen. Ein Kopierfehler lässt das lokale Backup erhalten und meldet einen
Fehler. Bei Einrichtung des Ziels auch die Codex-Automation aktualisieren.
