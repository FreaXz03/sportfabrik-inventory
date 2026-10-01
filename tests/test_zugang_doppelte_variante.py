"""Two positions of one document can hold the same variant (the supplier lists
it twice). Booking both in one transaction must add up, not collide on the
`bestand` primary key (found 2026-10-01 with a real CMP confirmation)."""

from decimal import Decimal

from conftest import neue_datenbank
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.core.models import Artikel, Bestand, Lagerbewegung, Lagerort, Variante
from datetime import date, datetime, timezone

from app.services.wareneingang import buche_zugang


def test_same_variant_twice_in_one_transaction_adds_up():
    # Like production (`SessionLocal`): no autoflush.
    sessions = sessionmaker(neue_datenbank().kw["bind"], autoflush=False, expire_on_commit=False)
    with sessions.begin() as session:
        artikel = Artikel(bezeichnung="Jacket")
        session.add(artikel)
        session.flush()
        variante = Variante(artikel_id=artikel.id, farbe="Teak", groesse="54")
        session.add(variante)
        lagerort_id = session.scalar(select(Lagerort.id).where(Lagerort.code == "SF1"))
        session.flush()
        varianten_id = variante.id
        for menge in ("4", "8"):
            buche_zugang(
                session,
                lagerort_id=lagerort_id,
                varianten_id=varianten_id,
                position_id=None,
                menge=Decimal(menge),
                eingangsdatum=date(2026, 10, 1),
                benutzer=None,
                zeitpunkt=datetime.now(timezone.utc),
            )
    with sessions() as session:
        assert session.get(Bestand, (varianten_id, lagerort_id)).menge == Decimal("12")
        assert session.scalar(select(func.count()).select_from(Lagerbewegung)) == 2
