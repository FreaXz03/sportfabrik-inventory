"""Atomic, duplicate-safe imports and deletions. Import: call only after explicit
preview confirmation. Deletion: chef-only, see app/auth.py."""
from datetime import datetime
from decimal import Decimal
import hashlib
import re

import pymupdf
from sqlalchemy import delete, func, select, or_, text
from sqlalchemy.exc import IntegrityError

from .models import Invoice, InvoiceItem, InvoiceItemSource, Product
from .parser import parse_invoice


class ImportRejected(ValueError):
    pass


class DeleteRejected(ValueError):
    pass


def invoice_dates(pdf):
    with pymupdf.open(stream=pdf, filetype='pdf') as doc:
        words = doc[0].get_text('words')
    result = {}
    for label, key in [('Rechnungsdatum', 'invoice_date'), ('Belegdatum', 'document_date')]:
        anchors = [w for w in words if w[4] == label]
        if len(anchors) != 1:
            raise ImportRejected(f'{label} nicht eindeutig erkannt.')
        anchor = anchors[0]
        candidates = [w[4] for w in words if w[0] > anchor[2] and abs(w[1]-anchor[1]) < 2
                      and re.fullmatch(r'\d{2}\.\d{2}\.\d{4}', w[4])]
        if len(candidates) != 1:
            raise ImportRejected(f'{label} fehlt oder ist mehrdeutig.')
        try:
            result[key] = datetime.strptime(candidates[0], '%d.%m.%Y').date()
        except ValueError as exc:
            raise ImportRejected(f'{label} ist ungültig.') from exc
    return result


def import_invoice(pdf, filename, expected_hash, session_factory, imported_by=None):
    digest = hashlib.sha256(pdf).hexdigest()
    if digest != expected_hash:
        raise ImportRejected('Die Datei stimmt nicht mit der geprüften Vorschau überein. Bitte Vorschau neu erstellen.')
    parsed = parse_invoice(pdf)
    if not parsed['invoice_number'] or parsed['warnings'] or parsed['rows_with_warnings']:
        raise ImportRejected('Import gesperrt: Rechnungsnummer fehlt oder die Vorschau enthält Warnungen.')
    dates = invoice_dates(pdf)
    for item in parsed['items']:
        for key, limit in [('brand',100), ('supplier_article_no',100), ('article_no',100),
                           ('ean',30), ('description',500), ('color',250), ('size',100), ('unit',30)]:
            if len(item.get(key) or '') > limit:
                raise ImportRejected(f'Position {item["row_number"]}: {key} ist zu lang.')
        for key in ('quantity','uvp'):
            value = Decimal(item[key])
            if abs(value) >= Decimal('100000000') or value != value.quantize(Decimal('.01')):
                raise ImportRejected(f'Position {item["row_number"]}: {key} passt nicht in das Datenbankformat.')
    try:
        with session_factory() as session, session.begin():
            # Serialize imports across all app workers on PostgreSQL, including
            # different invoices that introduce the same EAN concurrently.
            if session.bind.dialect.name == 'postgresql':
                session.execute(text('SELECT pg_advisory_xact_lock(73421061)'))
            existing = session.scalar(select(Invoice).where(or_(Invoice.file_hash == digest,
                Invoice.invoice_number == parsed['invoice_number'])))
            if existing:
                raise ImportRejected(f'Rechnung {existing.invoice_number} wurde bereits importiert (ID {existing.id}).')
            invoice = Invoice(invoice_number=parsed['invoice_number'], file_hash=digest,
                filename=(filename or 'rechnung.pdf')[:500], supplier='INTERSPORT Schweiz AG',
                imported_by_kassennummer=(imported_by or {}).get('kassennummer'),
                imported_by_name=(imported_by or {}).get('name'), **dates)
            session.add(invoice)
            session.flush()
            new_products, reused = 0, set()
            cache = {}
            for item in parsed['items']:
                ean = item['ean']
                product = cache.get(ean)
                if product is None:
                    product = session.scalar(select(Product).where(Product.ean == ean))
                    if product is None:
                        product = Product(**{key:item.get(key) for key in ('brand','supplier_article_no',
                            'article_no','ean','description','color','size')})
                        session.add(product)
                        session.flush()
                        new_products += 1
                    else:
                        reused.add(product.id)
                    cache[ean] = product
                seen = dates['invoice_date']
                product.first_seen = min(product.first_seen, seen) if product.first_seen else seen
                product.last_seen = max(product.last_seen, seen) if product.last_seen else seen
                position = InvoiceItem(invoice_id=invoice.id, product_id=product.id,
                    quantity=Decimal(item['quantity']), unit=item['unit'], uvp=Decimal(item['uvp']))
                session.add(position)
                session.flush()
                session.add(InvoiceItemSource(item_id=position.id, data=item))
            result = dict(invoice_id=invoice.id, invoice_number=invoice.invoice_number,
                item_count=parsed['item_count'], new_products=new_products, reused_products=len(reused))
        return result
    except IntegrityError as exc:
        raise ImportRejected('Datenkonflikt: Der Import wurde vollständig zurückgerollt. Bitte Vorschau erneut prüfen.') from exc


def delete_invoice(invoice_id: int, session_factory) -> dict:
    """Löscht eine Rechnung samt Positionen und Originaltexten unwiderruflich.

    Betroffene Artikel (first_seen/last_seen) werden aus den verbleibenden
    Lieferungen neu berechnet, statt veraltete Werte stehen zu lassen.
    """
    with session_factory() as session, session.begin():
        # Dieselbe Sperre wie beim Import: verhindert, dass ein gleichzeitiger
        # Import/Löschvorgang mit denselben Artikeln first_seen/last_seen falsch berechnet.
        if session.bind.dialect.name == 'postgresql':
            session.execute(text('SELECT pg_advisory_xact_lock(73421061)'))
        invoice = session.get(Invoice, invoice_id)
        if invoice is None:
            raise DeleteRejected(f'Rechnung {invoice_id} wurde nicht gefunden.')
        invoice_number = invoice.invoice_number
        item_rows = session.execute(
            select(InvoiceItem.id, InvoiceItem.product_id).where(InvoiceItem.invoice_id == invoice_id)
        ).all()
        item_ids = [item_id for item_id, _ in item_rows]
        product_ids = {product_id for _, product_id in item_rows}
        if item_ids:
            session.execute(delete(InvoiceItemSource).where(InvoiceItemSource.item_id.in_(item_ids)))
            session.execute(delete(InvoiceItem).where(InvoiceItem.invoice_id == invoice_id))
        session.delete(invoice)
        session.flush()
        for product_id in product_ids:
            first_seen, last_seen = session.execute(
                select(func.min(Invoice.invoice_date), func.max(Invoice.invoice_date))
                .select_from(InvoiceItem).join(Invoice, Invoice.id == InvoiceItem.invoice_id)
                .where(InvoiceItem.product_id == product_id)
            ).one()
            product = session.get(Product, product_id)
            product.first_seen, product.last_seen = first_seen, last_seen
        return dict(invoice_id=invoice_id, invoice_number=invoice_number,
                    item_count=len(item_ids), affected_products=len(product_ids))
