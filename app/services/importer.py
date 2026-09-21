"""Atomic, duplicate-safe imports and deletions. Import: call only after explicit
preview confirmation. Deletion: chef-only, see app/auth.py."""

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import re

import pymupdf
from sqlalchemy import delete, func, select, or_, text
from sqlalchemy.exc import IntegrityError

from ..core.fedas import suggest_kategorie
from ..core.i18n import DEFAULT_LANGUAGE, translate
from ..core.models import (
    Artikel,
    Bestand,
    Dokument,
    Kategorie,
    Lagerbewegung,
    Lagerort,
    Lieferant,
    Preis,
    Variante,
    Wareneingang,
    WareneingangPosition,
    WareneingangPositionQuelle,
)
from .parser import page_content, parse_invoice
from .corrections import apply_corrections, CorrectionError

INTERSPORT_PARSER_KEY = "intersport"


class ImportRejected(ValueError):
    pass


class DeleteRejected(ValueError):
    pass


def invoice_dates(pdf, language: str = DEFAULT_LANGUAGE):
    # Uses the same native-text-or-OCR fallback as parse_invoice, so dates are
    # still found on scanned (paper) invoices - see parser.py. All pages are
    # searched, not just the first: a scanned invoice's pages are not always
    # in the order a digital export always uses (the header block with these
    # dates can end up scanned onto a later page).
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        pages_words = [page_content(page, language)[0] for page in doc]
    result = {}
    # "Rechnungsdatum"/"Belegdatum" sind feste Textanker im INTERSPORT-Layout
    # (immer Deutsch, unabhängig von der UI-Sprache) - nur die Fehlermeldung
    # bei fehlendem/mehrdeutigem Datum wird übersetzt.
    for label, key in [
        ("Rechnungsdatum", "invoice_date"),
        ("Belegdatum", "document_date"),
    ]:
        anchors = [(words, w) for words in pages_words for w in words if w[4] == label]
        if len(anchors) != 1:
            raise ImportRejected(translate(f"errors.importer.{key}_not_unique", language))
        words, anchor = anchors[0]
        candidates = [
            w[4]
            for w in words
            if w[0] > anchor[2]
            and abs(w[1] - anchor[1]) < 2
            and re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", w[4])
        ]
        if len(candidates) != 1:
            raise ImportRejected(
                translate(f"errors.importer.{key}_missing_or_ambiguous", language)
            )
        try:
            result[key] = datetime.strptime(candidates[0], "%d.%m.%Y").date()
        except ValueError as exc:
            raise ImportRejected(translate(f"errors.importer.{key}_invalid", language)) from exc
    return result


def _artikel_group_key(brand: str | None, supplier_article_no: str | None):
    """Gleiche Gruppierung wie die Alembic-Migration c3d4e5f6a7b8 und (bis zur
    Umstellung) app/services/article_groups.py: gleiche Marke (ohne Gross-/
    Kleinschreibung, getrimmt) UND gleiche, nicht-leere Lieferanten-
    Artikelnummer (getrimmt) = ein Artikel. Fehlt die Nummer, bleibt jedes
    Produkt ein eigener Artikel (None = immer neu anlegen)."""
    number = (supplier_article_no or "").strip()
    if not number:
        return None
    return ((brand or "").strip().lower(), number)


def _backfill_artikel(session, kategorie_cache, artikel, item):
    """Fehlenden FEDAS-Code und die daraus abgeleitete Kategorie nachtragen.

    Läuft für jeden Artikel einer Rechnungsposition - auch wenn die Variante
    über ihre EAN gefunden wurde, denn genau die migrierten Altartikel haben
    noch keinen FEDAS-Code. Ein bereits gesetzter Wert wird nie überschrieben
    („einmal pro Artikel, danach gemerkt").
    """
    if not artikel.fedas_code and item.get("fedas_code"):
        artikel.fedas_code = item["fedas_code"]
    if artikel.kategorie_id is None:
        artikel.kategorie_id = _resolve_kategorie_id(
            session, kategorie_cache, artikel.fedas_code
        )


def _resolve_kategorie_id(session, cache, fedas_code):
    """Kategorie-Vorschlag aus dem FEDAS-Code (siehe app/core/fedas.py), oder
    None, wenn der Code (noch) nicht zugeordnet ist bzw. fehlt - dann bleibt
    artikel.kategorie_id leer (manuelle Auswahl folgt in einem späteren
    Schritt von Phase B)."""
    suggestion = suggest_kategorie(fedas_code)
    if suggestion is None:
        return None
    if suggestion not in cache:
        hauptgruppe, sportbereich = suggestion
        cache[suggestion] = session.scalar(
            select(Kategorie.id).where(
                Kategorie.hauptgruppe == hauptgruppe, Kategorie.sportbereich == sportbereich
            )
        )
    return cache[suggestion]


def import_invoice(
    pdf,
    filename,
    expected_hash,
    session_factory,
    lagerort_id,
    imported_by=None,
    corrections=None,
    language: str = DEFAULT_LANGUAGE,
):
    digest = hashlib.sha256(pdf).hexdigest()
    if digest != expected_hash:
        raise ImportRejected(translate("errors.importer.hash_mismatch", language))
    parsed = parse_invoice(pdf, language)
    if corrections:
        try:
            parsed = apply_corrections(parsed, corrections, imported_by, language)
        except CorrectionError as exc:
            raise ImportRejected(str(exc)) from exc
    if (
        not parsed["invoice_number"]
        or parsed["warnings"]
        or parsed["rows_with_warnings"]
    ):
        raise ImportRejected(translate("errors.importer.locked_warnings", language))
    dates = invoice_dates(pdf, language)
    for item in parsed["items"]:
        # Jedes Feld, das in eine begrenzte Spalte geschrieben wird - sonst
        # scheitert erst PostgreSQL mit einem DataError (der nicht als
        # ImportRejected, sondern als 503 beim Benutzer landet).
        for key, limit in [
            ("brand", 100),
            ("supplier_article_no", 100),
            ("fedas_code", 10),
            ("ean", 30),
            ("description", 500),
            ("color", 250),
            ("size", 100),
            ("unit", 30),
        ]:
            if len(item.get(key) or "") > limit:
                raise ImportRejected(
                    translate(
                        "errors.importer.field_too_long",
                        language,
                        row=item["row_number"],
                        field=translate(f"fields.{key}", language),
                    )
                )
        for key in ("quantity", "uvp"):
            value = Decimal(item[key])
            if abs(value) >= Decimal("100000000") or value != value.quantize(
                Decimal(".01")
            ):
                raise ImportRejected(
                    translate(
                        "errors.importer.field_invalid_format",
                        language,
                        row=item["row_number"],
                        field=translate(f"fields.{key}", language),
                    )
                )
    try:
        with session_factory() as session, session.begin():
            # Serialize imports across all app workers on PostgreSQL, including
            # different invoices that introduce the same EAN concurrently.
            if session.bind.dialect.name == "postgresql":
                session.execute(text("SELECT pg_advisory_xact_lock(73421061)"))
            existing = session.scalar(
                select(Dokument).where(
                    or_(
                        Dokument.datei_hash == digest,
                        Dokument.dokumentnummer == parsed["invoice_number"],
                    )
                )
            )
            if existing:
                raise ImportRejected(
                    translate(
                        "errors.importer.already_imported",
                        language,
                        number=existing.dokumentnummer,
                        id=existing.id,
                    )
                )
            lieferant = session.scalar(
                select(Lieferant).where(Lieferant.parser_key == INTERSPORT_PARSER_KEY)
            )
            if lieferant is None:
                raise ImportRejected(
                    translate("errors.importer.supplier_not_configured", language)
                )
            # Regel 6: Ware an ein externes Lager (GEWA, `verkauf = False`)
            # bekommt noch KEIN Eingangsdatum - das wird erst bei Ankunft in
            # einer Filiale gesetzt, damit die Reduktionsuhr (18/36 Monate)
            # nicht schon im Zwischenlager zu laufen beginnt.
            lagerort_verkauft = session.scalar(
                select(Lagerort.verkauf).where(Lagerort.id == lagerort_id)
            )
            eingangsdatum = dates["invoice_date"] if lagerort_verkauft else None
            now = datetime.now(timezone.utc)
            dokument = Dokument(
                lieferant_id=lieferant.id,
                lagerort_id=lagerort_id,
                typ="rechnung",
                dokumentnummer=parsed["invoice_number"],
                dokumentdatum=dates["invoice_date"],
                belegdatum=dates["document_date"],
                dateiname=(filename or "rechnung.pdf")[:500],
                datei_hash=digest,
                hochgeladen_am=now,
                hochgeladen_von_kassennummer=(imported_by or {}).get("kassennummer"),
                hochgeladen_von_name=(imported_by or {}).get("name"),
                ocr_verwendet=bool(parsed.get("ocr_used")),
            )
            session.add(dokument)
            session.flush()
            wareneingang = Wareneingang(
                dokument_id=dokument.id,
                lagerort_id=lagerort_id,
                status="eingetroffen",
                eingangsdatum=eingangsdatum,
            )
            session.add(wareneingang)
            session.flush()

            new_varianten, reused_varianten = 0, set()
            artikel_cache = {}
            variante_cache = {}
            kategorie_cache = {}
            seen = dates["invoice_date"]
            for item in parsed["items"]:
                ean = item["ean"] or None
                # Cache-Treffer = in dieser Rechnung selbst angelegt; nur ein
                # Treffer in der Datenbank ist echte Wiederverwendung.
                variante = variante_cache.get(ean) if ean else None
                if variante is None and ean:
                    variante = session.scalar(select(Variante).where(Variante.ean == ean))
                    if variante is not None:
                        reused_varianten.add(variante.id)

                if variante is None:
                    group_key = _artikel_group_key(item.get("brand"), item.get("supplier_article_no"))
                    artikel = artikel_cache.get(group_key) if group_key else None
                    if artikel is None and group_key:
                        artikel = session.scalar(
                            select(Artikel).where(
                                Artikel.lieferant_id == lieferant.id,
                                func.lower(func.trim(func.coalesce(Artikel.marke, "")))
                                == group_key[0],
                                func.trim(Artikel.lieferanten_artikelnr) == group_key[1],
                            )
                        )
                    if artikel is None:
                        fedas_code = item.get("fedas_code") or None
                        artikel = Artikel(
                            lieferant_id=lieferant.id,
                            marke=item.get("brand"),
                            lieferanten_artikelnr=item.get("supplier_article_no"),
                            bezeichnung=item.get("description"),
                            fedas_code=fedas_code,
                            kategorie_id=_resolve_kategorie_id(session, kategorie_cache, fedas_code),
                        )
                        session.add(artikel)
                        session.flush()
                    else:
                        _backfill_artikel(session, kategorie_cache, artikel, item)
                    if group_key:
                        artikel_cache[group_key] = artikel

                    variante = None
                    if not ean:
                        variante = session.scalar(
                            select(Variante).where(
                                Variante.artikel_id == artikel.id,
                                func.coalesce(Variante.farbe, "") == (item.get("color") or ""),
                                func.coalesce(Variante.groesse, "") == (item.get("size") or ""),
                            )
                        )
                    if variante is None:
                        variante = Variante(
                            artikel_id=artikel.id,
                            farbe=item.get("color"),
                            groesse=item.get("size"),
                            ean=ean,
                            ean_intern=False,
                        )
                        session.add(variante)
                        session.flush()
                        new_varianten += 1
                    else:
                        reused_varianten.add(variante.id)
                else:
                    # Variante schon bekannt (EAN-Treffer): der zugehörige
                    # Artikel bekommt trotzdem FEDAS-Code/Kategorie nachgetragen
                    # - sonst bliebe genau der migrierte Altbestand für immer
                    # ohne Kategorie.
                    _backfill_artikel(
                        session, kategorie_cache, session.get(Artikel, variante.artikel_id), item
                    )
                if ean:
                    variante_cache[ean] = variante

                variante.first_seen = (
                    min(variante.first_seen, seen) if variante.first_seen else seen
                )
                variante.last_seen = (
                    max(variante.last_seen, seen) if variante.last_seen else seen
                )

                quantity = Decimal(item["quantity"])
                uvp = Decimal(item["uvp"])
                position = WareneingangPosition(
                    wareneingang_id=wareneingang.id,
                    varianten_id=variante.id,
                    menge=quantity,
                    einheit=item["unit"],
                    uvp=uvp,
                )
                session.add(position)
                session.flush()
                session.add(WareneingangPositionQuelle(position_id=position.id, data=item))
                session.add(
                    Preis(
                        varianten_id=variante.id,
                        uvp=uvp,
                        datum=dates["invoice_date"],
                        dokument_id=dokument.id,
                    )
                )
                session.add(
                    Lagerbewegung(
                        lagerort_id=lagerort_id,
                        varianten_id=variante.id,
                        typ="zugang",
                        menge=quantity,
                        wareneingang_position_id=position.id,
                        benutzer_kassennummer=(imported_by or {}).get("kassennummer"),
                        benutzer_name=(imported_by or {}).get("name"),
                        zeitpunkt=now,
                    )
                )
                bestand = session.get(Bestand, (variante.id, lagerort_id))
                if bestand is None:
                    bestand = Bestand(
                        varianten_id=variante.id,
                        lagerort_id=lagerort_id,
                        menge=quantity,
                        aeltestes_eingangsdatum=eingangsdatum,
                    )
                    session.add(bestand)
                else:
                    bestand.menge += quantity
                    if eingangsdatum and (
                        bestand.aeltestes_eingangsdatum is None
                        or eingangsdatum < bestand.aeltestes_eingangsdatum
                    ):
                        bestand.aeltestes_eingangsdatum = eingangsdatum

            result = dict(
                invoice_id=dokument.id,
                invoice_number=dokument.dokumentnummer,
                item_count=parsed["item_count"],
                new_products=new_varianten,
                reused_products=len(reused_varianten),
            )
        return result
    except IntegrityError as exc:
        raise ImportRejected(
            translate("errors.importer.integrity_conflict", language)
        ) from exc


def delete_invoice(invoice_id: int, session_factory, language: str = DEFAULT_LANGUAGE) -> dict:
    """Löscht ein importiertes Dokument samt Wareneingang, Positionen und
    Originaltexten unwiderruflich - inklusive der dadurch entstandenen
    Lagerbewegungen und Preiseinträge, damit `bestand` (Regel 2) konsistent
    bleibt. `varianten`/`artikel` selbst bleiben bestehen (Artikelstamm gilt
    für immer, Regel 4), nur first_seen/last_seen werden aus den verbleibenden
    Wareneingängen neu berechnet.
    """
    with session_factory() as session, session.begin():
        # Dieselbe Sperre wie beim Import: verhindert, dass ein gleichzeitiger
        # Import/Löschvorgang mit denselben Varianten first_seen/last_seen
        # oder bestand falsch berechnet.
        if session.bind.dialect.name == "postgresql":
            session.execute(text("SELECT pg_advisory_xact_lock(73421061)"))
        dokument = session.get(Dokument, invoice_id)
        if dokument is None:
            raise DeleteRejected(
                translate("errors.importer.invoice_not_found", language, id=invoice_id)
            )
        dokumentnummer = dokument.dokumentnummer
        wareneingaenge = session.scalars(
            select(Wareneingang).where(Wareneingang.dokument_id == invoice_id)
        ).all()
        wareneingang_ids = [w.id for w in wareneingaenge]
        position_rows = session.execute(
            select(
                WareneingangPosition.id,
                WareneingangPosition.varianten_id,
                WareneingangPosition.wareneingang_id,
            ).where(WareneingangPosition.wareneingang_id.in_(wareneingang_ids))
        ).all()
        position_ids = [p.id for p in position_rows]
        varianten_by_lagerort = {}
        for _, varianten_id, wareneingang_id in position_rows:
            wareneingang = next(w for w in wareneingaenge if w.id == wareneingang_id)
            varianten_by_lagerort.setdefault(wareneingang.lagerort_id, set()).add(varianten_id)

        if position_ids:
            session.execute(
                delete(WareneingangPositionQuelle).where(
                    WareneingangPositionQuelle.position_id.in_(position_ids)
                )
            )
            session.execute(
                delete(Lagerbewegung).where(
                    Lagerbewegung.wareneingang_position_id.in_(position_ids)
                )
            )
        session.execute(delete(Preis).where(Preis.dokument_id == invoice_id))
        session.execute(
            delete(WareneingangPosition).where(
                WareneingangPosition.wareneingang_id.in_(wareneingang_ids)
            )
        )
        session.execute(delete(Wareneingang).where(Wareneingang.dokument_id == invoice_id))
        session.delete(dokument)
        session.flush()

        for lagerort_id, varianten_ids in varianten_by_lagerort.items():
            for varianten_id in varianten_ids:
                menge = session.scalar(
                    select(func.coalesce(func.sum(Lagerbewegung.menge), 0)).where(
                        Lagerbewegung.varianten_id == varianten_id,
                        Lagerbewegung.lagerort_id == lagerort_id,
                    )
                )
                bestand = session.get(Bestand, (varianten_id, lagerort_id))
                aeltestes = session.scalar(
                    select(func.min(Wareneingang.eingangsdatum))
                    .select_from(WareneingangPosition)
                    .join(
                        Wareneingang,
                        Wareneingang.id == WareneingangPosition.wareneingang_id,
                    )
                    .where(
                        WareneingangPosition.varianten_id == varianten_id,
                        Wareneingang.lagerort_id == lagerort_id,
                    )
                )
                if menge:
                    if bestand is None:
                        bestand = Bestand(
                            varianten_id=varianten_id,
                            lagerort_id=lagerort_id,
                            menge=menge,
                            aeltestes_eingangsdatum=aeltestes,
                        )
                        session.add(bestand)
                    else:
                        bestand.menge = menge
                        bestand.aeltestes_eingangsdatum = aeltestes
                elif bestand is not None:
                    session.delete(bestand)

        all_varianten_ids = {v for ids in varianten_by_lagerort.values() for v in ids}
        for varianten_id in all_varianten_ids:
            # first_seen/last_seen aus dem Dokumentdatum, genau wie beim Import
            # - nicht aus dem Eingangsdatum: das bleibt fuer Ware an GEWA leer
            #   (Regel 6) und wuerde die Werte hier auf NULL zuruecksetzen.
            first_seen, last_seen = session.execute(
                select(
                    func.min(Dokument.dokumentdatum), func.max(Dokument.dokumentdatum)
                )
                .select_from(WareneingangPosition)
                .join(
                    Wareneingang, Wareneingang.id == WareneingangPosition.wareneingang_id
                )
                .join(Dokument, Dokument.id == Wareneingang.dokument_id)
                .where(WareneingangPosition.varianten_id == varianten_id)
            ).one()
            variante = session.get(Variante, varianten_id)
            variante.first_seen, variante.last_seen = first_seen, last_seen
        return dict(
            invoice_id=invoice_id,
            invoice_number=dokumentnummer,
            item_count=len(position_ids),
            affected_products=len(all_varianten_ids),
        )
