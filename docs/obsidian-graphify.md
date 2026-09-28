# Project Knowledge: Graphify and Obsidian

## Rule as of 2026-09-24

**`--code-only` is no longer a general requirement.** Code and explicitly selected project documentation may be processed by Graphify. The document selection lives in `docs/wissensquellen.txt`; `.graphifyignore` also limits direct project scans. Add new document sources deliberately to both lists.

No automatic processing of supplier documents, uploads, credentials, or personal vault areas. The deliberate release of individual documents for parser building remains a separate exception. In the finished inventory-management system, documents continue to be processed exclusively locally by our own parsers.

GitHub publication and processing by the AI provider are separate processes. The graph stays under the gitignored `graphify-out/`. A semantic run can still transmit content of the selected documents to the chosen AI provider and consume tokens. No blanket scan of the vault; no automatic semantic analysis after every commit.

## Everyday use: targeted lookup

```sh
python3 scripts/projektwissen.py query "Umlagerung"
python3 scripts/projektwissen.py query "reduktionen_manuell"
```

The tool builds a **structural document section index** locally from headings, short original excerpts, and explicit code paths. For the query, it connects this to the existing Graphify code graph and calls Graphify with a limited output budget. This is not a semantic AI analysis of the documents and not a complete model of all business relationships. After a hit, always check the relevant original section.

For this, the selected Markdown files are read locally; their full text is not output into the model context. The merged graph lives at `graphify-out/knowledge/graph.json`. It is regenerated on every query; the original code graph stays untouched. If it doesn't exist, the document index still works alone, with a notice. Handle missing/outdated code relationships with a targeted text search.

Read a known file directly. For targeted code relationships, `graphify explain "<function>"` and `graphify path "<A>" "<B>"` are also available on the original code graph. Never load the full graph.json into the chat.

## Updating

The existing Git hook continues to update only the code structure, locally and without a language model. This is a cheap piece of automation, not a limit on permitted document analysis. If needed: `graphify update .` (code update of the installed version); then `python3 scripts/projektwissen.py index`.

## Optional semantic document analysis

If the section index isn't enough for a specific question:

```sh
python3 scripts/projektwissen.py prepare-docs
# Only the explicit selection, do not scan the project or the vault:
graphify extract graphify-out/selected-docs/input --out graphify-out/selected-docs --no-gitignore --backend claude --max-concurrency 1 --token-budget 6000
```

`prepare-docs` builds a clean local input folder from the release list, without symlinks or extra files. `--no-gitignore` is only needed here because this prepared folder sits under the deliberately gitignored output folder; do not use it for arbitrary project scans. Before the AI run, the file list states the scope. The explicit provider prevents an unintended automatic provider choice; its local login/API configuration must be available. Don't start it automatically — only when a task justifies the extra semantic analysis.

The result stays as a separate document graph at `graphify-out/selected-docs/graphify-out/graph.json` and can be queried with `graphify query "<question>" --graph <path> --budget 1200`. Update it after document changes, before use. This does not replace the cheap default index, and the code hook does not overwrite this document graph.

## Obsidian and sources

- Main vault: own ideas, requirements, and an understandable overview.
- `docs/start.md`: current entry point and next priority.
- Technical documents in the project: their respective main source; update only the affected sections.
- Historical vault status copies: archive, not read on every task.
- Generated Sportfabrik graph: optional visual view, not an extra information source for Claude.

Export when needed, after `python3 scripts/projektwissen.py index`:

```sh
graphify export obsidian --graph graphify-out/knowledge/graph.json --dir graphify-out/Sportfabrik-Graph
```

Don't maintain handwritten notes in the generated area. Without a local graph (e.g. a cloud session), work directly with `rg` and targeted file excerpts.

## Sessions

After a completed task, a short handover: result, relevant files, open points. Start a new session for an unrelated task; condense long-running tasks when needed. Graphify replaces neither context upkeep nor checking the current code. A concrete token saving is only measurable through comparable sessions.
