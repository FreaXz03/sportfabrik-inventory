"""Create verified local backups of the Docker DB and original PDFs."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def backup(external=None):
    docker = shutil.which("docker")
    if not docker:
        candidate = (
            Path.home()
            / "AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe"
        )
        if candidate.is_file():
            docker = str(candidate)
    if not docker:
        raise RuntimeError("Docker-Befehl fehlt.")
    destination = ROOT / "backups" / "automatic"
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    final = destination / ("inventory-" + stamp)
    command = [
        docker,
        "compose",
        "--env-file",
        str(ROOT / ".env.server"),
        "exec",
        "-T",
        "db",
    ]
    # A directory is published only after every local verification succeeds.
    with tempfile.TemporaryDirectory(prefix=".pending-", dir=destination) as temporary:
        folder = Path(temporary)
        dump = folder / "database.dump"
        with dump.open("wb") as output:
            result = subprocess.run(
                command + ["pg_dump", "-U", "inventory", "-d", "inventory_db", "-Fc"],
                cwd=ROOT,
                stdout=output,
                stderr=subprocess.PIPE,
                timeout=1800,
            )
        if result.returncode or dump.stat().st_size == 0:
            raise RuntimeError(
                "Datenbanksicherung fehlgeschlagen: "
                + result.stderr.decode(errors="replace")
            )
        with dump.open("rb") as source:
            result = subprocess.run(
                command + ["pg_restore", "--list"],
                cwd=ROOT,
                stdin=source,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120,
            )
        if result.returncode or b"TABLE DATA" not in result.stdout:
            raise RuntimeError("Das Datenbankarchiv konnte nicht validiert werden.")
        (folder / "archive-contents.txt").write_bytes(result.stdout)
        pdf_count = 0
        with zipfile.ZipFile(
            folder / "original-pdfs.zip", "w", zipfile.ZIP_DEFLATED
        ) as archive:
            for directory in ("Recchnungen", "uploads"):
                base = ROOT / directory
                if base.is_dir():
                    for path in sorted(base.rglob("*.pdf")):
                        if path.is_symlink() or not path.resolve().is_relative_to(
                            base.resolve()
                        ):
                            continue
                        archive.write(path, path.relative_to(ROOT).as_posix())
                        pdf_count += 1
        with zipfile.ZipFile(folder / "original-pdfs.zip") as archive:
            if archive.testzip() is not None:
                raise RuntimeError("PDF-Archivprüfung fehlgeschlagen.")
        hashes = {
            path.name: sha256(path) for path in folder.iterdir() if path.is_file()
        }
        manifest = {
            "created_utc": stamp,
            "database": "inventory_db",
            "pdf_count": pdf_count,
            "sha256": hashes,
            "validation": "pg_restore --list and ZIP CRC; no full restore performed",
        }
        (folder / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        folder.rename(final)
    if external:
        target_root = Path(external)
        if not target_root.is_dir():
            raise RuntimeError(
                f"Lokales Backup gespeichert: {final}. Externes Ziel nicht erreichbar."
            )
        target = target_root / final.name
        try:
            shutil.copytree(final, target)
            for name, digest in hashes.items():
                if sha256(target / name) != digest:
                    raise RuntimeError("Prüfsumme der externen Kopie stimmt nicht.")
            if sha256(target / "manifest.json") != sha256(final / "manifest.json"):
                raise RuntimeError("Manifest der externen Kopie stimmt nicht.")
        except Exception as exc:
            raise RuntimeError(
                f"Lokales Backup gespeichert: {final}. Externe Kopie fehlgeschlagen: {exc}"
            ) from exc
    return {
        "backup": str(final),
        "pdf_count": pdf_count,
        "external_copy": bool(external),
    }


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--external", type=Path, help="Existing external backup directory")
    args = cli.parse_args()
    try:
        print(json.dumps(backup(args.external), ensure_ascii=False))
    except Exception as exc:
        raise SystemExit(str(exc))
