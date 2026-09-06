from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, JSON
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
