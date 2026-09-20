"""Lagerorte-Seed-Daten (SF1-SF4 + GEWA) und die Zuordnungslogik in
app/services/lagerorte.py (Filialwechsel, Rechte gemäss Regel 9)."""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.lagerorte import LAGERORTE_SEED, seed_lagerorte
from app.core.models import Base, BenutzerLagerort, Lagerort, User
from app.services.lagerorte import (
    get_primary_lagerort,
    list_all_lagerorte,
    list_user_lagerorte,
)


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with sessionmaker(engine).begin() as s:
        yield s


def test_seed_creates_five_lagerorte_with_expected_codes(session):
    seed_lagerorte(session)
    session.flush()
    codes = {lo.code for lo in session.scalars(select(Lagerort)).all()}
    assert codes == {"SF1", "SF2", "SF3", "SF4", "GEWA"}


def test_gewa_has_no_verkauf_filialen_have_verkauf(session):
    seed_lagerorte(session)
    session.flush()
    by_code = {lo.code: lo for lo in session.scalars(select(Lagerort)).all()}
    assert by_code["GEWA"].verkauf is False
    for code in ("SF1", "SF2", "SF3", "SF4"):
        assert by_code[code].verkauf is True


def test_seed_is_idempotent(session):
    seed_lagerorte(session)
    session.flush()
    seed_lagerorte(session)
    session.flush()
    assert session.scalar(select(Lagerort).where(Lagerort.code == "SF1")) is not None
    count = len(session.scalars(select(Lagerort)).all())
    assert count == len(LAGERORTE_SEED)


def _make_user(session, role, kassennummer="1", password_hash=None):
    user = User(kassennummer=kassennummer, name="Test", role=role, password_hash=password_hash)
    session.add(user)
    session.flush()
    return user


def test_list_all_lagerorte_ordered_sf_then_gewa(session):
    seed_lagerorte(session)
    session.flush()
    assert [lo.code for lo in list_all_lagerorte(session)] == [
        "SF1",
        "SF2",
        "SF3",
        "SF4",
        "GEWA",
    ]


def test_admin_sees_all_lagerorte_and_has_no_primary(session):
    seed_lagerorte(session)
    session.flush()
    admin = _make_user(session, "admin", password_hash="x")
    assert [lo.code for lo in list_user_lagerorte(session, admin)] == [
        "SF1",
        "SF2",
        "SF3",
        "SF4",
        "GEWA",
    ]
    assert get_primary_lagerort(session, admin) is None


def test_mitarbeiter_sees_only_assigned_lagerorte(session):
    seed_lagerorte(session)
    session.flush()
    sf2 = session.scalar(select(Lagerort).where(Lagerort.code == "SF2"))
    mitarbeiter = _make_user(session, "mitarbeiter")
    session.add(
        BenutzerLagerort(user_id=mitarbeiter.id, lagerort_id=sf2.id, ist_primaer=True)
    )
    session.flush()
    assert [lo.code for lo in list_user_lagerorte(session, mitarbeiter)] == ["SF2"]
    assert get_primary_lagerort(session, mitarbeiter).code == "SF2"


def test_primary_lagerort_is_listed_first(session):
    seed_lagerorte(session)
    session.flush()
    sf1 = session.scalar(select(Lagerort).where(Lagerort.code == "SF1"))
    sf4 = session.scalar(select(Lagerort).where(Lagerort.code == "SF4"))
    user = _make_user(session, "chef", password_hash="x")
    session.add(BenutzerLagerort(user_id=user.id, lagerort_id=sf1.id, ist_primaer=False))
    session.add(BenutzerLagerort(user_id=user.id, lagerort_id=sf4.id, ist_primaer=True))
    session.flush()
    assert [lo.code for lo in list_user_lagerorte(session, user)] == ["SF4", "SF1"]
    assert get_primary_lagerort(session, user).code == "SF4"


def test_user_without_assignment_has_no_primary_lagerort(session):
    seed_lagerorte(session)
    session.flush()
    mitarbeiter = _make_user(session, "mitarbeiter")
    assert list_user_lagerorte(session, mitarbeiter) == []
    assert get_primary_lagerort(session, mitarbeiter) is None
