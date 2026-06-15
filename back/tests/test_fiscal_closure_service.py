from datetime import date
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from closings.models.closing_models import ClosurePeriodRequest
from closings.service.fiscal_closure_service import FiscalClosureService
from db.db_models import (
    CashClosingModel,
    ClosingPaymentModel,
    ClosingsModel,
    FiscalClosureModel,
    InvoiceModel,
)
from invoices.service.invoice_service import (
    INVOICE_AUTHORIZED,
    INVOICE_AUTHORIZING,
    INVOICE_PENDING,
    INVOICE_REJECTED,
    InvoiceService,
)
from shared.time_utils import local_now


def _sale(sale_id: int, total: int = 1000) -> ClosingsModel:
    sale = ClosingsModel(
        id=sale_id,
        table_id=1,
        table_number=sale_id,
        opening_time=local_now(),
        closing_time=local_now(),
        business_date=local_now().date(),
        people=2,
        served_by=1,
        subtotal=total,
        discount=0,
        total=total,
        status="cerrada",
        invoicing_status="SALE_INVOICING_PENDING",
        items=[],
        payments=[
            ClosingPaymentModel(
                id=sale_id,
                method="tarjeta_debito",
                amount=total,
            )
        ],
    )
    cash_closing = CashClosingModel(
        id=100 + sale_id,
        business_date=sale.business_date,
        closed_at=local_now(),
        closed_by_id=1,
        total_sales=total,
        expected_cash=0,
        counted_cash=0,
        difference=0,
        status="cerrado",
        sales=[sale],
    )
    sale.cash_closing_id = cash_closing.id
    sale.cash_closing = cash_closing
    return sale


def _invoice(
    invoice_id: int,
    sale: ClosingsModel,
    status: str = INVOICE_AUTHORIZED,
    total: int | None = None,
) -> InvoiceModel:
    now = local_now()
    invoice = InvoiceModel(
        id=invoice_id,
        closings=[sale],
        voucher_type="Factura B",
        point_of_sale=1,
        voucher_number=invoice_id,
        issued_at=now,
        declaration_type="ticket",
        total=sale.total if total is None else total,
        sales_count=1,
        period_start=None,
        period_end=None,
        status=status,
        created_at=now,
        updated_at=now,
        attempts=[],
    )
    invoice.fiscal_payload_json = InvoiceService._request_payload(invoice)
    return invoice


def _payload() -> ClosurePeriodRequest:
    return ClosurePeriodRequest(
        periodFrom=date(2026, 6, 15),
        periodTo=date(2026, 6, 15),
        periodType="DAY",
    )


def _service(
    sales: list[ClosingsModel],
    invoices: list[InvoiceModel],
    orphans: list[InvoiceModel] | None = None,
) -> FiscalClosureService:
    service = FiscalClosureService(MagicMock())
    service.closing_repository = MagicMock()
    service.invoice_repository = MagicMock()
    service.repository = MagicMock()
    service.closing_repository.get_period_sales.return_value = sales
    service.invoice_repository.get_for_sales_period.return_value = invoices
    service.invoice_repository.get_orphans_issued_in_period.return_value = (
        orphans or []
    )
    service.invoice_repository.get_duplicate_sale_invoice_rows.return_value = (
        []
    )
    service.table_repository = MagicMock()
    service.table_repository.get_active_before.return_value = []
    service.repository.get_declared_period.return_value = None
    return service


def test_period_summary_calculates_invoice_counts_and_totals():
    authorized_sale = _sale(1, 1000)
    pending_sale = _sale(2, 2000)
    rejected_sale = _sale(3, 3000)
    without_invoice = _sale(4, 4000)
    invoices = [
        _invoice(1, authorized_sale, INVOICE_AUTHORIZED),
        _invoice(2, pending_sale, INVOICE_PENDING),
        _invoice(3, rejected_sale, INVOICE_REJECTED),
    ]
    service = _service(
        [
            authorized_sale,
            pending_sale,
            rejected_sale,
            without_invoice,
        ],
        invoices,
    )

    summary = service.get_period_summary(
        date(2026, 6, 15),
        date(2026, 6, 15),
    )

    assert summary.sales_count == 4
    assert summary.total_sales_amount == 10000
    assert summary.invoices_count == 3
    assert summary.authorized_invoices_count == 1
    assert summary.pending_invoices_count == 1
    assert summary.rejected_invoices_count == 1
    assert summary.sales_without_invoice_count == 1
    assert summary.total_authorized_amount == 1000
    assert summary.total_pending_amount == 2000
    assert summary.total_rejected_amount == 3000


@pytest.mark.parametrize(
    ("invoice_status", "issue_type"),
    [
        (INVOICE_PENDING, "INVOICE_PENDING"),
        (INVOICE_AUTHORIZING, "INVOICE_AUTHORIZING"),
        (INVOICE_REJECTED, "INVOICE_REJECTED"),
    ],
)
def test_validation_blocks_pending_and_rejected_invoices(
    invoice_status,
    issue_type,
):
    sale = _sale(1)
    invoice = _invoice(1, sale, invoice_status)
    service = _service([sale], [invoice])

    validation = service.validate_period(
        _payload(),
        persist_issues=False,
    )

    assert validation.can_declare is False
    assert validation.status == "CLOSURE_BLOCKED"
    assert any(
        issue.issue_type == issue_type
        and issue.severity == "BLOCKING"
        for issue in validation.issues
    )


def test_validation_blocks_sale_without_invoice_and_amount_mismatch():
    missing = _sale(1, 1000)
    mismatched_sale = _sale(2, 2000)
    mismatched_invoice = _invoice(
        2,
        mismatched_sale,
        INVOICE_AUTHORIZED,
        total=1500,
    )
    mismatched_invoice.fiscal_payload_json["total_amount"] = 1500
    service = _service(
        [missing, mismatched_sale],
        [mismatched_invoice],
    )

    validation = service.validate_period(
        _payload(),
        persist_issues=False,
    )

    issue_types = {issue.issue_type for issue in validation.issues}
    assert "SALE_WITHOUT_INVOICE" in issue_types
    assert "INVOICE_AMOUNT_MISMATCH" in issue_types
    assert validation.can_declare is False


def test_validation_blocks_period_with_an_open_table():
    service = _service([], [])
    service.table_repository.get_active_before.return_value = [
        MagicMock(table_number=12)
    ]

    validation = service.validate_period(
        _payload(),
        persist_issues=False,
    )

    assert validation.can_declare is False
    assert any(
        issue.issue_type == "OPEN_TABLE_IN_PERIOD"
        and "mesa 12" in issue.description
        for issue in validation.issues
    )


def test_validation_blocks_sale_without_cash_closing():
    sale = _sale(1)
    sale.cash_closing_id = None
    sale.cash_closing = None
    invoice = _invoice(1, sale, INVOICE_AUTHORIZED)
    service = _service([sale], [invoice])

    validation = service.validate_period(
        _payload(),
        persist_issues=False,
    )

    assert validation.can_declare is False
    assert any(
        issue.issue_type == "SALE_WITHOUT_CASH_CLOSING"
        for issue in validation.issues
    )


def test_validation_blocks_inconsistent_cash_closing():
    sale = _sale(1)
    sale.cash_closing.total_sales = sale.total + 1
    invoice = _invoice(1, sale, INVOICE_AUTHORIZED)
    service = _service([sale], [invoice])

    validation = service.validate_period(
        _payload(),
        persist_issues=False,
    )

    assert validation.can_declare is False
    assert any(
        issue.issue_type == "CASH_CLOSING_TOTAL_MISMATCH"
        for issue in validation.issues
    )


def test_declare_period_creates_closure_with_authorized_invoices():
    sale = _sale(1, 2500)
    invoice = _invoice(1, sale, INVOICE_AUTHORIZED)
    service = _service([sale], [invoice])
    captured = {}

    def add_closure(closure):
        closure.id = 8
        captured["closure"] = closure

    service.repository.add.side_effect = add_closure
    service.repository.get_by_id.side_effect = (
        lambda _: captured["closure"]
    )

    result = service.declare_period(_payload())

    assert result.already_declared is False
    assert result.closure.status == "CLOSURE_DECLARED"
    assert result.closure.total_sales_amount == 2500
    assert result.closure.total_authorized_amount == 2500
    assert result.closure.invoices[0].id == invoice.id
    service.repository.add.assert_called_once()
    service.session.commit.assert_called_once()


def test_declare_period_is_idempotent():
    now = local_now()
    closure = FiscalClosureModel(
        id=9,
        period_type="DAY",
        period_from=date(2026, 6, 15),
        period_to=date(2026, 6, 15),
        status="CLOSURE_DECLARED",
        total_sales_amount=0,
        total_authorized_amount=0,
        total_pending_amount=0,
        total_rejected_amount=0,
        sales_count=0,
        invoices_count=0,
        authorized_invoices_count=0,
        pending_invoices_count=0,
        rejected_invoices_count=0,
        sales_without_invoice_count=0,
        declared_at=now,
        created_at=now,
        updated_at=now,
        invoices=[],
        validation_issues=[],
    )
    service = _service([], [])
    service.repository.get_declared_period.return_value = closure

    result = service.declare_period(_payload())

    assert result.already_declared is True
    assert result.closure.id == closure.id
    service.repository.add.assert_not_called()
    service.session.commit.assert_not_called()


def test_validate_declared_period_is_not_declarable_again():
    now = local_now()
    closure = FiscalClosureModel(
        id=9,
        period_type="DAY",
        period_from=date(2026, 6, 15),
        period_to=date(2026, 6, 15),
        status="CLOSURE_DECLARED",
        total_sales_amount=0,
        total_authorized_amount=0,
        total_pending_amount=0,
        total_rejected_amount=0,
        sales_count=0,
        invoices_count=0,
        authorized_invoices_count=0,
        pending_invoices_count=0,
        rejected_invoices_count=0,
        sales_without_invoice_count=0,
        declared_at=now,
        created_at=now,
        updated_at=now,
        invoices=[],
        validation_issues=[],
    )
    service = _service([], [])
    service.repository.get_declared_period.return_value = closure

    validation = service.validate_period(
        _payload(),
        persist_issues=False,
    )

    assert validation.can_declare is False
    assert validation.status == "CLOSURE_DECLARED"


def test_declare_period_returns_clear_blocking_error():
    sale = _sale(1)
    invoice = _invoice(1, sale, INVOICE_PENDING)
    service = _service([sale], [invoice])

    with pytest.raises(HTTPException) as error:
        service.declare_period(_payload())

    assert error.value.status_code == 409
    assert error.value.detail["code"] == "CLOSURE_BLOCKED"
    assert error.value.detail["issues"][0]["severity"] == "BLOCKING"
