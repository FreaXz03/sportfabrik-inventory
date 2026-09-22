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
| Konfiguriert in | claude.ai/code → Umgebung | `.claude/settings.json` im Repo |
| Läuft | vor dem Start von Claude Code | nach dem Start |
| Gilt für | nur Cloud-Sessions | lokal und Cloud |
| Hier zuständig für | Plugins | Projekt-Abhängigkeiten |

Nach dem Setup-Skript wird das Dateisystem gespeichert; spätere Sessions starten
direkt aus diesem Abbild und überspringen das Skript. Es läuft erneut, wenn du
das Skript oder die Netzwerkfreigaben änderst, und nach etwa sieben Tagen.

## 1. Plugins: Setup-Skript eintragen

Auf [claude.ai/code](https://claude.ai/code) die Umgebung bearbeiten und den
Inhalt von [`scripts/claude-cloud-setup.sh`](../scripts/claude-cloud-setup.sh)
in das Feld **Setup script** kopieren. Das Skript ist bewusst eigenständig — es
greift auf nichts aus dem Repo zu, weil die Reihenfolge von Klonen und
Setup-Skript nicht garantiert ist.

Installiert werden diese Plugins:

| Plugin | Marktplatz | Wofür |
| --- | --- | --- |
| `pyright-lsp` | offiziell | Typprüfung live, passend zu `pyrightconfig.json` |
| `code-review` | offiziell | `/code-review` mit spezialisierten Agenten |
| `commit-commands` | offiziell | `/commit`, `/commit-push-pr`, `/clean_gone` |
| `claude-md-management` | offiziell | `CLAUDE.md` pflegen |
| `security-guidance` | offiziell | Sicherheitshinweise beim Bearbeiten |
| `frontend-design` | offiziell | Oberfläche, passend zu Vanilla JS/CSS |
| `playwright` | offiziell | Browsersteuerung; Chromium ist vorinstalliert |
| `context7` | offiziell | Bibliotheks-Dokumentation zur Hand |
| `claude-mem` | `thedotmack` | Gedächtnis über Sessions hinweg |

Die ersten sieben laufen vollständig im Container. Die letzten beiden nicht:
`context7` holt Dokumentation von einem externen Dienst, `claude-mem` überträgt
Sitzungsdaten an cmem.ai und liest von dort zurück. Regel 1 in `CLAUDE.md`
erlaubt das: sie verlangt lokale Verarbeitung für **Belegdaten**, nicht für die
Entwicklungswerkzeuge.

Eine Einschränkung bleibt aber bestehen: `claude-mem` überträgt, was die Session
anfasst. Wer in einer Session mit echten Belegen aus `uploads/` oder
`Rechnungen/` arbeitet — etwa beim Bau eines neuen Parsers —, schickt deren
Inhalte mit. Das ist derselbe Punkt wie bei Graphify ohne `--code-only`. Für
solche Sessions `claude-mem` deaktivieren (`/plugin`), oder gleich `context7`
und den zweiten `install_marketplace`-Aufruf aus dem Skript streichen.

**Nicht dabei:**

- Plugins aus einem lokalen Marktplatz (`my-plugins`, `obsidian-skills`,
  `local-desktop-app-uploads`) sind aus der Cloud nicht erreichbar. Dafür müsste
  der Marktplatz in einem Git-Repository liegen; dann lässt er sich mit
  `claude plugin marketplace add <owner>/<repo>` genauso einbinden.
- Desktop-gebundene Plugins (Desktop Commander, pdf-viewer,
  cowork-plugin-management) haben im Container keine Grundlage.

## 2. Abhängigkeiten: SessionStart-Hook registrieren

Ohne diesen Schritt kann eine Cloud-Session die Testsuite nicht ausführen — der
Container bringt weder FastAPI noch pytest mit. `.claude/settings.json` anlegen
(oder den `hooks`-Block in eine bestehende Datei einfügen):

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

[`scripts/claude-session-deps.sh`](../scripts/claude-session-deps.sh) legt ein
`.venv` an, installiert `requirements.txt` plus pytest und setzt den Pfad für
die Session. Lokal beendet es sich sofort (`CLAUDE_CODE_REMOTE`), das
vorhandene `.venv` bleibt unangetastet.

Der Hook läuft synchron: die Session startet erst, wenn er fertig ist. Gemessen
sind rund 22 Sekunden. Der Vorteil ist, dass die Abhängigkeiten sicher stehen,
bevor gearbeitet wird; wer den schnelleren Start bevorzugt, kann den Hook
asynchron ausführen und nimmt dafür in Kauf, dass ein früher `pytest`-Aufruf ins
Leere läuft.

## Geprüft

In einem frischen HOME, also so wie ein neuer Container startet:

- Setup-Skript läuft durch, Exit-Code 0, die sieben rein lokalen Plugins
  installiert.
- Eine danach gestartete Session im Projektverzeichnis lädt sie: `code-review:`,
  `commit-commands:` (drei), `claude-md-management:` (zwei), `frontend-design:`.
  `pyright-lsp`, `security-guidance` und `playwright` bringen keine Skills mit,
  sondern LSP, Hooks bzw. einen MCP-Server.
- `context7` und `claude-mem` wurden **nicht** probeweise installiert — der
  Auto-Modus der Entwicklungs-Session hat das unterbunden, weil `claude-mem`
  Sitzungsdaten nach aussen überträgt. Geprüft ist stattdessen, dass beide in
  ihrem Marktplatz vorhanden sind (`context7` im offiziellen Katalog,
  `claude-mem` im Manifest von `thedotmack/claude-mem`) und dass das Skript die
  richtigen Befehle absetzt. Der erste echte Lauf ist der in deiner Umgebung.
- Abhängigkeits-Skript: Exit-Code 0, 22 Sekunden.
- Danach `pytest tests/test_ean_etikett.py tests/test_lagerorte.py` → 80 grün,
  `pyright app/services/corrections.py` → 0 Fehler.

## Wenn etwas fehlt

- `claude plugin list` zeigt, was geladen ist, `/plugin` die Oberfläche dazu.
- Das Setup-Skript muss mit 0 enden, sonst startet die Session nicht — deshalb
  steht hinter jedem Aufruf ein `|| true`.
- Nach einer Änderung am Skript läuft es beim nächsten Sessionstart erneut, das
  gespeicherte Abbild wird neu gebaut.
