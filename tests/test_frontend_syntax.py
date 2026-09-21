"""Alle <script>-Bloecke einer Seite (inline + eigene /static/js/-Dateien)
teilen sich im Browser denselben Top-Level-Scope fuer let/const - ein Name,
der in zwei Blöcken auf derselben Seite top-level deklariert wird (z.B.
`const t = ...` gegen ein bestehendes `var t = ...`), wirft einen
SyntaxError, der den ganzen Block lautlos lahmlegt (siehe Vorfall: die
Uebersichtsseite blieb bei "Uebersicht wird geladen ..." haengen, weil der
frühe Theme-Snippet `var t` mit dem neu hinzugefuegten `const t` im
Dashboard-Skript kollidierte). pytest allein prueft kein JavaScript, daher
hier ein Node-Syntaxcheck ueber die tatsaechliche Skript-Reihenfolge jeder
Seite, wie sie ein Browser sehen wuerde."""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "app" / "templates"
STATIC_JS = ROOT / "app" / "static" / "js"

_SCRIPT_TAG = re.compile(r"<script\b([^>]*)>(.*?)</script>", re.S | re.I)
_SRC_ATTR = re.compile(r"""src=["']([^"']+)["']""")


def _page_scripts_in_order(html_path: Path) -> list[str]:
    """Bodies aller <script>-Bloecke einer Seite in Dokumentreihenfolge:
    fuer src="/static/js/..." der Dateiinhalt, sonst der Inline-Text."""
    html = html_path.read_text(encoding="utf-8")
    scripts = []
    for attrs, inline_body in _SCRIPT_TAG.findall(html):
        src_match = _SRC_ATTR.search(attrs)
        if src_match:
            src = src_match.group(1).split("?")[0]
            if not src.startswith("/static/js/"):
                continue  # externe Skripte (z.B. login-redirect.js) hier nicht relevant
            js_path = ROOT / "app" / src.lstrip("/")
            scripts.append(js_path.read_text(encoding="utf-8"))
        elif inline_body.strip():
            scripts.append(inline_body)
    return scripts


@pytest.mark.parametrize("html_file", sorted(TEMPLATES.glob("*.html")), ids=lambda p: p.name)
def test_page_scripts_share_scope_without_redeclaration(html_file):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required")
    scripts = _page_scripts_in_order(html_file)
    if not scripts:
        pytest.skip(f"{html_file.name} enthaelt keine Skripte")
    # Wie im Browser: alle Bloecke nacheinander im selben Top-Level-Scope.
    combined = "\n;\n".join(scripts)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as tmp:
        tmp.write(combined)
        tmp_path = tmp.name
    try:
        result = subprocess.run(
            [node, "--check", tmp_path],
            capture_output=True,
            timeout=15,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    assert result.returncode == 0, (
        f"Skript-Kollision auf {html_file.name} (geteilter Top-Level-Scope "
        f"aller <script>-Bloecke der Seite):\n{result.stderr.decode()}"
    )
