"""Kontoverwaltung (Anforderung 13, 24./25.09.2026): die Zentrale legt Konten
an und löscht sie - Mitarbeiter und Filialleiter, nicht sich selbst.

Wird ein Konto gelöscht, bleiben alle Buchungen in der Datenbank (Regel: sie
speichern Kassennummer/Name als Momentaufnahme, keine Fremdschlüssel auf
`users`, siehe z.B. `Lagerbewegung.benutzer_name`) - nur die Verknüpfung
`benutzer_lagerorte` entfällt (Entscheid 24.09.2026).
"""

from sqlalchemy import select

from ..core.models import BenutzerLagerort, Lagerort, User
from ..core.security import hash_password

ROLLEN = ("mitarbeiter", "chef", "admin")
MINDEST_PASSWORTLAENGE = 6


class KontoRejected(ValueError):
    """Ungültige Eingabe - nichts wurde gespeichert."""


class KontoDuplicate(ValueError):
    """Kassennummer schon vergeben."""


class KontoSelbstloeschung(ValueError):
    """Das eigene Konto lässt sich nicht selbst löschen."""


def _konto_daten(user: User, lagerort_ids: list[int]) -> dict:
    return {
        "id": user.id,
        "kassennummer": user.kassennummer,
        "name": user.name,
        "role": user.role,
        "lagerort_ids": sorted(lagerort_ids),
    }


def liste(session) -> list[dict]:
    zeilen = session.execute(
        select(User, BenutzerLagerort.lagerort_id)
        .outerjoin(BenutzerLagerort, BenutzerLagerort.user_id == User.id)
        .order_by(User.role.desc(), User.name)
    ).all()
    je_konto: dict[int, dict] = {}
    for user, lagerort_id in zeilen:
        eintrag = je_konto.setdefault(user.id, _konto_daten(user, []))
        if lagerort_id is not None:
            eintrag["lagerort_ids"].append(lagerort_id)
    for eintrag in je_konto.values():
        eintrag["lagerort_ids"].sort()
    return list(je_konto.values())


def anlegen(
    session,
    *,
    kassennummer: str,
    name: str,
    role: str,
    password: str | None,
    lagerort_ids: list[int],
) -> dict:
    kassennummer = (kassennummer or "").strip()
    name = (name or "").strip()
    if not kassennummer or not name:
        raise KontoRejected("Kassennummer und Name sind Pflicht.")
    if role not in ROLLEN:
        raise KontoRejected(f"Rolle muss eine von {', '.join(ROLLEN)} sein.")

    braucht_passwort = role in ("chef", "admin")
    if braucht_passwort:
        if not password or len(password) < MINDEST_PASSWORTLAENGE:
            raise KontoRejected(
                f"Filialleiter/Zentrale brauchen ein Passwort mit mindestens {MINDEST_PASSWORTLAENGE} Zeichen."
            )
    elif password:
        raise KontoRejected("Mitarbeiterkonten haben kein Passwort.")

    lagerort_ids = list(dict.fromkeys(lagerort_ids or []))
    if role != "admin" and not lagerort_ids:
        raise KontoRejected("Mitarbeiter und Filialleiter brauchen mindestens eine Filiale.")
    if role == "admin":
        lagerort_ids = []
    else:
        bekannt = set(
            session.scalars(select(Lagerort.id).where(Lagerort.id.in_(lagerort_ids)))
        )
        if bekannt != set(lagerort_ids):
            raise KontoRejected("Unbekannter Lagerort.")

    if session.scalar(select(User.id).where(User.kassennummer == kassennummer)) is not None:
        raise KontoDuplicate(kassennummer)

    user = User(
        kassennummer=kassennummer,
        name=name,
        role=role,
        password_hash=hash_password(password) if braucht_passwort else None,
    )
    session.add(user)
    session.flush()
    for index, lagerort_id in enumerate(lagerort_ids):
        session.add(
            BenutzerLagerort(user_id=user.id, lagerort_id=lagerort_id, ist_primaer=index == 0)
        )
    session.commit()
    return _konto_daten(user, lagerort_ids)


def loeschen(session, user_id: int, aktueller_benutzer: User) -> None:
    if user_id == aktueller_benutzer.id:
        raise KontoSelbstloeschung(user_id)
    user = session.get(User, user_id)
    if user is None:
        return
    session.execute(
        BenutzerLagerort.__table__.delete().where(BenutzerLagerort.user_id == user_id)
    )
    session.delete(user)
    session.commit()
