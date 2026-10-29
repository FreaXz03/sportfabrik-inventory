"""Replacing a cancelled delivery preserves history and variant identities."""
import hashlib
from decimal import Decimal
import pytest
from sqlalchemy import select,func
from conftest import neue_datenbank
from test_intersport_delivery import delivery_with_barcode
from app.core.models import Dokument,Lagerort,Variante,Bestand,Wareneingang,WareneingangPosition
from app.services import importer
from app.services.beleg_storno import storniere_dokument


def test_cancelled_reimport_backfills_eans_without_duplicate_variants(monkeypatch):
    sessions=neue_datenbank()
    pdf=delivery_with_barcode();digest=hashlib.sha256(pdf).hexdigest()
    with sessions() as s:
        location=s.scalar(select(Lagerort.id).where(Lagerort.code=='SF1'))
    original=importer.parse_with_parser
    def legacy(*args,**kwargs):
        result=original(*args,**kwargs)
        for row in result['items']: row['ean']=''
        return result
    monkeypatch.setattr(importer,'parse_with_parser',legacy)
    first=importer.import_invoice(pdf,'test.pdf',digest,sessions,location)
    storniere_dokument(first['invoice_id'],sessions)
    monkeypatch.setattr(importer,'parse_with_parser',original)
    with pytest.raises(importer.ImportRejected):
        importer.import_invoice(pdf,'test.pdf',digest,sessions,location,replace_cancelled_id=999999)
    with pytest.raises(importer.ImportRejected):
        importer.import_invoice(pdf,'test.pdf',digest,sessions,location+1,replace_cancelled_id=first['invoice_id'])
    second=importer.import_invoice(pdf,'test.pdf',digest,sessions,location,
        lieferung='neu',replace_cancelled_id=first['invoice_id'])
    with sessions() as s:
        assert s.get(Dokument,first['invoice_id']).status=='storniert'
        replacement=s.get(Dokument,second['invoice_id'])
        assert replacement.status=='aktiv'
        assert replacement.ersetzt_dokument_id==first['invoice_id']
        assert s.scalar(select(func.count()).select_from(Variante))==1
        assert s.scalar(select(Variante.ean))=='4065419735048'
        assert s.scalar(select(func.sum(Bestand.menge)))==Decimal('8')
    with pytest.raises(importer.ImportRejected):
        importer.import_invoice(pdf,'test.pdf',digest,sessions,location,
            lieferung='neu',replace_cancelled_id=first['invoice_id'])
    storniere_dokument(second['invoice_id'],sessions)
    with sessions() as s:
        assert s.scalar(select(func.sum(Bestand.menge)))==0
