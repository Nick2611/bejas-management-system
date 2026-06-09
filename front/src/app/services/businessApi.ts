import { apiRequest } from './apiClient';
import type { PaymentMethod } from './tablesApi';

export interface InvoiceAttempt {
  id: number;
  attempted_at: string;
  success: boolean;
  error: string | null;
}

export interface Invoice {
  id: number;
  closing_id: number;
  voucher_type: string;
  point_of_sale: number;
  voucher_number: number;
  display_number: string;
  issued_at: string;
  cae: string | null;
  cae_expiration: string | null;
  status: 'pendiente' | 'autorizada' | 'rechazada' | 'anulada';
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
  people: number;
  served_by: number;
  subtotal: number;
  discount: number;
  total: number;
  amount_received: number;
  change: number;
  status: string;
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
  status: 'completado' | 'parcial' | 'error' | 'sin_pendientes';
  message: string;
  processed_count: number;
  authorized_count: number;
  failed_count: number;
  invoices: Invoice[];
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
) => apiRequest<RetryInvoicePeriodResponse>('/invoices/retry-period', {
  method: 'POST',
  body: JSON.stringify(payload)
}, { fallback: 'No se pudo procesar el período en AFIP' });

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
