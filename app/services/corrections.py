"""Apply field-only corrections to a freshly parsed invoice; never trust client rows."""
from copy import deepcopy
from datetime import datetime, timezone
from collections import Counter
import re
from decimal import Decimal
from .parser import decimal_value

FIELDS = {'brand':100, 'supplier_article_no':100, 'article_no':100, 'ean':30,
          'description':500, 'color':250, 'size':100, 'quantity':30, 'unit':30, 'uvp':30}


class CorrectionError(ValueError):
    pass


def apply_corrections(parsed, corrections=None, actor=None):
    result = deepcopy(parsed)
    if not isinstance(corrections or {}, dict):
        raise CorrectionError('Korrekturen müssen nach Positionsnummer geordnet sein.')
    patches = corrections or {}
    known = {str(i['row_number']) for i in result['items']}
    if set(patches) - known:
        raise CorrectionError('Eine korrigierte Position existiert nicht in der Rechnung.')
    for item in result['items']:
        patch = patches.get(str(item['row_number']), {})
        if not isinstance(patch, dict) or set(patch) - FIELDS.keys():
            raise CorrectionError('Nur die vorgesehenen Artikelfelder dürfen korrigiert werden.')
        original = deepcopy(item)
        for key, value in patch.items():
            if not isinstance(value, str) or len(value) > FIELDS[key]:
                raise CorrectionError(f'Position {item["row_number"]}: ungültiger Wert für {key}.')
            item[key] = value.strip()
        errors = []
        # Revalidate field warnings, but retain unknown parser warnings.
        for warning in original['warnings']:
            if warning.startswith(('Pflichtfeld fehlt:', 'EAN hat ein unerwartetes', 'Ungültiger Wert für')):
                continue
            if warning.startswith('Farbe/Grösse nicht eindeutig') and all(item.get(k) and k in patch for k in ('color','size')):
                continue
            errors.append(warning)
        for key, limit in FIELDS.items():
            value = item.get(key)
            if key not in ('color','size') and not value:
                errors.append(f'Pflichtfeld fehlt: {key}')
            if value and len(str(value)) > limit:
                errors.append(f'{key}: maximal {limit} Zeichen.')
        if not re.fullmatch(r'(?:[0-9]{8}|[0-9]{12,14})', item.get('ean') or ''):
            errors.append('EAN muss 8, 12, 13 oder 14 Ziffern enthalten.')
        for key in ('quantity','uvp'):
            try:
                value = decimal_value(str(item.get(key) or ''))
                number = Decimal(value)
                if abs(number) >= Decimal('100000000') or number != number.quantize(Decimal('.01')):
                    raise ValueError()
                if key == 'uvp' and number < 0:
                    raise ValueError()
                item[key] = value
            except (ValueError, ArithmeticError):
                errors.append(f'{key}: gültige Zahl mit höchstens zwei Nachkommastellen erforderlich.')
        item['warnings'] = errors
        changes = {k:{'before':original.get(k),'after':item.get(k)} for k in patch if original.get(k) != item.get(k)}
        if changes:
            item['correction_audit'] = {'original':original,'changes':changes,
                'by': actor or {}, 'at': datetime.now(timezone.utc).isoformat()}
    counts = Counter(i['ean'] for i in result['items'] if i.get('ean'))
    result['duplicate_eans'] = {k:v for k,v in counts.items() if v > 1}
    result['rows_with_warnings'] = sum(bool(i['warnings']) for i in result['items'])
    result['corrected_rows'] = sum('correction_audit' in i for i in result['items'])
    return result
