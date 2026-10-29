"""Create verified local backups of the Docker DB and original PDFs.

The copy for the external drive is always encrypted with age (security S4,
decision 2026-09-29): only the public key (recipient, `age1...`) is on the
server, in `backup-age-recipient.txt` or via `--recipient`. The private key
stays on a USB stick and on paper - see docs/BACKUPS.md for restoring.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RECIPIENT_FILE = ROOT / "backup-age-recipient.txt"
AGE_RECIPIENT = re.compile(r"age1[0-9a-z]{58}")
AGE_HEADER = b"age-encryption.org/v1"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_recipient(value=None):
    """Public age key from `--recipient` or `backup-age-recipient.txt`."""
    if value:
        return value.strip()
    if RECIPIENT_FILE.is_file():
        for line in RECIPIENT_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return line
    return None


def externe_kopie(final, target_root, recipient, age):
    """Encrypt the finished backup folder into one `.tar.age` file and copy
    it to the external drive, verified by checksum. Never writes anything
    unencrypted to the drive. Returns the path of the encrypted file."""
    if not recipient or not AGE_RECIPIENT.fullmatch(recipient):
        raise RuntimeError(
            "Kein gültiger öffentlicher age-Schlüssel (backup-age-recipient.txt oder --recipient)."
        )
    if not age:
        raise RuntimeError("Das Programm age fehlt (Installation: docs/BACKUPS.md).")
    target_root = Path(target_root)
    if not target_root.is_dir():
        raise RuntimeError("Externes Ziel nicht erreichbar.")
    name = final.name + ".tar.age"
    with tempfile.TemporaryDirectory(prefix=".encrypt-", dir=final.parent) as temporary:
        archive = Path(temporary) / (final.name + ".tar")
        with tarfile.open(archive, "w") as tar:
            tar.add(final, arcname=final.name)
        encrypted = Path(temporary) / name
        result = subprocess.run(
            [age, "-r", recipient, "-o", str(encrypted), str(archive)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=1800,
        )
        if result.returncode or not encrypted.is_file():
            raise RuntimeError(
                "Verschlüsselung fehlgeschlagen: " + result.stderr.decode(errors="replace")
            )
        with encrypted.open("rb") as stream:
            if not stream.read(len(AGE_HEADER)) == AGE_HEADER:
                raise RuntimeError("Die verschlüsselte Datei ist keine age-Datei.")
        digest = sha256(encrypted)
        partial = target_root / (name + ".partial")
        shutil.copyfile(encrypted, partial)
        if sha256(partial) != digest:
            partial.unlink(missing_ok=True)
            raise RuntimeError("Prüfsumme der externen Kopie stimmt nicht.")
        target = target_root / name
        partial.rename(target)
    (target_root / (name + ".sha256")).write_text(f"{digest}  {name}\n", encoding="utf-8")
    return target


def backup(external=None, recipient=None):
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
    external_file = None
    if external:
        try:
            external_file = externe_kopie(
                final, external, load_recipient(recipient), shutil.which("age")
            )
        except Exception as exc:
            raise RuntimeError(
                f"Lokales Backup gespeichert: {final}. Externe Kopie fehlgeschlagen: {exc}"
            ) from exc
    return {
        "backup": str(final),
        "pdf_count": pdf_count,
        "external_copy": None if external_file is None else str(external_file),
    }


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--external", type=Path, help="Existing external backup directory")
    cli.add_argument("--recipient", help="Public age key (age1...) for the external copy")
    args = cli.parse_args()
    try:
        print(json.dumps(backup(args.external, args.recipient), ensure_ascii=False))
    except Exception as exc:
        raise SystemExit(str(exc))
