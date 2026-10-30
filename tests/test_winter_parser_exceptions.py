"""Known printing quirks of the branch winter size list (synthetic PDFs only)."""
from decimal import Decimal

import pymupdf

from app.services.parsers import parse_document


def pdf(section, first, second, labels, rows, skip=0, bump=0):
    """rows: (name, first_price, second_price, qty_x, qty, printed_amount, printed_vp_total)"""
    with pymupdf.open() as doc:
        left_items = [(20, 60, 'Bestellung Winter HW SF1'), (944, 76, 'SF1'), (985, 76, 'Total'), (1040, 76, 'EP Total'),
                      (80, 96, section), (232, 96, first), (274, 96, second)] + [(x, 96, t) for x, t in labels]
        right_items = [(49, 76, 'VP Total'), (150, 76, 'VP-30%'), (218, 76, 'Liefertermin'), (286, 76, 'Art. Nr.')]
        y, totals, totals_rows = 120, {}, []
        for name, a, b, qx, qty, amount, vp_total in rows:
            left_items += [(40, y, name), (232, y, a), (274, y, b), (qx, y, str(qty)), (945, y, str(qty)), (985, y, str(qty)), (1040, y, amount)]
            right_items += [(49, y, vp_total), (150, y, '1.00'), (223, y, '15.09.2025')]
            if len(totals_rows) >= skip:
                totals[qx] = totals.get(qx, 0) + qty
            totals_rows.append(qty)
            y += 25
        count = str(sum(totals_rows))
        if bump:
            totals[next(iter(totals))] += bump
        left_items += [(80, y, 'Total pro Grösse'), (945, y, count), (985, y, count)] + [(x, y, str(q)) for x, q in totals.items()]
        for items in (left_items, right_items):
            page = doc.new_page(width=1190.5, height=841.9)
            for x, yy, t in items:
                page.insert_text((x, yy), t, fontsize=8)
        return doc.tobytes()


def vector(amount='699.00', vp_total='244.50'):
    return pdf('Skistöcke Erw.', 'EP', 'VP', [(320, '115')], [('Mckinley Vector CRB (Carbon)', '24.45', '69.90', 320, 10, amount, vp_total)])


def test_vector_swapped_total_columns_use_listed_vp_and_ep():
    group = parse_document(vector())['groups'][0]
    assert not group['warnings']
    assert (Decimal(group['uvp']), Decimal(group['ek'])) == (Decimal('69.90'), Decimal('24.45'))


def test_vector_with_inconsistent_totals_stays_blocked():
    assert parse_document(vector(amount='700.00'))['groups'][0]['warnings']


def flyte(name='McKinley Flyte JR Revo schwarz'):
    return pdf('Brillen Kids', 'VP', 'EP', [(306, 'One Size'), (362, '2')], [(name, '44.90', '14.80', 362, 5, '74.00', '224.50')])


def test_flyte_jr_revo_keeps_the_two_in_the_name_and_is_onesize():
    group = parse_document(flyte())['groups'][0]
    assert group['name'] == 'McKinley Flyte JR 2 Revo schwarz'
    assert group['sizes'] == {'ONESIZE': '5'} and not group['warnings']


def test_other_digit_column_next_to_onesize_stays_blocked():
    assert parse_document(flyte('Other Goggle schwarz'))['groups'][0]['warnings']


def two_rows(**kw):
    rows = [('Scarpa Rush Polar GTX', '299', '148.90', 320, 4, '595.60', '1196.00'),
            ('Columbia Burnsider OHI Black', '150', '64.50', 320, 3, '193.50', '450.00')]
    return pdf('Winterschuhe Men', 'VP', 'EP', [(320, '41')], rows, **kw)


def test_column_totals_missing_exactly_one_listed_row_are_accepted():
    # Real SF2 print: the per-size total line omits one article; row and grand totals are right.
    result = parse_document(two_rows(skip=1))
    assert [g['quantity'] for g in result['groups']] == ['4', '3'] and not result['warnings']


def test_column_totals_with_other_difference_stay_blocked():
    import pytest
    from app.services.parsers.base import DocumentParseError
    with pytest.raises(DocumentParseError):
        parse_document(two_rows(skip=1, bump=2))
    with pytest.raises(DocumentParseError):
        parse_document(two_rows(skip=0, bump=1))
