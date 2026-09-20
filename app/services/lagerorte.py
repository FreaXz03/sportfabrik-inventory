"""Lesezugriffe auf Lagerorte und die Filialzuordnung von Benutzern
(m:n `benutzer_lagerorte`). Admin-Konten haben keine Zuordnung, gelten aber
als filialübergreifend (Regel 9: Zugriff auf alle Lagerorte)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.models import BenutzerLagerort, Lagerort, User

_CODE_ORDER = {"SF1": 0, "SF2": 1, "SF3": 2, "SF4": 3, "GEWA": 4}


def _sort_key(lagerort: Lagerort) -> tuple:
    return (_CODE_ORDER.get(lagerort.code, 99), lagerort.code)


def list_all_lagerorte(session: Session) -> list[Lagerort]:
    return sorted(session.scalars(select(Lagerort)).all(), key=_sort_key)


def list_user_lagerorte(session: Session, user: User) -> list[Lagerort]:
    """Lagerorte, zwischen denen der Benutzer wechseln darf: Admin alle, sonst
    die über benutzer_lagerorte zugewiesenen (primäre zuerst)."""
    if user.role == "admin":
        return list_all_lagerorte(session)
    rows = session.execute(
        select(Lagerort, BenutzerLagerort.ist_primaer)
        .join(BenutzerLagerort, BenutzerLagerort.lagerort_id == Lagerort.id)
        .where(BenutzerLagerort.user_id == user.id)
    ).all()
    return [
        row[0]
        for row in sorted(rows, key=lambda row: (not row[1], _sort_key(row[0])))
    ]


def get_primary_lagerort(session: Session, user: User) -> Lagerort | None:
    """Die nach dem Login vorausgewählte Filiale. None für Admin (Ansicht
    „alle Filialen") oder falls dem Benutzer keine Filiale zugewiesen ist."""
    if user.role == "admin":
        return None
    assigned = list_user_lagerorte(session, user)
    return assigned[0] if assigned else None
