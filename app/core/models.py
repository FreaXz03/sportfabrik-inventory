from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Numeric, String, JSON, text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)

    brand: Mapped[str | None] = mapped_column(String(100))
    supplier_article_no: Mapped[str | None] = mapped_column(String(100))

    article_no: Mapped[str | None] = mapped_column(
        String(100),
        index=True
    )

    ean: Mapped[str | None] = mapped_column(
        String(30),
        unique=True,
        index=True
    )

    description: Mapped[str | None] = mapped_column(String(500))

    color: Mapped[str | None] = mapped_column(String(250))
    size: Mapped[str | None] = mapped_column(String(100))

    first_seen: Mapped[date | None] = mapped_column(Date)
    last_seen: Mapped[date | None] = mapped_column(Date)


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)

    invoice_number: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True
    )

    invoice_date: Mapped[date | None] = mapped_column(Date)
    document_date: Mapped[date | None] = mapped_column(Date)

    supplier: Mapped[str | None] = mapped_column(String(200))

    filename: Mapped[str | None] = mapped_column(String(500))

    file_hash: Mapped[str | None] = mapped_column(
        String(64),
        unique=True
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    imported_by_kassennummer: Mapped[str | None] = mapped_column(String(20))
    imported_by_name: Mapped[str | None] = mapped_column(String(100))

    # True when this invoice's PDF had no text layer (a paper invoice that
    # arrived in the package and was scanned instead of received digitally)
    # and had to be read via OCR - see app/services/ocr.py. OCR is less
    # reliable than a native text layer, so this stays visible for later audits.
    ocr_used: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(primary_key=True)

    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id"),
        index=True
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"),
        index=True
    )

    quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2)
    )

    unit: Mapped[str | None] = mapped_column(
        String(30)
    )

    uvp: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2)
    )


class InvoiceItemSource(Base):
    """Immutable invoice-time fields, order and original text for later audits."""
    __tablename__ = "invoice_item_sources"
    item_id: Mapped[int] = mapped_column(ForeignKey('invoice_items.id'), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)


class User(Base):
    """Anmeldung übers Kassensystem-Muster: Mitarbeiter nur mit Kassennummer,
    Chefs zusätzlich mit Passwort. Rollen steuern Zugriff (siehe app/auth.py)."""
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('mitarbeiter', 'chef')", name="ck_users_role"),
        CheckConstraint(
            "(role = 'chef' AND password_hash IS NOT NULL) OR "
            "(role = 'mitarbeiter' AND password_hash IS NULL)",
            name="ck_users_chef_has_password",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    kassennummer: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        index=True
    )

    name: Mapped[str | None] = mapped_column(String(100))

    role: Mapped[str] = mapped_column(String(20))

    password_hash: Mapped[str | None] = mapped_column(String(200))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )


class ArticleNote(Base):
    __tablename__ = 'article_notes'
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id'), index=True)
    body: Mapped[str] = mapped_column(String(2000))
    author_user_id: Mapped[int] = mapped_column()
    author_name: Mapped[str] = mapped_column(String(100))
    author_number: Mapped[str] = mapped_column(String(20))
    updated_by: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    version: Mapped[int] = mapped_column(default=1)
