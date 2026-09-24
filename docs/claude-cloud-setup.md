# Claude Code in Cloud-Sessions einrichten

Lokal installierte Claude-Code-Plugins gelten nur auf dem eigenen Rechner.
Cloud-Sessions (claude.ai/code, `claude --cloud`, GitHub-Trigger) starten in
einem frischen Container und bringen nichts davon mit. Diese Anleitung richtet
sie dort ein.

## Warum das Repo-Setting allein nicht reicht

Naheliegend wäre, `enabledPlugins` und `extraKnownMarketplaces` in
`.claude/settings.json` zu schreiben. Das greift für Cloud-Sessions **nicht** —
die Claude-Code-Dokumentation führt „Plugins and marketplaces declared in your
repo's `.claude/settings.json`" ausdrücklich als *nicht* verfügbar auf
([Cloud environments → What carries over from your setup](https://code.claude.com/docs/en/cloud-environments#what-carries-over-from-your-setup)).

Entscheidend ist der Zeitpunkt: Plugins werden beim Start von Claude Code
geladen. Was erst *während* des Starts installiert wird — durch einen
SessionStart-Hook etwa — ist in derselben Session noch nicht da. Nur das
**Setup-Skript** der Umgebung läuft davor.

| | Setup-Skript | SessionStart-Hook |
| --- | --- | --- |
| Konfiguriert in | claude.ai/code → Umgebungs-Wähler → Zahnrad | `.claude/settings.json` im Repo |
| Läuft | vor dem Start von Claude Code | nach dem Start |
| Gilt für | nur Cloud-Sessions | lokal und Cloud |
| Hier zuständig für | Systempakete, Datenbank, Plugins | Dienst starten, Python-Abhängigkeiten |

Nach dem Setup-Skript wird das Dateisystem gespeichert; spätere Sessions starten
direkt aus diesem Abbild und überspringen das Skript. Es läuft erneut, wenn du
das Skript oder die Netzwerkfreigaben änderst, und nach etwa sieben Tagen.

Das Abbild hält **Dateien, keine Prozesse**. Installierte Pakete und die
angelegte Datenbank sind in jeder späteren Session da; ein im Setup-Skript
gestarteter Dienst dagegen nicht — der gehört in den Hook.

## 1. Setup-Skript eintragen

Auf [claude.ai/code](https://claude.ai/code) in der Zeile über dem
Nachrichtenfeld auf das Wolken-Symbol mit dem Umgebungsnamen klicken, im
Abschnitt **Cloud** über die Umgebung fahren, das **Zahnrad** anklicken und den
Inhalt von [`scripts/claude-cloud-setup.sh`](../scripts/claude-cloud-setup.sh)
in das Feld **Setup script** kopieren. Eine Einstellungsseite oder direkte URL
dafür gibt es nicht.

Das Skript ist bewusst eigenständig — es greift auf nichts aus dem Repo zu, weil
zu diesem Zeitpunkt nicht garantiert ist, dass der Klon schon vorliegt. Es
erledigt drei Dinge: Systempakete (PostgreSQL, Tesseract mit DE/FR für OCR),
die Test-Datenbank `sportfabrik_dev` samt Benutzer, und die Plugins.

Alles kommt aus einem einzigen Marktplatz:
[`FreaXz03/claude-plugin-marketplace`](https://github.com/FreaXz03/claude-plugin-marketplace).
Der bündelt die offiziellen Anthropic-Plugins und die aus fremden Repos an einer
Stelle; bis auf `markitdown` verweist er per `git-subdir` auf die
Original-Repos, die Plugins bleiben also von selbst aktuell.

**Der Marktplatz und die dort verlinkten Quell-Repos müssen öffentlich sein.**
Der Container hat keinen Git-Credential-Helper und kein `gh`; ein privates Repo
scheitert mit `could not read Username`. Weil im Skript hinter jedem Aufruf ein
`|| true` steht, fällt das sonst nicht auf — das Plugin fehlt einfach.

Installiert werden:

| Plugin | Wofür |
| --- | --- |
| `pyright-lsp` | Typprüfung live, passend zu `pyrightconfig.json` |
| `code-review` | `/code-review` mit spezialisierten Agenten |
| `commit-commands` | `/commit`, `/commit-push-pr`, `/clean_gone` |
| `claude-md-management` | `CLAUDE.md` pflegen |
| `security-guidance` | Sicherheitshinweise beim Bearbeiten |
| `frontend-design` | Oberfläche, passend zu Vanilla JS/CSS |
| `playwright` | Browsersteuerung; Chromium ist vorinstalliert |
| `markitdown` | Dokumente nach Markdown wandeln |
| `caveman` | knappe Antworten |
| `context-mode` | Kontextfenster schonen |
| `context7` | Bibliotheks-Dokumentation zur Hand |
| `claude-mem` | Gedächtnis über Sessions hinweg |

Die ersten zehn laufen vollständig im Container. Die letzten beiden nicht:
`context7` holt Dokumentation von einem externen Dienst, `claude-mem` überträgt
Sitzungsdaten an cmem.ai und liest von dort zurück. Regel 1 in `CLAUDE.md`
erlaubt das: sie verlangt lokale Verarbeitung für **Belegdaten**, nicht für die
Entwicklungswerkzeuge.

Eine Einschränkung bleibt aber bestehen: `claude-mem` überträgt, was die Session
anfasst. Wer in einer Session mit echten Belegen aus `uploads/` oder
`Rechnungen/` arbeitet — etwa beim Bau eines neuen Parsers —, schickt deren
Inhalte mit. Auch bei Graphify ist die Auswahl der tatsächlich verarbeiteten Inhalte entscheidend; `--code-only` ist optional, automatische Beleganalyse bleibt ausgeschlossen (siehe `docs/obsidian-graphify.md`). Für
solche Sessions `claude-mem` deaktivieren (`/plugin`) oder die beiden Zeilen aus
der Plugin-Liste streichen.

**Im Marktplatz gelistet, aber bewusst nicht installiert:**

- `obsidian` — der Vault liegt auf dem Arbeitsrechner, im Container nutzlos.
- `security-sweep` — das im Manifest hinterlegte Quell-Repo
  `onomeaj/security-sweep-plugin` ist nicht anonym klonbar (`git ls-remote`
  fragt nach einem Benutzernamen). Soll es mit in die Cloud, muss das Plugin wie
  `markitdown` direkt im eigenen Marktplatz-Repo liegen statt per `git-subdir`
  verlinkt.

**Gar nicht verfügbar:** desktop-gebundene Plugins (Desktop Commander,
pdf-viewer, cowork-plugin-management) haben im Container keine Grundlage.

## 2. SessionStart-Hook registrieren

Ohne diesen Schritt läuft in einer Cloud-Session weder die Testsuite noch die
App: die Python-Pakete fehlen, und PostgreSQL ist zwar installiert, aber nicht
gestartet. `.claude/settings.json` anlegen (oder den `hooks`-Block in eine
bestehende Datei einfügen):

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/scripts/claude-session-deps.sh"
          }
        ]
      }
    ]
  }
}
```

[`scripts/claude-session-deps.sh`](../scripts/claude-session-deps.sh) startet
PostgreSQL, legt ein `.venv` an, installiert `requirements.txt` plus pytest und
setzt den Pfad für die Session. Lokal beendet es sich sofort
(`CLAUDE_CODE_REMOTE`), das vorhandene `.venv` bleibt unangetastet.

**Warum ein `.venv` und nicht der Systempython:** dort scheitert
`pip install -r requirements.txt` reproduzierbar mit
`Cannot uninstall PyYAML 6.0.1, RECORD file not found. Hint: The package was
installed by debian` — auch mit `--break-system-packages`. `pyrightconfig.json`
zeigt ohnehin auf `.venv`.

Der Hook läuft synchron: die Session startet erst, wenn er fertig ist. Gemessen
sind rund 22 Sekunden beim ersten Mal, danach etwa 4, weil `.venv` steht und nur
noch der Dienst hochkommt. Wer den schnelleren Start bevorzugt, kann den Hook
asynchron ausführen und nimmt dafür in Kauf, dass ein früher `pytest`-Aufruf ins
Leere läuft.

## Geprüft

In einem frischen HOME, also so wie ein neuer Container startet:

- `claude plugin validate .` gegen den Marktplatz → „Validation passed".
- Marktplatz hinzugefügt und die zehn rein lokalen Plugins daraus installiert:
  alle zehn erfolgreich, `security-sweep` als einziges gescheitert (Quell-Repo
  nicht anonym klonbar, siehe oben).
- Eine so vorbereitete Session lädt die Plugins auch im Projektverzeichnis —
  mit der Vorversion des Skripts geprüft: `code-review:`, `commit-commands:`
  (drei), `claude-md-management:` (zwei), `frontend-design:`. `pyright-lsp`,
  `security-guidance` und `playwright` bringen keine Skills mit, sondern LSP,
  Hooks bzw. einen MCP-Server.
- `context7` und `claude-mem` wurden **nicht** probeweise installiert — der
  Auto-Modus der Entwicklungs-Session hat das unterbunden, weil `claude-mem`
  Sitzungsdaten nach aussen überträgt. Geprüft ist stattdessen, dass beide im
  Marktplatz-Manifest stehen und dass das Skript die richtigen Befehle absetzt.
  Der erste echte Lauf ist der in deiner Umgebung.
- Hook: Exit-Code 0, 22 Sekunden beim ersten Lauf, 4 Sekunden bei stehendem
  `.venv`. Gegenprobe mit vorher gestopptem Dienst — danach meldet `pg_isready`
  „accepting connections", und `CLAUDE_ENV_FILE` enthält den `.venv`-Pfad.
- Datenbank erreichbar: `create_engine(DATABASE_URL)` verbindet sich als
  `sportfabrik` auf `sportfabrik_dev`.
- Danach `pytest -q` → 369 bestanden, 19 übersprungen;
  `pyright app/services/corrections.py` → 0 Fehler.

Im laufenden Container ebenfalls bestätigt: `psql` und `tesseract` (mit `deu`,
`fra`) sind vorhanden und die Datenbank besteht weiter — die Systempakete und
die Daten überleben also im Abbild. Der PostgreSQL-Dienst dagegen war unten,
und die Python-Pakete fehlten: der `pip`-Aufruf im Setup-Skript scheitert am
Debian-PyYAML und wird dort von `|| true` verschluckt. Genau diese beiden
Lücken schliesst der Hook.

## Wenn etwas fehlt

- `claude plugin list` zeigt, was geladen ist, `/plugin` die Oberfläche dazu.
- Das Setup-Skript muss mit 0 enden, sonst startet die Session nicht — deshalb
  steht hinter jedem Aufruf ein `|| true`.
- Nach einer Änderung am Skript läuft es beim nächsten Sessionstart erneut, das
  gespeicherte Abbild wird neu gebaut.
