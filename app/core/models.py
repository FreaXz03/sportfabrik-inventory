from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    JSON,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)

    brand: Mapped[str | None] = mapped_column(String(100))
    supplier_article_no: Mapped[str | None] = mapped_column(String(100))

    article_no: Mapped[str | None] = mapped_column(String(100), index=True)

    ean: Mapped[str | None] = mapped_column(String(30), unique=True, index=True)

    description: Mapped[str | None] = mapped_column(String(500))

    color: Mapped[str | None] = mapped_column(String(250))
    size: Mapped[str | None] = mapped_column(String(100))

    first_seen: Mapped[date | None] = mapped_column(Date)
    last_seen: Mapped[date | None] = mapped_column(Date)


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)

    invoice_number: Mapped[str] = mapped_column(String(100), unique=True, index=True)

    invoice_date: Mapped[date | None] = mapped_column(Date)
    document_date: Mapped[date | None] = mapped_column(Date)

    supplier: Mapped[str | None] = mapped_column(String(200))

    filename: Mapped[str | None] = mapped_column(String(500))

    file_hash: Mapped[str | None] = mapped_column(String(64), unique=True)

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    imported_by_kassennummer: Mapped[str | None] = mapped_column(String(20))
    imported_by_name: Mapped[str | None] = mapped_column(String(100))

    # True when this invoice's PDF had no text layer (a paper invoice that
    # arrived in the package and was scanned instead of received digitally)
    # and had to be read via OCR - see app/services/ocr.py. OCR is less
    # reliable than a native text layer, so this stays visible for later audits.
    ocr_used: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(primary_key=True)

    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), index=True)

    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)

    quantity: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    unit: Mapped[str | None] = mapped_column(String(30))

    uvp: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))


class InvoiceItemSource(Base):
    """Immutable invoice-time fields, order and original text for later audits."""

    __tablename__ = "invoice_item_sources"
    item_id: Mapped[int] = mapped_column(
        ForeignKey("invoice_items.id"), primary_key=True
    )
    data: Mapped[dict] = mapped_column(JSON)


class User(Base):
    """Anmeldung übers Kassensystem-Muster: Mitarbeiter nur mit Kassennummer,
    Filialleiter/Admin zusätzlich mit Passwort. Rollen steuern Zugriff gemäss
    Regel 9 (siehe app/routers/auth.py): Mitarbeiter alles ausser Dokumente,
    Filialleiter (`chef`) zusätzlich Dokumente, Admin/Zentrale filialübergreifend.
    Die Filialzuordnung liegt in `benutzer_lagerorte` (m:n, Admin braucht keine)."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('mitarbeiter', 'chef', 'admin')", name="ck_users_role"),
        CheckConstraint(
            "(role IN ('chef', 'admin') AND password_hash IS NOT NULL) OR "
            "(role = 'mitarbeiter' AND password_hash IS NULL)",
            name="ck_users_chef_has_password",
        ),
        CheckConstraint("language IN ('de', 'fr', 'en')", name="ck_users_language"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    kassennummer: Mapped[str] = mapped_column(String(20), unique=True, index=True)

    name: Mapped[str | None] = mapped_column(String(100))

    role: Mapped[str] = mapped_column(String(20))

    password_hash: Mapped[str | None] = mapped_column(String(200))

    # Regel 7: Deutsch ist Standard, jederzeit pro Benutzer umstellbar
    # (siehe app/core/i18n.py, POST /api/language).
    language: Mapped[str] = mapped_column(
        String(2), default="de", server_default=text("'de'")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Lagerort(Base):
    """Filiale (SF1-SF4, Verkauf) oder externes Aufbereitungslager (GEWA, kein
    Verkauf). Seed-Daten in app/core/lagerorte.py, Adresse dient später auch
    der automatischen Filial-Erkennung aus der Lieferadresse eines Dokuments."""

    __tablename__ = "lagerorte"

    id: Mapped[int] = mapped_column(primary_key=True)

    code: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))

    strasse: Mapped[str | None] = mapped_column(String(200))
    plz: Mapped[str | None] = mapped_column(String(10))
    ort: Mapped[str | None] = mapped_column(String(100))
    telefon: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(200))

    verkauf: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class BenutzerLagerort(Base):
    """Ordnet einen Benutzer einer oder mehreren Filialen zu (m:n, z.B. Aushilfe
    an mehreren Standorten). `ist_primaer` markiert die Filiale, die nach dem
    Login vorausgewählt ist. Admin-Konten brauchen keinen Eintrag hier."""

    __tablename__ = "benutzer_lagerorte"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    lagerort_id: Mapped[int] = mapped_column(
        ForeignKey("lagerorte.id"), primary_key=True
    )
    ist_primaer: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )


class ArticleNote(Base):
    __tablename__ = "article_notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    body: Mapped[str] = mapped_column(String(2000))
    author_user_id: Mapped[int] = mapped_column()
    author_name: Mapped[str] = mapped_column(String(100))
    author_number: Mapped[str] = mapped_column(String(20))
    updated_by: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    version: Mapped[int] = mapped_column(default=1)
