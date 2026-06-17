import { apiRequest } from './apiClient';
import type { PaymentMethod } from './tablesApi';

export interface InvoiceAttempt {
  id: number;
  invoice_id: number;
  attempt_number: number;
  attempted_at: string;
  previous_status: string;
  new_status: string;
  request_payload: Record<string, unknown> | null;
  response_payload: Record<string, unknown> | null;
  error_reason: string | null;
  worker_id: string | null;
  correlation_id: string | null;
  success: boolean;
  error: string | null;
}

export type InvoiceStatus =
  | 'INVOICE_PENDING'
  | 'INVOICE_QUEUED'
  | 'INVOICE_AUTHORIZING'
  | 'INVOICE_AUTHORIZED'
  | 'INVOICE_REJECTED'
  | 'INVOICE_CANCELLED'
  | 'INVOICE_RETRY_PENDING';

export interface Invoice {
  id: number;
  closing_id: number | null;
  closing_ids: number[];
  voucher_type: string;
  point_of_sale: number;
  voucher_number: number;
  display_number: string;
  issued_at: string;
  declaration_type: 'ticket' | 'diario' | 'mensual' | 'legacy';
  total: number;
  sales_count: number;
  period_start: string | null;
  period_end: string | null;
  cae: string | null;
  cae_expiration: string | null;
  authorization_code: string | null;
  authorization_date: string | null;
  rejection_reason: string | null;
  fiscal_payload_json: Record<string, unknown> | null;
  arca_response_json: Record<string, unknown> | null;
  status: InvoiceStatus;
  created_at: string;
  updated_at: string;
  attempts: InvoiceAttempt[];
}

export interface ClosingItem {
  id: number;
  product_id: number | null;
  product_name: string;
  product_type: string;
  unit: string;
  quantity: number;
  unit_price: number;
  subtotal: number;
}

export interface Closing {
  id: number;
  table_number: number;
  table_name: string | null;
  opening_time: string;
  closing_time: string;
  business_date: string;
  people: number;
  served_by: number;
  subtotal: number;
  discount: number;
  total: number;
  amount_received: number;
  change: number;
  status: string;
  invoicing_status: string;
  cash_closing_id: number | null;
  items: ClosingItem[];
  payments: Array<{ id: number; method: PaymentMethod; amount: number }>;
  invoice: Invoice | null;
}

export interface CashClosing {
  id: number;
  business_date: string;
  closed_at: string;
  closed_by_id: number;
  total_sales: number;
  expected_cash: number;
  counted_cash: number;
  difference: number;
  status: string;
  notes: string | null;
  sales_count: number;
  total_credit_card: number;
  total_debit_card: number;
  total_mercado_pago: number;
}

export interface CashClosingRevision {
  id: number;
  cash_closing_id: number;
  changed_by_id: number;
  changed_at: string;
  previous_counted_cash: number;
  new_counted_cash: number;
  previous_notes: string | null;
  new_notes: string | null;
}

export interface RetryInvoicePeriodResponse {
  status: 'encolado' | 'error' | 'sin_pendientes';
  message: string;
  queued_count: number;
  published_count: number;
  invoice_ids: number[];
  invoices: Invoice[];
  sales_count: number;
  total: number;
  invoice: Invoice | null;
}

export type FiscalPeriodType = 'DAY' | 'MONTH' | 'CUSTOM';

export interface FiscalPeriodRequest {
  periodFrom: string;
  periodTo: string;
  periodType: FiscalPeriodType;
}

export interface FiscalPeriodSummary {
  period_from: string;
  period_to: string;
  sales_count: number;
  total_sales_amount: number;
  invoices_count: number;
  authorized_invoices_count: number;
  pending_invoices_count: number;
  rejected_invoices_count: number;
  sales_without_invoice_count: number;
  total_authorized_amount: number;
  total_pending_amount: number;
  total_rejected_amount: number;
}

export interface ClosureValidationIssue {
  issue_type: string;
  severity: 'BLOCKING' | 'WARNING';
  sale_id: number | null;
  invoice_id: number | null;
  description: string;
  suggested_action: string;
}

export interface ClosureValidation {
  can_declare: boolean;
  status: 'CLOSURE_BLOCKED' | 'CLOSURE_READY' | 'CLOSURE_DECLARED';
  summary: FiscalPeriodSummary;
  issues: ClosureValidationIssue[];
  existing_closure_id: number | null;
  message: string;
}

export interface FiscalClosure {
  id: number;
  period_type: FiscalPeriodType;
  period_from: string;
  period_to: string;
  status: string;
  total_sales_amount: number;
  total_authorized_amount: number;
  total_pending_amount: number;
  total_rejected_amount: number;
  sales_count: number;
  invoices_count: number;
  authorized_invoices_count: number;
  pending_invoices_count: number;
  rejected_invoices_count: number;
  sales_without_invoice_count: number;
  declared_at: string | null;
  created_at: string;
  updated_at: string;
  invoices: Invoice[];
  issues: ClosureValidationIssue[];
}

export interface DeclareFiscalPeriodResponse {
  closure: FiscalClosure;
  already_declared: boolean;
  message: string;
}

export interface PendingInvoiceSummary {
  period: 'diario' | 'mensual';
  period_start: string;
  period_end: string;
  sales_count: number;
  total: number;
  cash_closing_exists: boolean;
  can_declare: boolean;
  blocking_reason: string | null;
}

export interface MonthlySummary {
  year: number;
  month: number;
  total_sales: number;
  sales_count: number;
  active_days: number;
  daily_average: number;
  total_cash: number;
  total_credit_card: number;
  total_debit_card: number;
  total_mercado_pago: number;
}

export interface Goal {
  id: number;
  period: 'diario' | 'semanal' | 'mensual';
  target_amount: number;
  description: string | null;
  start_date: string;
  end_date: string;
  created_by_id: number;
  created_at: string;
  updated_at: string;
  current_sales: number;
  progress: number;
}

export interface KpiSummary {
  daily: { total_sales: number; sales_count: number };
  weekly: { total_sales: number; sales_count: number };
  monthly: { total_sales: number; sales_count: number };
  employee_performance: Array<{
    user_id: number;
    username: string;
    closed_tables: number;
    total_sales: number;
  }>;
}

export const fetchClosings = () =>
  apiRequest<Closing[]>('/closings', {}, { fallback: 'No se pudieron cargar las ventas' });

export const fetchInvoices = () =>
  apiRequest<Invoice[]>('/invoices', {}, { fallback: 'No se pudieron cargar las facturas' });

export const retryInvoice = (id: number) =>
  apiRequest<Invoice>(`/invoices/${id}/retry`, { method: 'POST' }, {
    fallback: 'No se pudo reintentar la factura'
  });

export const fetchCashClosings = () =>
  apiRequest<CashClosing[]>('/cash-closings', {}, {
    fallback: 'No se pudieron cargar los cierres'
  });

export const createCashClosing = (
  businessDate: string,
  countedCash: number,
  notes?: string
) => apiRequest<CashClosing>('/cash-closings', {
  method: 'POST',
  body: JSON.stringify({
    business_date: businessDate,
    counted_cash: countedCash,
    notes: notes || null
  })
}, { fallback: 'No se pudo realizar el cierre' });

export const updateCashClosing = (
  id: number,
  payload: { counted_cash?: number; notes?: string | null }
) => apiRequest<CashClosing>(`/cash-closings/${id}`, {
  method: 'PATCH',
  body: JSON.stringify(payload)
}, { fallback: 'No se pudo corregir el cierre' });

export const fetchCashClosingRevisions = (id: number) =>
  apiRequest<CashClosingRevision[]>(
    `/cash-closings/${id}/revisions`,
    {},
    { fallback: 'No se pudo cargar el historial del cierre' }
  );

export const retryInvoicePeriod = (
  payload:
    | { period: 'diario'; date: string }
    | { period: 'mensual'; year: number; month: number }
    | {
      periodFrom: string;
      periodTo: string;
      statuses?: Array<
        'INVOICE_PENDING'
        | 'INVOICE_REJECTED'
        | 'INVOICE_RETRY_PENDING'
      >;
    }
) => apiRequest<RetryInvoicePeriodResponse>('/invoices/retry-period', {
  method: 'POST',
  body: JSON.stringify(payload)
}, { fallback: 'No se pudieron reintentar los comprobantes del período' });

export const fetchPendingInvoiceSummary = (
  payload:
    | { period: 'diario'; date: string }
    | { period: 'mensual'; year: number; month: number }
) => {
  const query = payload.period === 'diario'
    ? `period=diario&date=${encodeURIComponent(payload.date)}`
    : `period=mensual&year=${payload.year}&month=${payload.month}`;
  return apiRequest<PendingInvoiceSummary>(
    `/invoices/pending-summary?${query}`,
    {},
    { fallback: 'No se pudo cargar el resumen pendiente de AFIP' }
  );
};

export const fetchFiscalPeriodSummary = (
  periodFrom: string,
  periodTo: string
) => apiRequest<FiscalPeriodSummary>(
  `/closings/summary?from=${encodeURIComponent(periodFrom)}&to=${encodeURIComponent(periodTo)}`,
  {},
  { fallback: 'No se pudo cargar el resumen fiscal' }
);

export const validateFiscalPeriod = (payload: FiscalPeriodRequest) =>
  apiRequest<ClosureValidation>('/closings/validate', {
    method: 'POST',
    body: JSON.stringify(payload)
  }, { fallback: 'No se pudo validar el período' });

export const declareFiscalPeriod = (payload: FiscalPeriodRequest) =>
  apiRequest<DeclareFiscalPeriodResponse>('/closings/declare', {
    method: 'POST',
    body: JSON.stringify(payload)
  }, { fallback: 'No se pudo declarar el período' });

export const fetchMonthlySummary = (year: number, month: number) =>
  apiRequest<MonthlySummary>(
    `/cash-closings/monthly?year=${year}&month=${month}`,
    {},
    { fallback: 'No se pudo cargar el resumen mensual' }
  );

export const fetchGoals = () =>
  apiRequest<Goal[]>('/goals', {}, { fallback: 'No se pudieron cargar los objetivos' });

export const createGoal = (
  payload: Pick<Goal, 'period' | 'target_amount'> & { description?: string }
) => apiRequest<Goal>('/goals', {
  method: 'POST',
  body: JSON.stringify(payload)
}, { fallback: 'No se pudo crear el objetivo' });

export const updateGoal = (
  id: number,
  payload: Partial<Pick<Goal, 'period' | 'target_amount' | 'description'>>
) => apiRequest<Goal>(`/goals/${id}`, {
  method: 'PATCH',
  body: JSON.stringify(payload)
}, { fallback: 'No se pudo actualizar el objetivo' });

export const deleteGoal = (id: number) =>
  apiRequest<void>(`/goals/${id}`, { method: 'DELETE' }, {
    fallback: 'No se pudo eliminar el objetivo'
  });

export const fetchKpiSummary = () =>
  apiRequest<KpiSummary>('/kpis/summary', {}, {
    fallback: 'No se pudieron cargar los indicadores'
  });

export interface DailyKpiPoint {
  date: string;          // "YYYY-MM-DD"
  total_sales: number;
  sales_count: number;
  total_people: number;
}

export interface DailySalesHistory {
  days: DailyKpiPoint[];
  total_sales: number;
  max_day: number;
  avg_per_day: number;
  active_days: number;
}

export const fetchSalesHistory = (days = 60) =>
  apiRequest<DailySalesHistory>(`/kpis/daily-history?days=${days}`, {}, {
    fallback: 'No se pudo cargar el historial de ventas'
  });

export async function downloadInvoiceReport(date: string): Promise<void> {
  const report = await apiRequest<unknown>(`/invoices/report?date=${date}`, {}, {
    fallback: 'No se pudo generar el reporte'
  });
  const blob = new Blob([JSON.stringify(report, null, 2)], {
    type: 'application/json'
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `reporte-afip-${date}.json`;
  link.click();
  URL.revokeObjectURL(url);
}
