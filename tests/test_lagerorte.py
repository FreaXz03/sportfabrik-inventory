"""Lagerorte-Seed-Daten (SF1-SF4 plus die externen Standorte GEWA, VEBO und
Lager Dietikon) und die Zuordnungslogik in app/services/lagerorte.py
(Filialwechsel, Rechte gemäss Regel 9)."""

import importlib.util
import pathlib

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


ALLE_CODES = ["SF1", "SF2", "SF3", "SF4", "GEWA", "VEBO", "DIETIKON"]
# Externe Standorte ohne Verkauf: die Verarbeitungsstellen GEWA und VEBO
# sowie das Lager Dietikon (Regel 6 - dort startet die Reduktionsuhr nicht).
OHNE_VERKAUF = ["GEWA", "VEBO", "DIETIKON"]


def test_seed_creates_expected_codes(session):
    seed_lagerorte(session)
    session.flush()
    codes = {lo.code for lo in session.scalars(select(Lagerort)).all()}
    assert codes == set(ALLE_CODES)


def test_seed_maps_every_code_to_the_right_branch():
    """Die Zuordnung war bis zum 22.09.2026 falsch (SF2 Regensdorf,
    SF3 Hägendorf, SF4 Conthey). Bestätigt ist die Reihenfolge hier - ein
    echter Beleg nennt ebenfalls „SF3 Regensdorf" (ALPINA 160166)."""
    orte = {e["code"]: e["ort"] for e in LAGERORTE_SEED}
    assert orte["SF1"] == "Volketswil"
    assert orte["SF2"] == "Conthey"
    assert orte["SF3"] == "Regensdorf"
    assert orte["SF4"] == "Hägendorf"


def test_only_filialen_have_verkauf(session):
    seed_lagerorte(session)
    session.flush()
    by_code = {lo.code: lo for lo in session.scalars(select(Lagerort)).all()}
    for code in OHNE_VERKAUF:
        assert by_code[code].verkauf is False, code
    for code in ("SF1", "SF2", "SF3", "SF4"):
        assert by_code[code].verkauf is True, code


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


def test_list_all_lagerorte_lists_filialen_before_externe(session):
    seed_lagerorte(session)
    session.flush()
    assert [lo.code for lo in list_all_lagerorte(session)] == ALLE_CODES


def test_admin_sees_all_lagerorte_and_has_no_primary(session):
    seed_lagerorte(session)
    session.flush()
    admin = _make_user(session, "admin", password_hash="x")
    assert [lo.code for lo in list_user_lagerorte(session, admin)] == ALLE_CODES
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
# --- Migration d0e1f2a3b4c5: Filialcodes korrigieren -----------------------

MIGRATION = (
    pathlib.Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "d0e1f2a3b4c5_filialcodes_korrigieren.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location("filialcodes_migration", MIGRATION)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_migration_und_seed_meinen_dasselbe():
    """Migration und Seed dürfen nicht auseinanderlaufen: beide beschreiben,
    welche Filiale welchen Code trägt."""
    aus_seed = {e["ort"]: e["code"] for e in LAGERORTE_SEED if e["code"] in ("SF2", "SF3", "SF4")}
    assert _migration().RICHTIG == aus_seed


def test_migration_dreht_die_codes_im_ring(session):
    """SF2 → SF3 → SF4 → SF2: weil `code` eindeutig ist, muss der Tausch über
    Zwischencodes laufen - sonst kollidiert die zweite Zeile mit dem Code, den
    die erste noch trägt. Der Ort bleibt, wo er ist, damit gebuchte Ware ihre
    Filiale behält."""
    mig = _migration()
    vorher = {"Regensdorf": "SF2", "Hägendorf": "SF3", "Conthey": "SF4"}
    for ort, code in vorher.items():
        session.add(Lagerort(code=code, name=ort, ort=ort))
    session.flush()

    mig._codes_setzen(session.connection(), mig.RICHTIG)
    session.expire_all()
    assert {lo.ort: lo.code for lo in session.scalars(select(Lagerort)).all()} == {
        "Conthey": "SF2",
        "Regensdorf": "SF3",
        "Hägendorf": "SF4",
    }

    mig._codes_setzen(session.connection(), mig.VORHER)
    session.expire_all()
    assert {lo.ort: lo.code for lo in session.scalars(select(Lagerort)).all()} == vorher
