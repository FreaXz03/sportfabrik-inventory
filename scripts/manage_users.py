"""Kommandozeilen-Werkzeug zur Benutzerverwaltung (Kassennummern, Filialleiter-
und Admin-Konten, Filialzuordnung).

Beispiele:
    python scripts/manage_users.py list
    python scripts/manage_users.py add-mitarbeiter 910141 "Anna Muster" SF1
    python scripts/manage_users.py add-mitarbeiter 910142 "Beat Aushilf" SF1 SF2
    python scripts/manage_users.py add-chef 910199 "Fabian Morf" SF1
    python scripts/manage_users.py add-admin 910100 "Zentrale"
    python scripts/manage_users.py set-lagerorte 910141 SF2 SF3
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
from app.core.models import BenutzerLagerort, Lagerort, User  # noqa: E402
from app.core.security import hash_password  # noqa: E402

ROLE_LABELS = {"mitarbeiter": "Mitarbeiter", "chef": "Filialleiter", "admin": "Admin/Zentrale"}


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


def _resolve_lagerorte(session, codes: list[str]) -> list[Lagerort]:
    lagerorte = []
    for code in codes:
        lagerort = session.scalar(select(Lagerort).where(Lagerort.code == code.upper()))
        if lagerort is None:
            raise SystemExit(
                f"Unbekannter Lagerort-Code '{code}'. Gültig: SF1, SF2, SF3, SF4, GEWA."
            )
        lagerorte.append(lagerort)
    return lagerorte


def _set_user_lagerorte(session, user: User, codes: list[str]) -> None:
    session.query(BenutzerLagerort).filter(
        BenutzerLagerort.user_id == user.id
    ).delete()
    for index, lagerort in enumerate(_resolve_lagerorte(session, codes)):
        session.add(
            BenutzerLagerort(
                user_id=user.id, lagerort_id=lagerort.id, ist_primaer=(index == 0)
            )
        )


def cmd_list(args):
    with SessionLocal() as session:
        users = session.scalars(
            select(User).order_by(User.role, User.kassennummer)
        ).all()
        if not users:
            print("Noch keine Benutzer angelegt.")
            return
        for user in users:
            zuordnungen = session.execute(
                select(Lagerort.code, BenutzerLagerort.ist_primaer)
                .join(BenutzerLagerort, BenutzerLagerort.lagerort_id == Lagerort.id)
                .where(BenutzerLagerort.user_id == user.id)
            ).all()
            filialen = ", ".join(
                code + ("*" if primaer else "") for code, primaer in zuordnungen
            ) or ("alle" if user.role == "admin" else "—")
            print(
                f"{user.kassennummer}\t{ROLE_LABELS.get(user.role, user.role):<15}\t"
                f"{user.name or '(kein Name)'}\t{filialen}"
            )


def cmd_add_mitarbeiter(args):
    with SessionLocal() as session, session.begin():
        if session.scalar(select(User).where(User.kassennummer == args.kassennummer)):
            print(f"Kassennummer {args.kassennummer} existiert bereits.")
            return
        if not args.lagerorte:
            raise SystemExit("Mindestens ein Lagerort-Code nötig, z.B. SF1.")
        user = User(
            kassennummer=args.kassennummer,
            name=args.name,
            role="mitarbeiter",
            password_hash=None,
        )
        session.add(user)
        session.flush()
        _set_user_lagerorte(session, user, args.lagerorte)
    print(
        f"Mitarbeiter {args.kassennummer} ({args.name}) angelegt für "
        f"{', '.join(c.upper() for c in args.lagerorte)}. Anmeldung nur mit Kassennummer."
    )


def cmd_add_chef(args):
    with SessionLocal() as session, session.begin():
        if session.scalar(select(User).where(User.kassennummer == args.kassennummer)):
            print(f"Kassennummer {args.kassennummer} existiert bereits.")
            return
        if not args.lagerorte:
            raise SystemExit("Mindestens ein Lagerort-Code nötig, z.B. SF1.")
        password = read_password()
        user = User(
            kassennummer=args.kassennummer,
            name=args.name,
            role="chef",
            password_hash=hash_password(password),
        )
        session.add(user)
        session.flush()
        _set_user_lagerorte(session, user, args.lagerorte)
    print(
        f"Filialleiter-Konto {args.kassennummer} ({args.name}) angelegt für "
        f"{', '.join(c.upper() for c in args.lagerorte)}."
    )


def cmd_add_admin(args):
    with SessionLocal() as session, session.begin():
        if session.scalar(select(User).where(User.kassennummer == args.kassennummer)):
            print(f"Kassennummer {args.kassennummer} existiert bereits.")
            return
        password = read_password()
        session.add(
            User(
                kassennummer=args.kassennummer,
                name=args.name,
                role="admin",
                password_hash=hash_password(password),
            )
        )
    print(
        f"Admin-Konto {args.kassennummer} ({args.name}) angelegt. "
        "Filialübergreifend, keine Lagerort-Zuordnung nötig."
    )


def cmd_set_lagerorte(args):
    with SessionLocal() as session, session.begin():
        user = session.scalar(
            select(User).where(User.kassennummer == args.kassennummer)
        )
        if user is None:
            print(f"Kassennummer {args.kassennummer} nicht gefunden.")
            return
        if user.role == "admin":
            print("Admin-Konten sind filialübergreifend, keine Zuordnung nötig.")
            return
        if not args.lagerorte:
            raise SystemExit("Mindestens ein Lagerort-Code nötig, z.B. SF1.")
        _set_user_lagerorte(session, user, args.lagerorte)
    print(
        f"Filialen für {args.kassennummer} gesetzt: "
        f"{', '.join(c.upper() for c in args.lagerorte)} (erste = primär)."
    )


def cmd_set_password(args):
    with SessionLocal() as session, session.begin():
        user = session.scalar(
            select(User).where(User.kassennummer == args.kassennummer)
        )
        if user is None:
            print(f"Kassennummer {args.kassennummer} nicht gefunden.")
            return
        if user.role not in ("chef", "admin"):
            print(
                f"{args.kassennummer} ist kein Filialleiter-/Admin-Konto "
                "(Mitarbeiter melden sich ohne Passwort an)."
            )
            return
        user.password_hash = hash_password(read_password())
    print(f"Passwort für {args.kassennummer} aktualisiert.")


def cmd_remove(args):
    with SessionLocal() as session, session.begin():
        user = session.scalar(
            select(User).where(User.kassennummer == args.kassennummer)
        )
        if user is None:
            print(f"Kassennummer {args.kassennummer} nicht gefunden.")
            return
        if not args.yes:
            confirm = input(
                f"{user.kassennummer} ({user.name}, {user.role}) wirklich löschen? [j/N] "
            )
            if confirm.strip().lower() not in ("j", "ja", "y", "yes"):
                print("Abgebrochen.")
                return
        session.query(BenutzerLagerort).filter(
            BenutzerLagerort.user_id == user.id
        ).delete()
        session.delete(user)
    print(f"{args.kassennummer} entfernt.")


def main():
    parser = argparse.ArgumentParser(
        description="Benutzerverwaltung Sportfabrik Inventory"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="Alle Benutzer auflisten").set_defaults(func=cmd_list)

    p = sub.add_parser(
        "add-mitarbeiter", help="Mitarbeiter anlegen (Anmeldung nur mit Kassennummer)"
    )
    p.add_argument("kassennummer")
    p.add_argument("name")
    p.add_argument("lagerorte", nargs="+", help="Lagerort-Codes, erster ist primär")
    p.set_defaults(func=cmd_add_mitarbeiter)

    p = sub.add_parser(
        "add-chef", help="Filialleiter-Konto anlegen (Anmeldung mit Kassennummer + Passwort)"
    )
    p.add_argument("kassennummer")
    p.add_argument("name")
    p.add_argument("lagerorte", nargs="+", help="Lagerort-Codes, erster ist primär")
    p.set_defaults(func=cmd_add_chef)

    p = sub.add_parser(
        "add-admin",
        help="Admin-/Zentrale-Konto anlegen (filialübergreifend, mit Passwort)",
    )
    p.add_argument("kassennummer")
    p.add_argument("name")
    p.set_defaults(func=cmd_add_admin)

    p = sub.add_parser(
        "set-lagerorte", help="Filialzuordnung eines Mitarbeiters/Filialleiters ersetzen"
    )
    p.add_argument("kassennummer")
    p.add_argument("lagerorte", nargs="+", help="Lagerort-Codes, erster ist primär")
    p.set_defaults(func=cmd_set_lagerorte)

    p = sub.add_parser(
        "set-password", help="Passwort eines Filialleiter-/Admin-Kontos zurücksetzen"
    )
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
