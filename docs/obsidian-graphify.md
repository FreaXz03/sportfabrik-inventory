# Projektwissen: Graphify und Obsidian

## Regel ab 24.09.2026

**`--code-only` ist keine allgemeine Pflicht mehr.** Code und ausdrücklich ausgewählte Projektdokumentation dürfen in Graphify verarbeitet werden. Die Dokumentauswahl steht in `docs/wissensquellen.txt`; `.graphifyignore` begrenzt direkte Projektscans ebenfalls. Neue Dokumentquellen bewusst in beiden Listen aufnehmen.

Keine automatische Verarbeitung von Lieferantenbelegen, Uploads, Zugangsdaten oder persönlichen Vault-Bereichen. Die bewusste Freigabe einzelner Belege zum Parserbau bleibt eine separate Ausnahme. Im fertigen Warenwirtschaftssystem werden Belege weiterhin ausschliesslich lokal durch eigene Parser verarbeitet.

GitHub-Veröffentlichung und Verarbeitung beim KI-Anbieter sind getrennte Vorgänge. Der Graph bleibt unter dem gitignorierten `graphify-out/`. Ein semantischer Lauf kann trotzdem Inhalte der ausgewählten Dokumente an den gewählten KI-Anbieter übertragen und Tokens verbrauchen. Kein pauschaler Scan des Vaults; keine automatische semantische Analyse nach jedem Commit.

## Alltag: gezielt finden

```sh
python3 scripts/projektwissen.py query "Umlagerung"
python3 scripts/projektwissen.py query "reduktionen_manuell"
```

Das Werkzeug erstellt lokal einen **strukturellen Dokumentabschnittsindex** aus Überschriften, kurzen Originalauszügen und expliziten Codepfaden. Es verbindet ihn für die Abfrage mit dem vorhandenen Graphify-Codegraphen und ruft Graphify mit begrenztem Ausgabebudget auf. Das ist keine semantische KI-Analyse der Dokumente und kein vollständiges Modell aller fachlichen Zusammenhänge. Nach einem Treffer immer den relevanten Originalabschnitt prüfen.

Die ausgewählten Markdown-Dateien werden dafür lokal gelesen; ihr vollständiger Text wird nicht in den Modellkontext ausgegeben. Der zusammengeführte Graph liegt in `graphify-out/knowledge/graph.json`. Er wird bei jeder Abfrage neu erzeugt; der originale Codegraph bleibt unangetastet. Ist er nicht vorhanden, funktioniert der Dokumentindex allein mit einem Hinweis. Fehlende/veraltete Codebeziehungen mit gezielter Textsuche abfangen.

Bekannte Datei direkt lesen. Für gezielte Codebeziehungen sind auch `graphify explain "<Funktion>"` und `graphify path "<A>" "<B>"` am ursprünglichen Codegraphen möglich. Niemals die komplette graph.json in den Chat laden.

## Aktualisieren

Der vorhandene Git-Hook aktualisiert weiterhin nur die Codestruktur, lokal und ohne Sprachmodell. Dies ist eine günstige Automatik, keine Einschränkung der erlaubten Dokumentanalyse. Bei Bedarf: `graphify update .` (Code-Aktualisierung der installierten Version); danach `python3 scripts/projektwissen.py index`.

## Optionale semantische Dokumentanalyse

Wenn der Abschnittsindex für eine konkrete Frage nicht reicht:

```sh
python3 scripts/projektwissen.py prepare-docs
# Nur die explizite Auswahl, nicht das Projekt oder den Vault scannen:
graphify extract graphify-out/selected-docs/input --out graphify-out/selected-docs --no-gitignore --backend claude --max-concurrency 1 --token-budget 6000
```

`prepare-docs` erstellt einen sauberen lokalen Eingabeordner aus der Freigabeliste, ohne Symlinks oder weitere Dateien. `--no-gitignore` ist hier nur nötig, weil dieser vorbereitete Ordner unter dem absichtlich gitignorierten Ausgabeordner liegt; nicht für beliebige Projektscans verwenden. Vor dem KI-Lauf nennt die Dateiliste den Umfang. Der explizite Anbieter verhindert eine unbeabsichtigte automatische Anbieterwahl; seine lokale Anmeldung/API-Konfiguration muss verfügbar sein. Nicht automatisch starten, nur wenn eine Aufgabe die zusätzliche semantische Analyse rechtfertigt.

Das Ergebnis bleibt als separater Dokumentgraph in `graphify-out/selected-docs/graphify-out/graph.json` und kann mit `graphify query "<Frage>" --graph <Pfad> --budget 1200` abgefragt werden. Nach Dokumentänderungen vor Nutzung aktualisieren. Der günstige Standardindex wird dadurch nicht ersetzt und der Code-Hook überschreibt diesen Dokumentgraphen nicht.

## Obsidian und Quellen

- Main-Vault: eigene Ideen, Anforderungen und verständliche Übersicht.
- `docs/start.md`: aktueller Einstieg und nächste Priorität.
- Technische Dokumente im Projekt: jeweilige Hauptquelle; nur betroffene Abschnitte nachführen.
- Historische Vault-Statuskopien: Archiv, nicht bei jeder Aufgabe mitlesen.
- Generierter Sportfabrik-Graph: optionale visuelle Ansicht, keine zusätzliche Informationsquelle für Claude.

Bei Bedarf nach `python3 scripts/projektwissen.py index` exportieren:

```sh
graphify export obsidian --graph graphify-out/knowledge/graph.json --dir graphify-out/Sportfabrik-Graph
```

Keine handgeschriebenen Notizen im generierten Bereich pflegen. Ohne lokalen Graph (beispielsweise Cloud-Session) direkt mit `rg` und gezielten Dateiausschnitten arbeiten.

## Sitzungen

Nach einer abgeschlossenen Aufgabe kurze Übergabe: Ergebnis, relevante Dateien, offene Punkte. Für eine unabhängige Aufgabe neue Sitzung; lange laufende Aufgaben bei Bedarf verdichten. Graphify ersetzt weder Kontextpflege noch das Prüfen des aktuellen Codes. Eine konkrete Tokenersparnis ist erst durch vergleichbare Sitzungen messbar.
