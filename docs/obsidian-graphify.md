# Wissensgraph (Graphify) und Obsidian

Graphify erzeugt aus dem Quellcode einen Wissensgraphen: eine Karte aller
Module, Funktionen, Importe und ihrer Beziehungen. In Obsidian lässt sich
dieselbe Struktur als verlinkte Notizen und als Graph-Ansicht durchklicken;
Claude Code kann den Graphen abfragen, statt jedes Mal alle Python-Dateien zu
lesen.

Das Parsen des **Codes** läuft deterministisch und vollständig lokal über
tree-sitter (AST) — kein Sprachmodell, kein API-Key.

## Harte Regel: immer `--code-only`

Das folgt direkt aus Regel 1 der `CLAUDE.md` („Keine KI, keine externen
Dienste") und ist der wichtigste Punkt auf dieser Seite.

Nur für Quellcode ist Graphify vollständig lokal. PDFs, Bilder und
Office-Dokumente schickt es zur semantischen Analyse an ein Sprachmodell. Auf
dem Entwicklungsrechner liegen in `uploads/` und `Rechnungen/` echte
Lieferantenrechnungen — beide Ordner sind gitignored, auf der Platte aber
vorhanden und damit für einen Lauf ohne `--code-only` sichtbar. Dasselbe gilt
für `docs/*.docx`.

Ein Lauf ohne `--code-only` hat genau das schon einmal getan: der erzeugte
Graph war rund 7 MB gross und enthielt umgewandelte Dokumente (Commit
`46c85a4`). Deshalb:

```
/graphify . --code-only           # richtig
/graphify .                       # falsch — liest Rechnungen mit
```

## Die zwei Umgebungen

Die Werkzeuge sind nicht überall verfügbar:

| | Entwicklungsrechner | Cloud-Session (claude.ai/code) |
|---|---|---|
| Obsidian + Vault | ja | nein |
| Graphify-CLI, `/graphify` | ja | nein |
| `graphify-out/` | ja | nein (ignoriert, siehe unten) |

Der Graph wird also immer lokal gebaut und bleibt vorerst auch lokal.

## Warum `graphify-out/` nicht im Repo liegt

`graphify-out/` ist in der `.gitignore` vollständig ausgenommen. Zwei Gründe:

1. **Das Repo ist öffentlich.** Ein Graph, der ohne `--code-only` gebaut wurde,
   enthält Inhalte aus Lieferantenrechnungen. Einmal gepusht, ist das über
   Git-Historie, Forks und Caches nicht mehr zurückzuholen.
2. **Grösse.** Der bisherige Lauf ergab rund 7 MB, die sich bei jedem Rebuild
   vollständig ändern.

Ein rein mit `--code-only` gebauter Graph wäre inhaltlich unbedenklich — er
beschreibt nur Code, der ohnehin öffentlich im Repo steht. Ob ein solcher
Graph künftig mitversioniert wird, damit auch Cloud-Sessions ihn lesen können,
ist noch **offen**. Bis dahin gilt: nichts aus `graphify-out/` einchecken.

## Einrichtung (lokaler Rechner)

```bash
pip install graphifyy && graphify install
# bei "externally managed environment" (macOS) stattdessen:
#   pipx install graphifyy && graphify install
```

`graphify install` legt die Skill-Datei unter `~/.claude/skills/graphify/SKILL.md`
ab, damit `/graphify` in Claude Code als Slash-Befehl erscheint. Prüfen:

```bash
graphify --version
ls ~/.claude/skills/graphify/SKILL.md
```

## Graph bauen und aktualisieren

Im Projektordner, in lokalem Claude Code:

```
/graphify . --code-only --obsidian --obsidian-dir <pfad-zum-vault>/graphify/sportfabrik-inventory
```

Für spätere Läufe reicht `--update` — dann werden nur geänderte Dateien neu
eingelesen:

```
/graphify . --code-only --update
```

Optional führt ein post-commit-Hook den Graphen automatisch nach:

```bash
graphify hook install
```

## Obsidian

Den Vault-Ordner in Obsidian über *Open folder as vault* öffnen. Die Notizen
sind über Wikilinks verbunden, `graph.canvas` legt die erkannten Gruppen als
benanntes Canvas an.

Empfohlene Ablage, damit Generiertes und Handgeschriebenes getrennt bleiben:

```
<vault>/
  graphify/
    sportfabrik-inventory/   <- von --obsidian-dir befuellt, generiert
  sportfabrik-inventory/     <- eigene Notizen, handgeschrieben
```

Der generierte Teil wird bei jedem Lauf überschrieben — dort nichts von Hand
hineinschreiben, was erhalten bleiben soll.

## Grenzen

- Der Graph ist eine Momentaufnahme des letzten lokalen Laufs. **Bei Widerspruch
  gilt immer der Quellcode.**
- Cloud-Sessions haben weder die CLI noch den Graphen und lesen den Code direkt.
- Die Flags oben gelten für die Slash-Form (`/graphify` in Claude Code); die
  Terminal-Variante heisst `graphify extract`. Graphify steht bei Version 0.9.x,
  die Flags können sich ändern — im Zweifel `graphify --help`.
