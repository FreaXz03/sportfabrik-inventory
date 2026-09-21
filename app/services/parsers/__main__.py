"""Lieferantendokument auf der Kommandozeile als JSON-Vorschau auslesen -
Hilfsmittel für die Entwicklung neuer Parser (vorher: `python
app/services/parser.py`):

    python -m app.services.parsers rechnung.pdf [--output vorschau.json]

Das Layout wird automatisch erkannt; ein unbekanntes Layout meldet
`UnknownLayoutError` (siehe `__init__.py`).
"""

from pathlib import Path
import argparse
import json

from . import parse_document

cli = argparse.ArgumentParser(
    description="Lieferantendokument als JSON-Vorschau auslesen (Layout wird erkannt)"
)
cli.add_argument("pdf", type=Path)
cli.add_argument("--output", type=Path)
args = cli.parse_args()
result = json.dumps(parse_document(args.pdf.read_bytes()), ensure_ascii=False, indent=2)
if args.output:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result, encoding="utf-8")
else:
    print(result)
