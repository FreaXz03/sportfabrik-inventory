"""Strict row identity checks for an explicitly requested cancelled replacement."""
from decimal import Decimal
from sqlalchemy import select
from ..core.models import Dokument,Wareneingang,WareneingangPosition,WareneingangPositionQuelle
from ..core.i18n import translate


def replacement_rows(session,document_id,digest,parsed,location,language):
    old=session.get(Dokument,document_id)
    if not old or old.status!='storniert' or old.datei_hash!=digest or old.dokumentnummer!=parsed['invoice_number'] or old.lagerort_id!=location:
        raise ValueError(translate('errors.importer.replacement_mismatch',language))
    records=session.execute(select(WareneingangPosition,WareneingangPositionQuelle.data)
        .join(Wareneingang,Wareneingang.id==WareneingangPosition.wareneingang_id)
        .join(WareneingangPositionQuelle,WareneingangPositionQuelle.position_id==WareneingangPosition.id)
        .where(Wareneingang.dokument_id==document_id)).all()
    mapping={data['row_number']:(pos,data) for pos,data in records}
    if len(mapping)!=len(records) or set(mapping)!={i['row_number'] for i in parsed['items']}:
        raise ValueError(translate('errors.importer.replacement_rows_changed',language))
    for item in parsed['items']:
        pos,data=mapping[item['row_number']]
        if (Decimal(item['quantity'] or '0')!=pos.menge or item['page']!=data.get('page')
            or abs(item['source_y']-data.get('source_y',-999))>.5):
            raise ValueError(translate('errors.importer.replacement_rows_changed',language))
    return mapping
