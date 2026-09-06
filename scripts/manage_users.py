"""Kommandozeilen-Werkzeug zur Benutzerverwaltung (Kassennummern, Chef-Konten).

Beispiele:
    python scripts/manage_users.py list
    python scripts/manage_users.py add-mitarbeiter 910141 "Anna Muster"
    python scripts/manage_users.py add-chef 910199 "Fabian Morf"
    python scripts/manage_users.py set-password 910199
    python scripts/manage_users.py remove 910141
"""
import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.core.models import User  # noqa: E402
from app.core.security import hash_password  # noqa: E402


def read_password() -> str:
    while True:
        password = getpass.getpass("Passwort: ")
        if len(password) < 6:
            print("Mindestens 6 Zeichen. Bitte erneut.")
            continue
        if getpass.getpass("Passwort wiederholen: ") != password:
            print("Passwörter stimmen nicht überein. Bitte erneut.")
            continue
        return password


def cmd_list(args):
    with SessionLocal() as session:
        users = session.scalars(select(User).order_by(User.role, User.kassennummer)).all()
        if not users:
            print("Noch keine Benutzer angelegt.")
            return
        for user in users:
            print(f"{user.kassennummer}	{user.role:<12}	{user.name or '(kein Name)'}")


def cmd_add_mitarbeiter(args):
    with SessionLocal() as session, session.begin():
        if session.scalar(select(User).where(User.kassennummer == args.kassennummer)):
            print(f"Kassennummer {args.kassennummer} existiert bereits.")
            return
        session.add(User(kassennummer=args.kassennummer, name=args.name, role="mitarbeiter", password_hash=None))
    print(f"Mitarbeiter {args.kassennummer} ({args.name}) angelegt. Anmeldung nur mit Kassennummer, kein Passwort.")


def cmd_add_chef(args):
    with SessionLocal() as session, session.begin():
        if session.scalar(select(User).where(User.kassennummer == args.kassennummer)):
            print(f"Kassennummer {args.kassennummer} existiert bereits.")
            return
        password = read_password()
        session.add(User(kassennummer=args.kassennummer, name=args.name, role="chef",
                          password_hash=hash_password(password)))
    print(f"Chef-Konto {args.kassennummer} ({args.name}) angelegt.")


def cmd_set_password(args):
    with SessionLocal() as session, session.begin():
        user = session.scalar(select(User).where(User.kassennummer == args.kassennummer))
        if user is None:
            print(f"Kassennummer {args.kassennummer} nicht gefunden.")
            return
        if user.role != "chef":
            print(f"{args.kassennummer} ist kein Chef-Konto (Mitarbeiter melden sich ohne Passwort an).")
            return
        user.password_hash = hash_password(read_password())
    print(f"Passwort für {args.kassennummer} aktualisiert.")


def cmd_remove(args):
    with SessionLocal() as session, session.begin():
        user = session.scalar(select(User).where(User.kassennummer == args.kassennummer))
        if user is None:
            print(f"Kassennummer {args.kassennummer} nicht gefunden.")
            return
        if not args.yes:
            confirm = input(f"{user.kassennummer} ({user.name}, {user.role}) wirklich löschen? [j/N] ")
            if confirm.strip().lower() not in ("j", "ja", "y", "yes"):
                print("Abgebrochen.")
                return
        session.delete(user)
    print(f"{args.kassennummer} entfernt.")


def main():
    parser = argparse.ArgumentParser(description="Benutzerverwaltung Sportfabrik Inventory")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="Alle Benutzer auflisten").set_defaults(func=cmd_list)

    p = sub.add_parser("add-mitarbeiter", help="Mitarbeiter anlegen (Anmeldung nur mit Kassennummer)")
    p.add_argument("kassennummer")
    p.add_argument("name")
    p.set_defaults(func=cmd_add_mitarbeiter)

    p = sub.add_parser("add-chef", help="Chef-Konto anlegen (Anmeldung mit Kassennummer + Passwort)")
    p.add_argument("kassennummer")
    p.add_argument("name")
    p.set_defaults(func=cmd_add_chef)

    p = sub.add_parser("set-password", help="Passwort eines Chef-Kontos zurücksetzen")
    p.add_argument("kassennummer")
    p.set_defaults(func=cmd_set_password)

    p = sub.add_parser("remove", help="Benutzer entfernen")
    p.add_argument("kassennummer")
    p.add_argument("--yes", action="store_true", help="Ohne Rückfrage löschen")
    p.set_defaults(func=cmd_remove)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
