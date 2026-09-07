import os
from pathlib import Path
import shutil
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]


def migration_env():
    env = os.environ.copy()
    for key in (
        "DB_HOST",
        "DB_PASSWORD",
        "DB_PORT",
        "DB_NAME",
        "DB_USER",
        "DATABASE_URL",
    ):
        env.pop(key, None)
    return env


def test_container_url_offline_migrations():
    env = migration_env()
    env.update(
        DB_HOST="db",
        DB_PASSWORD="test@pass%with/slash:#",
        DB_USER="inventory",
        DB_NAME="inventory_db",
    )
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr.decode()
    assert b"CREATE TABLE users" in result.stdout
    assert b"ocr_used" in result.stdout


def test_online_migration_to_isolated_database(tmp_path):
    env = migration_env()
    env["DATABASE_URL"] = "sqlite:///" + (tmp_path / "migration.db").as_posix()
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr.decode()
    import sqlite3

    with sqlite3.connect(tmp_path / "migration.db") as db:
        assert "ocr_used" in [
            row[1] for row in db.execute("PRAGMA table_info(invoices)")
        ]
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()


def test_login_redirect_destinations():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for browser URL validation tests")
    script = (ROOT / "app/static/js/login-redirect.js").read_text(encoding="utf-8")
    script += r"""
const assert = require('node:assert/strict');
const origin = 'http://localhost:8080';
for (const input of [null, '', 'https://evil.example', '//evil.example',
    '/\\evil.example', 'javascript:alert(1)', '/static/js/theme.js',
    '/login?next=https://evil.example', '/%2f%2fevil.example', '/\tevil.example',
    ' /articles', '/api/invoices', '/unknown']) {
  assert.equal(safeLoginRedirect(input, origin), '/', String(input));
}
for (const input of ['/', '/articles', '/invoices', '/preview',
    '/invoices/123', '/articles/7/history', '/articles?q=Hoka#results']) {
  assert.equal(safeLoginRedirect(input, origin), input);
}
"""
    result = subprocess.run(
        [node, "-"], input=script.encode(), capture_output=True, timeout=15
    )
    assert result.returncode == 0, result.stderr.decode()
    html = (ROOT / "app/templates/login.html").read_text(encoding="utf-8")
    assert html.index('src="/static/js/login-redirect.js"') < html.index(
        "safeLoginRedirect(params"
    )
