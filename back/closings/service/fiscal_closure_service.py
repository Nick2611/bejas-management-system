from datetime import date, datetime, time, timedelta
from http import HTTPStatus

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from closings.models.closing_models import (
    ClosurePeriodRequest,
    ClosureValidationIssueResponse,
    ClosureValidationResponse,
    DeclarePeriodResponse,
    FiscalClosureResponse,
    FiscalPeriodSummaryResponse,
)
from closings.repository.closing_repository import (
    ClosingRepository,
    FiscalClosureRepository,
)
from db.db_models import (
    CashClosingModel,
    ClosureValidationIssueModel,
    ClosingsModel,
    FiscalClosureModel,
    InvoiceModel,
)
from invoices.afip_client import InvalidFiscalPayloadError
from invoices.repository.invoice_repository import InvoiceRepository
from invoices.service.invoice_service import (
    INVOICE_AUTHORIZED,
    INVOICE_AUTHORIZING,
    INVOICE_PENDING,
    INVOICE_QUEUED,
    INVOICE_REJECTED,
    INVOICE_RETRY_PENDING,
    InvoiceService,
)
from shared.time_utils import local_now
from shared.utils import commit_session
from tables.repository.table_repository import TableRepository


class FiscalClosureService:
    def __init__(self, session: Session):
        self.session = session
        self.closing_repository = ClosingRepository(session)
        self.invoice_repository = InvoiceRepository(session)
        self.repository = FiscalClosureRepository(session)
        self.table_repository = TableRepository(session)

    @staticmethod
    def _bounds(
        period_from: date,
        period_to: date,
    ) -> tuple[datetime, datetime]:
        return (
            datetime.combine(period_from, time.min),
            datetime.combine(period_to + timedelta(days=1), time.min),
        )

    @staticmethod
    def _issue_response(
        issue: ClosureValidationIssueModel,
    ) -> ClosureValidationIssueResponse:
        return ClosureValidationIssueResponse(
            issue_type=issue.issue_type,
            severity=issue.severity,
            sale_id=issue.sale_id,
            invoice_id=issue.invoice_id,
            description=issue.description,
            suggested_action=issue.suggested_action,
        )

    @staticmethod
    def _new_issue(
        *,
        period_from: date,
        period_to: date,
        issue_type: str,
        severity: str = "BLOCKING",
        sale_id: int | None = None,
        invoice_id: int | None = None,
        description: str,
        suggested_action: str,
    ) -> ClosureValidationIssueModel:
        return ClosureValidationIssueModel(
            period_from=period_from,
            period_to=period_to,
            issue_type=issue_type,
            severity=severity,
            sale_id=sale_id,
            invoice_id=invoice_id,
            description=description,
            suggested_action=suggested_action,
            created_at=local_now(),
        )

    def _period_data(
        self,
        period_from: date,
        period_to: date,
    ) -> tuple[list, list[InvoiceModel], list[InvoiceModel]]:
        start, end = self._bounds(period_from, period_to)
        sales = self.closing_repository.get_period_sales(start, end)
        invoices = self.invoice_repository.get_for_sales_period(start, end)
        orphans = self.invoice_repository.get_orphans_issued_in_period(
            start,
            end,
        )
        return sales, invoices, orphans

    @staticmethod
    def _payment_totals(sales: list[ClosingsModel]) -> dict[str, int]:
        totals = {
            "efectivo": 0,
            "tarjeta_credito": 0,
            "tarjeta_debito": 0,
            "mercado_pago": 0,
        }
        for sale in sales:
            sale_totals = {method: 0 for method in totals}
            for payment in sale.payments:
                sale_totals[payment.method] += payment.amount

            excess = max(sum(sale_totals.values()) - sale.total, 0)
            for method in (
                "efectivo",
                "mercado_pago",
                "tarjeta_debito",
                "tarjeta_credito",
            ):
                if excess == 0:
                    break
                returned = min(sale_totals[method], excess)
                sale_totals[method] -= returned
                excess -= returned

            for method, amount in sale_totals.items():
                totals[method] += amount
        return totals

    def get_period_summary(
        self,
        period_from: date,
        period_to: date,
    ) -> FiscalPeriodSummaryResponse:
        sales, related_invoices, orphan_invoices = self._period_data(
            period_from,
            period_to,
        )
        fiscal_sales = [
            sale
            for sale in sales
            if sale.status != "anulada" and sale.total > 0
        ]
        invoices_by_id = {
            invoice.id: invoice
            for invoice in [*related_invoices, *orphan_invoices]
        }
        invoices = list(invoices_by_id.values())
        statuses = {
            invoice.id: InvoiceService._normalized_status(invoice.status)
            for invoice in invoices
        }
        pending_statuses = {
            INVOICE_PENDING,
            INVOICE_QUEUED,
            INVOICE_AUTHORIZING,
            INVOICE_RETRY_PENDING,
        }
        authorized = [
            invoice
            for invoice in invoices
            if statuses[invoice.id] == INVOICE_AUTHORIZED
        ]
        pending = [
            invoice
            for invoice in invoices
            if statuses[invoice.id] in pending_statuses
        ]
        rejected = [
            invoice
            for invoice in invoices
            if statuses[invoice.id] == INVOICE_REJECTED
        ]
        return FiscalPeriodSummaryResponse(
            period_from=period_from,
            period_to=period_to,
            sales_count=len(fiscal_sales),
            total_sales_amount=sum(sale.total for sale in fiscal_sales),
            invoices_count=len(invoices),
            authorized_invoices_count=len(authorized),
            pending_invoices_count=len(pending),
            rejected_invoices_count=len(rejected),
            sales_without_invoice_count=sum(
                sale.invoice is None for sale in fiscal_sales
            ),
            total_authorized_amount=sum(
                invoice.total for invoice in authorized
            ),
            total_pending_amount=sum(invoice.total for invoice in pending),
            total_rejected_amount=sum(
                invoice.total for invoice in rejected
            ),
        )

    def _find_issues(
        self,
        payload: ClosurePeriodRequest,
    ) -> list[ClosureValidationIssueModel]:
        start, end = self._bounds(
            payload.period_from,
            payload.period_to,
        )
        sales, invoices, orphan_invoices = self._period_data(
            payload.period_from,
            payload.period_to,
        )
        issues: list[ClosureValidationIssueModel] = []
        cash_closings: dict[int, CashClosingModel] = {}

        for table in self.table_repository.get_active_before(end):
            issues.append(
                self._new_issue(
                    period_from=payload.period_from,
                    period_to=payload.period_to,
                    issue_type="OPEN_TABLE_IN_PERIOD",
                    description=(
                        f"La mesa {table.table_number} sigue abierta dentro "
                        "del período fiscal."
                    ),
                    suggested_action=(
                        "Cierre o libere la mesa antes de declarar el período."
                    ),
                )
            )

        for sale in sales:
            if sale.status == "anulada":
                continue
            paid_total = sum(payment.amount for payment in sale.payments)
            if sale.subtotal - sale.discount != sale.total:
                issues.append(
                    self._new_issue(
                        period_from=payload.period_from,
                        period_to=payload.period_to,
                        issue_type="SALE_TOTAL_MISMATCH",
                        sale_id=sale.id,
                        description=(
                            f"La venta {sale.id} no coincide con su subtotal "
                            "y descuento."
                        ),
                        suggested_action=(
                            "Corrija los importes antes de declarar el período."
                        ),
                    )
                )
            if paid_total < sale.total:
                issues.append(
                    self._new_issue(
                        period_from=payload.period_from,
                        period_to=payload.period_to,
                        issue_type="SALE_PAYMENT_MISMATCH",
                        sale_id=sale.id,
                        description=(
                            f"La venta {sale.id} totaliza {sale.total}, pero "
                            f"sus pagos suman {paid_total}."
                        ),
                        suggested_action=(
                            "Corrija o complete los pagos de la venta."
                        ),
                    )
                )
            if sale.cash_closing_id is None:
                issues.append(
                    self._new_issue(
                        period_from=payload.period_from,
                        period_to=payload.period_to,
                        issue_type="SALE_WITHOUT_CASH_CLOSING",
                        sale_id=sale.id,
                        description=(
                            f"La venta {sale.id} no está incluida en un "
                            "cierre de caja."
                        ),
                        suggested_action=(
                            "Realice el cierre de caja pendiente para la venta."
                        ),
                    )
                )
            elif sale.cash_closing is not None:
                cash_closings[sale.cash_closing_id] = sale.cash_closing

            if sale.total > 0 and sale.invoice is None:
                issues.append(
                    self._new_issue(
                        period_from=payload.period_from,
                        period_to=payload.period_to,
                        issue_type="SALE_WITHOUT_INVOICE",
                        sale_id=sale.id,
                        description=(
                            f"La venta {sale.id} no tiene factura asociada."
                        ),
                        suggested_action=(
                            "Genere y encole el comprobante de la venta."
                        ),
                    )
                )

        for cash_closing in cash_closings.values():
            closing_sales = [
                sale
                for sale in cash_closing.sales
                if sale.status == "cerrada"
            ]
            expected_total = sum(sale.total for sale in closing_sales)
            expected_cash = self._payment_totals(closing_sales)["efectivo"]
            if cash_closing.status != "cerrado":
                issues.append(
                    self._new_issue(
                        period_from=payload.period_from,
                        period_to=payload.period_to,
                        issue_type="CASH_CLOSING_NOT_CLOSED",
                        description=(
                            f"El cierre de caja {cash_closing.id} no está "
                            "en estado cerrado."
                        ),
                        suggested_action="Complete el cierre de caja.",
                    )
                )
            if (
                cash_closing.total_sales != expected_total
                or cash_closing.expected_cash != expected_cash
            ):
                issues.append(
                    self._new_issue(
                        period_from=payload.period_from,
                        period_to=payload.period_to,
                        issue_type="CASH_CLOSING_TOTAL_MISMATCH",
                        description=(
                            f"El cierre de caja {cash_closing.id} no coincide "
                            "con las ventas y pagos asociados."
                        ),
                        suggested_action=(
                            "Revise los totales del cierre de caja."
                        ),
                    )
                )

        for invoice in orphan_invoices:
            issues.append(
                self._new_issue(
                    period_from=payload.period_from,
                    period_to=payload.period_to,
                    issue_type="INVOICE_WITHOUT_SALE",
                    invoice_id=invoice.id,
                    description=(
                        f"La factura {invoice.id} no tiene venta asociada."
                    ),
                    suggested_action=(
                        "Vincule la factura con su venta o anúlela."
                    ),
                )
            )

        for invoice in invoices:
            status = InvoiceService._normalized_status(invoice.status)
            sale_id = (
                invoice.closings[0].id
                if len(invoice.closings) == 1
                else None
            )
            if status in {
                INVOICE_PENDING,
                INVOICE_QUEUED,
                INVOICE_RETRY_PENDING,
            }:
                issues.append(
                    self._new_issue(
                        period_from=payload.period_from,
                        period_to=payload.period_to,
                        issue_type="INVOICE_PENDING",
                        sale_id=sale_id,
                        invoice_id=invoice.id,
                        description=(
                            f"La factura {invoice.id} está pendiente "
                            "de autorización."
                        ),
                        suggested_action=(
                            "Reintente la autorización del comprobante."
                        ),
                    )
                )
            elif status == INVOICE_AUTHORIZING:
                issues.append(
                    self._new_issue(
                        period_from=payload.period_from,
                        period_to=payload.period_to,
                        issue_type="INVOICE_AUTHORIZING",
                        sale_id=sale_id,
                        invoice_id=invoice.id,
                        description=(
                            f"La factura {invoice.id} todavía está siendo "
                            "procesada por el worker."
                        ),
                        suggested_action=(
                            "Espere al worker o recupere el intento si "
                            "superó el tiempo máximo."
                        ),
                    )
                )
            elif status == INVOICE_REJECTED:
                issues.append(
                    self._new_issue(
                        period_from=payload.period_from,
                        period_to=payload.period_to,
                        issue_type="INVOICE_REJECTED",
                        sale_id=sale_id,
                        invoice_id=invoice.id,
                        description=(
                            f"La factura {invoice.id} fue rechazada: "
                            f"{invoice.rejection_reason or 'sin detalle'}."
                        ),
                        suggested_action=(
                            "Revise los datos fiscales y reintente "
                            "el comprobante."
                        ),
                    )
                )

            expected_total = sum(sale.total for sale in invoice.closings)
            if invoice.closings and invoice.total != expected_total:
                issues.append(
                    self._new_issue(
                        period_from=payload.period_from,
                        period_to=payload.period_to,
                        issue_type="INVOICE_AMOUNT_MISMATCH",
                        sale_id=sale_id,
                        invoice_id=invoice.id,
                        description=(
                            f"La factura {invoice.id} totaliza "
                            f"{invoice.total}, pero sus ventas totalizan "
                            f"{expected_total}."
                        ),
                        suggested_action=(
                            "Corrija el importe antes de declarar el período."
                        ),
                    )
                )

            try:
                InvoiceService._validate_fiscal_payload(
                    invoice,
                    invoice.fiscal_payload_json,
                )
            except InvalidFiscalPayloadError as error:
                issues.append(
                    self._new_issue(
                        period_from=payload.period_from,
                        period_to=payload.period_to,
                        issue_type="INVALID_FISCAL_PAYLOAD",
                        sale_id=sale_id,
                        invoice_id=invoice.id,
                        description=(
                            f"El payload fiscal de la factura {invoice.id} "
                            f"es inválido: {error}."
                        ),
                        suggested_action=(
                            "Regenerar o corregir el payload fiscal."
                        ),
                    )
                )

            if (
                status == INVOICE_AUTHORIZED
                and any(sale.status == "anulada" for sale in invoice.closings)
            ):
                issues.append(
                    self._new_issue(
                        period_from=payload.period_from,
                        period_to=payload.period_to,
                        issue_type="CANCELLED_SALE_AUTHORIZED_INVOICE",
                        sale_id=sale_id,
                        invoice_id=invoice.id,
                        description=(
                            "Existe una venta anulada con una factura "
                            "autorizada sin reversa registrada."
                        ),
                        suggested_action=(
                            "Registre la nota de crédito o el mecanismo "
                            "de reversa correspondiente."
                        ),
                    )
                )

        for sale_id, invoice_count in (
            self.invoice_repository.get_duplicate_sale_invoice_rows(
                start,
                end,
            )
        ):
            issues.append(
                self._new_issue(
                    period_from=payload.period_from,
                    period_to=payload.period_to,
                    issue_type="DUPLICATE_INVOICE_FOR_SALE",
                    sale_id=sale_id,
                    description=(
                        f"La venta {sale_id} tiene {invoice_count} "
                        "facturas asociadas."
                    ),
                    suggested_action=(
                        "Conserve un único comprobante válido para la venta."
                    ),
                )
            )
        return issues

    def validate_period(
        self,
        payload: ClosurePeriodRequest,
        *,
        persist_issues: bool = True,
    ) -> ClosureValidationResponse:
        existing = self.repository.get_declared_period(
            payload.period_type,
            payload.period_from,
            payload.period_to,
        )
        summary = self.get_period_summary(
            payload.period_from,
            payload.period_to,
        )
        if existing is not None:
            return ClosureValidationResponse(
                can_declare=False,
                status="CLOSURE_DECLARED",
                summary=summary,
                issues=[],
                existing_closure_id=existing.id,
                message=(
                    "Este período ya fue declarado. "
                    "No se generará una nueva declaración."
                ),
            )

        issue_models = self._find_issues(payload)
        if persist_issues:
            self.repository.replace_period_issues(
                payload.period_from,
                payload.period_to,
                issue_models,
            )
            commit_session(self.session)
        issues = [
            self._issue_response(issue)
            for issue in issue_models
        ]
        has_blocking = any(
            issue.severity == "BLOCKING" for issue in issue_models
        )
        return ClosureValidationResponse(
            can_declare=not has_blocking,
            status=(
                "CLOSURE_BLOCKED"
                if has_blocking
                else "CLOSURE_READY"
            ),
            summary=summary,
            issues=issues,
            message=(
                "El período no puede declararse porque tiene "
                "inconsistencias bloqueantes."
                if has_blocking
                else "El período está listo para declarar."
            ),
        )

    def _closure_response(
        self,
        closure: FiscalClosureModel,
    ) -> FiscalClosureResponse:
        return FiscalClosureResponse(
            id=closure.id,
            period_type=closure.period_type,
            period_from=closure.period_from,
            period_to=closure.period_to,
            status=closure.status,
            total_sales_amount=closure.total_sales_amount,
            total_authorized_amount=closure.total_authorized_amount,
            total_pending_amount=closure.total_pending_amount,
            total_rejected_amount=closure.total_rejected_amount,
            sales_count=closure.sales_count,
            invoices_count=closure.invoices_count,
            authorized_invoices_count=closure.authorized_invoices_count,
            pending_invoices_count=closure.pending_invoices_count,
            rejected_invoices_count=closure.rejected_invoices_count,
            sales_without_invoice_count=(
                closure.sales_without_invoice_count
            ),
            declared_at=closure.declared_at,
            created_at=closure.created_at,
            updated_at=closure.updated_at,
            invoices=[
                InvoiceService._response(invoice)
                for invoice in closure.invoices
            ],
            issues=[
                self._issue_response(issue)
                for issue in closure.validation_issues
            ],
        )

    def declare_period(
        self,
        payload: ClosurePeriodRequest,
    ) -> DeclarePeriodResponse:
        existing = self.repository.get_declared_period(
            payload.period_type,
            payload.period_from,
            payload.period_to,
        )
        if existing is not None:
            return DeclarePeriodResponse(
                closure=self._closure_response(existing),
                already_declared=True,
                message=(
                    "Este período ya fue declarado. "
                    "No se generó una nueva declaración."
                ),
            )

        validation = self.validate_period(
            payload,
            persist_issues=False,
        )
        if not validation.can_declare:
            issue_models = self._find_issues(payload)
            self.repository.replace_period_issues(
                payload.period_from,
                payload.period_to,
                issue_models,
            )
            commit_session(self.session)
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail=jsonable_encoder(
                    {
                        "code": "CLOSURE_BLOCKED",
                        "message": (
                            "El período no puede declararse porque "
                            "tiene inconsistencias bloqueantes."
                        ),
                        "summary": validation.summary,
                        "issues": validation.issues,
                    }
                ),
            )

        start, end = self._bounds(
            payload.period_from,
            payload.period_to,
        )
        authorized_invoices = [
            invoice
            for invoice in self.invoice_repository.get_for_sales_period(
                start,
                end,
            )
            if InvoiceService._normalized_status(invoice.status)
            == INVOICE_AUTHORIZED
        ]
        now = local_now()
        summary = validation.summary
        closure = FiscalClosureModel(
            period_type=payload.period_type,
            period_from=payload.period_from,
            period_to=payload.period_to,
            status="CLOSURE_DECLARED",
            total_sales_amount=summary.total_sales_amount,
            total_authorized_amount=summary.total_authorized_amount,
            total_pending_amount=summary.total_pending_amount,
            total_rejected_amount=summary.total_rejected_amount,
            sales_count=summary.sales_count,
            invoices_count=summary.invoices_count,
            authorized_invoices_count=summary.authorized_invoices_count,
            pending_invoices_count=summary.pending_invoices_count,
            rejected_invoices_count=summary.rejected_invoices_count,
            sales_without_invoice_count=(
                summary.sales_without_invoice_count
            ),
            declared_at=now,
            created_at=now,
            updated_at=now,
            invoices=authorized_invoices,
        )
        self.repository.add(closure)
        self.repository.replace_period_issues(
            payload.period_from,
            payload.period_to,
            [],
        )
        try:
            commit_session(self.session)
        except IntegrityError:
            self.session.rollback()
            existing = self.repository.get_declared_period(
                payload.period_type,
                payload.period_from,
                payload.period_to,
            )
            if existing is None:
                raise
            return DeclarePeriodResponse(
                closure=self._closure_response(existing),
                already_declared=True,
                message=(
                    "Este período ya fue declarado por otro proceso. "
                    "No se generó una nueva declaración."
                ),
            )
        persisted = self.repository.get_by_id(closure.id)
        return DeclarePeriodResponse(
            closure=self._closure_response(persisted),
            already_declared=False,
            message="El período fue declarado correctamente.",
        )

    def get_closure_details(
        self,
        closure_id: int,
    ) -> FiscalClosureResponse:
        closure = self.repository.get_by_id(closure_id)
        if closure is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Declaración fiscal no encontrada",
            )
        return self._closure_response(closure)
