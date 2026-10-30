"""EAN eligibility for supplier/manual receipts; reversals and transfers stay separate."""
from sqlalchemy import select
from ..core.i18n import translate
from ..core.models import Artikel, VarianteEan
from .artikel import EAN_MUSTER


def receipt_identifiers(session, variante):
    return [ean for ean in [variante.ean, *session.scalars(
        select(VarianteEan.ean).where(VarianteEan.varianten_id == variante.id)
    )] if ean]


def missing_receipt_eans(session, varianten, language="de"):
    """Use the existing supplier identifier format rule (manual assignment checks digits)."""
    missing = []
    for variante in {v.id: v for v in varianten}.values():
        identifiers = receipt_identifiers(session, variante)
        if identifiers and all(EAN_MUSTER.fullmatch(ean) for ean in identifiers):
            continue
        artikel = session.get(Artikel, variante.artikel_id)
        missing.append({
            "varianten_id": variante.id, "artikel_id": artikel.id,
            "article": artikel.bezeichnung or artikel.lieferanten_artikelnr or str(artikel.id),
            "color": variante.farbe or "—", "size": variante.groesse or "—",
        })
    return missing


def receipt_error(missing, language):
    return translate("errors.receipt.ean_required", language, articles="; ".join(
        f"{row['article']} / {row['color']} / {row['size']}" for row in missing
    ))


def resolve_receipt_variant(session, artikel_id, color, size, ean, rejected, language):
    """Reuse a unique identity; an original EAN may complement an internal label."""
    from sqlalchemy import func
    from ..core.models import Variante
    from .ean import EanError, ist_intern, pruefe_nachgetragene_ean
    matches = session.scalars(select(Variante).where(
        Variante.artikel_id == artikel_id,
        func.coalesce(Variante.farbe, "") == (color or ""),
        func.coalesce(Variante.groesse, "") == (size or ""),
    )).all()
    if ean:
        # Distinct manufacturer EANs remain distinct variants, even if the
        # supplier omitted colour/size. Only enrich a missing/internal EAN.
        eligible = [v for v in matches if not v.ean or v.ean_intern]
        if eligible and len(matches) > 1:
            raise rejected(translate("errors.receipt.identity_conflict", language))
        matches = eligible
    if len(matches) > 1:
        raise rejected(translate("errors.receipt.identity_conflict", language))
    if not matches:
        return None
    variante = matches[0]
    if ean and ean not in receipt_identifiers(session, variante):
        if variante.ean and not variante.ean_intern:
            raise rejected(translate("errors.receipt.identity_conflict", language))
        try:
            ean = pruefe_nachgetragene_ean(ean, language)
        except EanError as exc:
            raise rejected(str(exc)) from exc
        if variante.ean:
            session.add(VarianteEan(varianten_id=variante.id, ean=ean, ean_intern=ist_intern(ean)))
        else:
            variante.ean, variante.ean_intern = ean, ist_intern(ean)
        session.flush()
    return variante
