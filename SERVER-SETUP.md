# Vorbereitung für Linux

Die Serverdateien sind vorbereitet. Ein Docker-Build, Datenumzug und eine
Backup-Wiederherstellung wurden noch nicht durchgeführt. Die Windows-App und
ihre `.env` bleiben weiter nutzbar.

## Dateien

- `Dockerfile`: App ohne Entwicklungsmodus, als Benutzer ohne Root-Rechte.
- `requirements-server.txt`: Serverpakete getrennt von der Windows-Installation.
- `compose.yaml`: App und PostgreSQL 18, dauerhaftes Datenvolume, Startprüfungen.
- `.env.server.example`: Vorlage für Servereinstellungen.
- `.dockerignore`: nur App-Code und Serverabhängigkeiten gelangen ins Image.

## Lokal testen, sobald Docker und das Compose-Plugin vorhanden sind

Im Projektordner:

```powershell
Copy-Item .env.server.example .env.server
```

In `.env.server` zwischen den einfachen Anführungszeichen bei `POSTGRES_PASSWORD`
ein neues, langes Passwort eintragen. Das Tutorial-Passwort nicht wiederverwenden.
Die vorhandene `.env` nicht verändern. Dann:

```powershell
docker compose --env-file .env.server config --quiet
docker compose --env-file .env.server up -d --build
docker compose --env-file .env.server ps
```

Testadresse: http://127.0.0.1:8080. Die Container verwenden eine neue, separate
Datenbank. Anfangs sind keine Rechnungen vorhanden. Die Windows-App auf Port
8000 und ihre bisherigen Daten bleiben getrennt.

## Später auf Linux

1. Serververwaltung stellt Docker Engine und das Compose-Plugin bereit.
2. Projektordner anlegen, beispielsweise `/opt/sportfabrik-inventory`.
3. `app/`, `Dockerfile`, `requirements-server.txt`, `compose.yaml` und die
   Einstellungsvorlage übertragen. Keine Windows-`.env` oder `.venv` ins Image kopieren.
4. Vorlage als `.env.server` kopieren, Passwort setzen und Datei mit
   `chmod 600 .env.server` schützen.
5. Mit obigen Compose-Befehlen starten. Docker muss beim Systemstart starten.
   `restart: unless-stopped` startet die Dienste dann wieder, sofern sie nicht
   bewusst gestoppt wurden.

## Datenumzug und Backups: nächster gesonderter Schritt

Vor dem Umzug die Hauptversion der Windows-PostgreSQL-Installation prüfen.
Das Ziel muss mindestens dieselbe Hauptversion unterstützen. Die Vorlage nutzt
PostgreSQL 18, passend zur aktuell geprüften Windows-Version 18.6. Falls die Quelle neuer ist, Zielversion und Volume-Pfad vor dem
ersten Start passend ändern. Ein bestehendes Volume nicht einfach mit einer
anderen PostgreSQL-Hauptversion verwenden.

Mit `pg_dump` ein vollständiges Backup erstellen und zuerst in einer leeren
Testdatenbank mit `pg_restore` wiederherstellen. Artikel, Rechnungen, Positionen
und Originaltexte vergleichen. Vor dem endgültigen Export neue Uploads anhalten,
damit zwischen Sicherung und Umzug keine Rechnungen fehlen.

Original-PDFs liegen zusätzlich im Windows-Ordner `Recchnungen/` und müssen
separat gesichert und bei Bedarf übertragen werden.
Backupautomatisierung, Aufbewahrung, externer Sicherungsort und der
Wiederherstellungstest stehen noch aus. Ein Docker-Volume ist kein Backup.

## Zugriff der vier PCs

Erst nach erfolgreichem Test `APP_BIND_IP` auf die interne Server-IP setzen
und `docker compose --env-file .env.server up -d` erneut ausführen.
Zugriff dann über `http://SERVER-IP:8080`. PostgreSQL veröffentlicht keinen Port.

Die App hat derzeit keine Anmeldung. Netzwerkzugriff nur für berechtigte
Laden-PCs freigeben, keine Internet-Portweiterleitung. Serververwaltung muss
Docker-Portfreigaben und Firewallregeln gemeinsam prüfen. Benutzerkonten und
HTTPS bei Bedarf vor Freigabe ergänzen.

## Betrieb

```sh
docker compose --env-file .env.server ps
docker compose --env-file .env.server logs --tail=100 app
docker compose --env-file .env.server stop
docker compose --env-file .env.server start
```

`docker compose down` behält das Datenvolume. **Kein `down -v` verwenden, wenn
Daten erhalten bleiben sollen.** Eine Passwortänderung in `.env.server` ändert
nicht automatisch das Passwort einer bereits initialisierten Datenbank.

Die App legt fehlende Tabellen beim Start an. Änderungen an bestehenden Tabellen
benötigen später eigene Migrationen; ein Neustart ersetzt diese nicht.
