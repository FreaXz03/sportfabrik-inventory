"""Apply field-only corrections to a freshly parsed invoice; never trust client rows.

Unterscheidet wie die Parser (siehe app/services/parsers/intersport.py)
zwischen blockierenden **Warnungen** und nicht blockierenden **Hinweisen**:
eine Position ohne EAN ist erlaubt (Regel 5) und bekommt nur einen Hinweis,
eine unleserliche EAN bleibt eine Warnung.
"""

from copy import deepcopy
from datetime import datetime, timezone
from collections import Counter
from decimal import Decimal
from .artikel import EAN_MUSTER
from .parsers import decimal_value
from ..core.i18n import DEFAULT_LANGUAGE, template, translate

FIELDS = {
    "brand": 100,
    "supplier_article_no": 100,
    "article_no": 100,
    "ean": 30,
    "description": 500,
    "color": 250,
    "size": 100,
    "quantity": 30,
    "unit": 30,
    "uvp": 30,
}


class CorrectionError(ValueError):
    pass


def apply_corrections(parsed, corrections=None, actor=None, language: str = DEFAULT_LANGUAGE):
    result = deepcopy(parsed)
    if not isinstance(corrections or {}, dict):
        raise CorrectionError(translate("errors.corrections.unordered", language))
    patches = corrections or {}
    known = {str(i["row_number"]) for i in result["items"]}
    if set(patches) - known:
        raise CorrectionError(translate("errors.corrections.unknown_position", language))
    # Sprachunabhängig alte Parser-Warnungen wiedererkennen: die feste Vorsilbe
    # jedes Warnungs-Keys in der Sprache, in der ursprünglich geparst wurde
    # (dieselbe wie hier, da derselbe Request). Reine Textvergleiche würden bei
    # einem Sprachwechsel zwischen Upload und Korrektur fehlschlagen.
    reparsed_prefixes = tuple(
        template(key, language).split("{", 1)[0]
        for key in (
            "errors.parser.required_field_missing",
            "errors.parser.ean_unexpected_format",
            "errors.parser.invalid_value",
        )
    )
    color_size_prefix = template("errors.parser.color_size_ambiguous", language).split("{", 1)[0]
    # Hinweise, die hier selbst neu erzeugt werden (derselbe Mechanismus wie
    # oben für Warnungen): alles andere aus dem Parser bleibt stehen.
    recomputed_hint_prefixes = tuple(
        template(key, language).split("{", 1)[0]
        for key in ("hints.parser.ean_missing",)
    )
    for item in result["items"]:
        patch = patches.get(str(item["row_number"]), {})
        if not isinstance(patch, dict) or set(patch) - FIELDS.keys():
            raise CorrectionError(translate("errors.corrections.field_not_allowed", language))
        original = deepcopy(item)
        for key, value in patch.items():
            if not isinstance(value, str) or len(value) > FIELDS[key]:
                raise CorrectionError(
                    translate(
                        "errors.corrections.invalid_field_value",
                        language,
                        row=item["row_number"],
                        field=translate(f"fields.{key}", language),
                    )
                )
            item[key] = value.strip()
        errors = []
        # Revalidate field warnings, but retain unknown parser warnings.
        for warning in original["warnings"]:
            if warning.startswith(reparsed_prefixes):
                continue
            if warning.startswith(color_size_prefix) and all(
                item.get(k) and k in patch for k in ("color", "size")
            ):
                continue
            errors.append(warning)
        hints = [
            hint
            for hint in original.get("hints", [])
            if not hint.startswith(recomputed_hint_prefixes)
        ]
        for key, limit in FIELDS.items():
            value = item.get(key)
            # Farbe/Grösse/EAN sind optional (Regel 5).
            if key not in ("color", "size", "ean") and not value:
                errors.append(
                    translate(
                        "errors.parser.required_field_missing",
                        language,
                        field=translate(f"fields.{key}", language),
                    )
                )
            if value and len(str(value)) > limit:
                errors.append(
                    translate(
                        "errors.corrections.field_too_long",
                        language,
                        field=translate(f"fields.{key}", language),
                        limit=limit,
                    )
                )
        if not item.get("ean"):
            hints.append(translate("hints.parser.ean_missing", language))
        elif not EAN_MUSTER.fullmatch(item["ean"]):
            errors.append(translate("errors.corrections.invalid_ean", language))
        for key in ("quantity", "uvp"):
            try:
                value = decimal_value(str(item.get(key) or ""))
                number = Decimal(value)
                if abs(number) >= Decimal("100000000") or number != number.quantize(
                    Decimal(".01")
                ):
                    raise ValueError()
                if key == "uvp" and number < 0:
                    raise ValueError()
                item[key] = value
            except (ValueError, ArithmeticError):
                errors.append(
                    translate(
                        "errors.corrections.invalid_number",
                        language,
                        field=translate(f"fields.{key}", language),
                    )
                )
        item["warnings"] = errors
        item["hints"] = hints
        changes = {
            k: {"before": original.get(k), "after": item.get(k)}
            for k in patch
            if original.get(k) != item.get(k)
        }
        if changes:
            item["correction_audit"] = {
                "original": original,
                "changes": changes,
                "by": actor or {},
                "at": datetime.now(timezone.utc).isoformat(),
            }
    counts = Counter(i["ean"] for i in result["items"] if i.get("ean"))
    result["duplicate_eans"] = {k: v for k, v in counts.items() if v > 1}
    result["rows_with_warnings"] = sum(bool(i["warnings"]) for i in result["items"])
    result["rows_with_hints"] = sum(bool(i.get("hints")) for i in result["items"])
    result["corrected_rows"] = sum("correction_audit" in i for i in result["items"])
    return result
