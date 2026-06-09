from datetime import date, datetime
from typing import List, Optional

from pydantic import ConfigDict
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


PAYMENT_METHODS = (
    "efectivo",
    "tarjeta_credito",
    "tarjeta_debito",
    "mercado_pago",
)
SALE_STATUSES = ("cerrada", "anulada")
INVOICE_STATUSES = ("pendiente", "autorizada", "rechazada", "anulada")
CASH_CLOSING_STATUSES = ("abierto", "cerrado")
GOAL_PERIODS = ("diario", "semanal", "mensual")
STOCK_MOVEMENT_TYPES = (
    "venta",
    "devolucion_mesa",
    "ajuste_manual",
    "reposicion",
    "merma",
    "correccion",
)


class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "user"
    __table_args__ = {"schema": "public"}

    model_config = ConfigDict(from_attributes=True)

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str]
    role: Mapped[str] = mapped_column(String(30))
    password: Mapped[str]
    deleted_at: Mapped[datetime | None]


class ProductModel(Base):
    __tablename__ = "products"
    __table_args__ = {"schema": "public"}

    model_config = ConfigDict(from_attributes=True)

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(30))
    name: Mapped[str]
    price: Mapped[int]
    unit: Mapped[str]
    qty: Mapped[int]

    inventory_settings: Mapped[Optional["ProductInventorySettingsModel"]] = (
        relationship(
            back_populates="product",
            cascade="all, delete-orphan",
            uselist=False,
        )
    )


class ProductInventorySettingsModel(Base):
    __tablename__ = "product_inventory_settings"
    __table_args__ = (
        CheckConstraint(
            "minimum_qty >= 0",
            name="ck_product_inventory_settings_minimum_qty",
        ),
        CheckConstraint(
            "capacity_qty IS NULL OR capacity_qty > 0",
            name="ck_product_inventory_settings_capacity_qty",
        ),
        {"schema": "public"},
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey(ProductModel.id, ondelete="CASCADE"),
        primary_key=True,
    )
    minimum_qty: Mapped[int] = mapped_column(Integer, default=0)
    capacity_qty: Mapped[Optional[int]]
    last_restocked_at: Mapped[Optional[datetime]]
    deleted_at: Mapped[Optional[datetime]]

    product: Mapped["ProductModel"] = relationship(
        back_populates="inventory_settings",
    )


class OpenTableModel(Base):
    __tablename__ = "open_tables"
    __table_args__ = {"schema": "public"}

    model_config = ConfigDict(from_attributes=True)

    id: Mapped[int] = mapped_column(primary_key=True)
    table_number: Mapped[int] = mapped_column(unique=True)
    table_name: Mapped[Optional[str]]
    opening_time: Mapped[datetime]
    people: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    deleted_at: Mapped[Optional[datetime]]

    # This relationship is the active order consumed by TableService.
    items: Mapped[List["OpenTableItemModel"]] = relationship(
        back_populates="table",
        cascade="all, delete-orphan",
    )


class OpenTableItemModel(Base):
    __tablename__ = "open_table_items"
    __table_args__ = {"schema": "public"}

    model_config = ConfigDict(from_attributes=True)

    id: Mapped[int] = mapped_column(primary_key=True)
    table_id: Mapped[int] = mapped_column(ForeignKey(OpenTableModel.id))
    product_id: Mapped[int] = mapped_column(ForeignKey(ProductModel.id))
    quantity: Mapped[int]
    curr_price: Mapped[int]

    table: Mapped["OpenTableModel"] = relationship(back_populates="items")
    product: Mapped["ProductModel"] = relationship()


class CashClosingModel(Base):
    __tablename__ = "cash_closings"
    __table_args__ = (
        CheckConstraint("total_sales >= 0", name="ck_cash_closings_total_sales"),
        CheckConstraint(
            "expected_cash >= 0",
            name="ck_cash_closings_expected_cash",
        ),
        CheckConstraint(
            "counted_cash >= 0",
            name="ck_cash_closings_counted_cash",
        ),
        {"schema": "public"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    business_date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    closed_at: Mapped[datetime] = mapped_column(default=datetime.now)
    closed_by_id: Mapped[int] = mapped_column(ForeignKey(UserModel.id))
    total_sales: Mapped[int] = mapped_column(Integer, default=0)
    expected_cash: Mapped[int] = mapped_column(Integer, default=0)
    counted_cash: Mapped[int] = mapped_column(Integer, default=0)
    difference: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(
        Enum(
            *CASH_CLOSING_STATUSES,
            name="cash_closing_status",
            native_enum=False,
        ),
        default="cerrado",
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)

    closed_by: Mapped["UserModel"] = relationship()
    sales: Mapped[List["ClosingsModel"]] = relationship(
        back_populates="cash_closing",
    )
    revisions: Mapped[List["CashClosingRevisionModel"]] = relationship(
        back_populates="cash_closing",
        cascade="all, delete-orphan",
        order_by="CashClosingRevisionModel.changed_at",
    )


class CashClosingRevisionModel(Base):
    __tablename__ = "cash_closing_revisions"
    __table_args__ = (
        CheckConstraint(
            "previous_counted_cash >= 0",
            name="ck_cash_closing_revisions_previous_cash",
        ),
        CheckConstraint(
            "new_counted_cash >= 0",
            name="ck_cash_closing_revisions_new_cash",
        ),
        {"schema": "public"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cash_closing_id: Mapped[int] = mapped_column(
        ForeignKey(CashClosingModel.id, ondelete="CASCADE"),
        index=True,
    )
    changed_by_id: Mapped[int] = mapped_column(ForeignKey(UserModel.id))
    changed_at: Mapped[datetime] = mapped_column(default=datetime.now)
    previous_counted_cash: Mapped[int]
    new_counted_cash: Mapped[int]
    previous_notes: Mapped[Optional[str]] = mapped_column(Text)
    new_notes: Mapped[Optional[str]] = mapped_column(Text)

    cash_closing: Mapped["CashClosingModel"] = relationship(
        back_populates="revisions",
    )
    changed_by: Mapped["UserModel"] = relationship()


class ClosingsModel(Base):
    """Historical sale generated when an open table is closed."""

    __tablename__ = "closings"
    __table_args__ = (
        CheckConstraint("people >= 0", name="ck_closings_people"),
        CheckConstraint("subtotal >= 0", name="ck_closings_subtotal"),
        CheckConstraint("discount >= 0", name="ck_closings_discount"),
        CheckConstraint("total >= 0", name="ck_closings_total"),
        CheckConstraint(
            "closing_time >= opening_time",
            name="ck_closings_time_range",
        ),
        {"schema": "public"},
    )

    model_config = ConfigDict(from_attributes=True)

    id: Mapped[int] = mapped_column(primary_key=True)
    table_id: Mapped[int] = mapped_column(ForeignKey(OpenTableModel.id))
    table_number: Mapped[int]
    table_name: Mapped[Optional[str]]
    opening_time: Mapped[datetime]
    closing_time: Mapped[datetime] = mapped_column(
        default=datetime.now,
        index=True,
    )
    people: Mapped[int]
    served_by: Mapped[int] = mapped_column(ForeignKey(UserModel.id))
    subtotal: Mapped[int]
    discount: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int]
    status: Mapped[str] = mapped_column(
        Enum(*SALE_STATUSES, name="sale_status", native_enum=False),
        default="cerrada",
    )
    cash_closing_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey(CashClosingModel.id),
        index=True,
    )

    table: Mapped["OpenTableModel"] = relationship()
    server: Mapped["UserModel"] = relationship()
    cash_closing: Mapped[Optional["CashClosingModel"]] = relationship(
        back_populates="sales",
    )
    items: Mapped[List["ClosingItemModel"]] = relationship(
        back_populates="closing",
        cascade="all, delete-orphan",
    )
    payments: Mapped[List["ClosingPaymentModel"]] = relationship(
        back_populates="closing",
        cascade="all, delete-orphan",
    )
    invoice: Mapped[Optional["InvoiceModel"]] = relationship(
        back_populates="closing",
        cascade="all, delete-orphan",
        uselist=False,
    )

    @property
    def products(self) -> list["ProductModel"]:
        return [item.product for item in self.items if item.product is not None]

    @property
    def payment_type(self) -> str | None:
        if len(self.payments) == 1:
            return self.payments[0].method
        return None

    @property
    def detail(self) -> list[dict]:
        return [
            {
                "product_id": item.product_id,
                "name": item.product_name,
                "type": item.product_type,
                "unit": item.unit,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "subtotal": item.subtotal,
            }
            for item in self.items
        ]


class ClosingItemModel(Base):
    __tablename__ = "closing_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_closing_items_quantity"),
        CheckConstraint("unit_price >= 0", name="ck_closing_items_unit_price"),
        CheckConstraint("subtotal >= 0", name="ck_closing_items_subtotal"),
        {"schema": "public"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    closing_id: Mapped[int] = mapped_column(
        ForeignKey(ClosingsModel.id, ondelete="CASCADE"),
        index=True,
    )
    product_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey(ProductModel.id, ondelete="SET NULL"),
    )
    product_name: Mapped[str]
    product_type: Mapped[str] = mapped_column(String(30))
    unit: Mapped[str]
    quantity: Mapped[int]
    unit_price: Mapped[int]
    subtotal: Mapped[int]

    closing: Mapped["ClosingsModel"] = relationship(back_populates="items")
    product: Mapped[Optional["ProductModel"]] = relationship()


class ClosingPaymentModel(Base):
    __tablename__ = "closing_payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_closing_payments_amount"),
        UniqueConstraint(
            "closing_id",
            "method",
            name="uq_closing_payments_method",
        ),
        {"schema": "public"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    closing_id: Mapped[int] = mapped_column(
        ForeignKey(ClosingsModel.id, ondelete="CASCADE"),
        index=True,
    )
    method: Mapped[str] = mapped_column(
        Enum(*PAYMENT_METHODS, name="payment_method", native_enum=False),
    )
    amount: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    closing: Mapped["ClosingsModel"] = relationship(back_populates="payments")


class InvoiceModel(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint(
            "point_of_sale",
            "voucher_type",
            "voucher_number",
            name="uq_invoices_fiscal_number",
        ),
        CheckConstraint("point_of_sale > 0", name="ck_invoices_point_of_sale"),
        CheckConstraint("voucher_number > 0", name="ck_invoices_voucher_number"),
        {"schema": "public"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    closing_id: Mapped[int] = mapped_column(
        ForeignKey(ClosingsModel.id, ondelete="CASCADE"),
        unique=True,
    )
    voucher_type: Mapped[str] = mapped_column(String(20))
    point_of_sale: Mapped[int]
    voucher_number: Mapped[int]
    issued_at: Mapped[datetime] = mapped_column(default=datetime.now)
    cae: Mapped[Optional[str]] = mapped_column(String(30))
    cae_expiration: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(
        Enum(*INVOICE_STATUSES, name="invoice_status", native_enum=False),
        default="pendiente",
    )
    afip_request: Mapped[Optional[dict]] = mapped_column(JSONB)
    afip_response: Mapped[Optional[dict]] = mapped_column(JSONB)

    closing: Mapped["ClosingsModel"] = relationship(back_populates="invoice")
    attempts: Mapped[List["InvoiceAttemptModel"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="InvoiceAttemptModel.attempted_at",
    )


class InvoiceAttemptModel(Base):
    __tablename__ = "invoice_attempts"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey(InvoiceModel.id, ondelete="CASCADE"),
        index=True,
    )
    attempted_at: Mapped[datetime] = mapped_column(
        default=datetime.now,
        index=True,
    )
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[Optional[str]] = mapped_column(Text)
    request_payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    response_payload: Mapped[Optional[dict]] = mapped_column(JSONB)

    invoice: Mapped["InvoiceModel"] = relationship(back_populates="attempts")


class SalesGoalModel(Base):
    __tablename__ = "sales_goals"
    __table_args__ = (
        CheckConstraint("target_amount > 0", name="ck_sales_goals_amount"),
        CheckConstraint("end_date >= start_date", name="ck_sales_goals_dates"),
        {"schema": "public"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    period: Mapped[str] = mapped_column(
        Enum(*GOAL_PERIODS, name="goal_period", native_enum=False),
        index=True,
    )
    target_amount: Mapped[int]
    description: Mapped[Optional[str]] = mapped_column(Text)
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date] = mapped_column(Date)
    created_by_id: Mapped[int] = mapped_column(ForeignKey(UserModel.id))
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now,
        onupdate=datetime.now,
    )
    deleted_at: Mapped[Optional[datetime]]

    created_by: Mapped["UserModel"] = relationship()


class StockMovementModel(Base):
    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint(
            "quantity_delta <> 0",
            name="ck_stock_movements_quantity_delta",
        ),
        CheckConstraint(
            "stock_before >= 0",
            name="ck_stock_movements_stock_before",
        ),
        CheckConstraint(
            "stock_after >= 0",
            name="ck_stock_movements_stock_after",
        ),
        {"schema": "public"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey(ProductModel.id),
        index=True,
    )
    closing_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey(ClosingsModel.id, ondelete="SET NULL"),
        index=True,
    )
    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey(UserModel.id),
    )
    movement_type: Mapped[str] = mapped_column(
        Enum(
            *STOCK_MOVEMENT_TYPES,
            name="stock_movement_type",
            native_enum=False,
        ),
        index=True,
    )
    quantity_delta: Mapped[int]
    stock_before: Mapped[int]
    stock_after: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.now,
        index=True,
    )
    note: Mapped[Optional[str]] = mapped_column(Text)

    product: Mapped["ProductModel"] = relationship()
    closing: Mapped[Optional["ClosingsModel"]] = relationship()
    created_by: Mapped[Optional["UserModel"]] = relationship()
