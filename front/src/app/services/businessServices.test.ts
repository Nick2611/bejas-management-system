import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createCashClosing,
  createGoal,
  declareFiscalPeriod,
  fetchCashClosingRevisions,
  fetchFiscalPeriodSummary,
  fetchPendingInvoiceSummary,
  retryInvoicePeriod,
  updateCashClosing,
  validateFiscalPeriod,
} from './businessApi';
import { adjustStock } from './stockApi';
import {
  closeTable,
  deleteTable,
  issueClosingTicket,
} from './tablesApi';
import { createUser, deleteUser, updateUser } from './usersApi';


function mockJsonResponse(payload: unknown = {}) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify(payload), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    })
  );
}


describe('servicios de negocio', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.setItem('bejas_access_token', 'admin-token');
  });

  it('registra usuarios desde auth/register con rol', async () => {
    const fetchMock = mockJsonResponse({
      id: 2,
      user: 'ana',
      role: 'empleado'
    });

    await createUser('ana', 'secreto', 'empleado');

    expect(fetchMock.mock.calls[0][0]).toContain('/auth/register');
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({
      username: 'ana',
      password: 'secreto',
      role: 'empleado'
    });
  });

  it('elimina empleados y mesas usando endpoints persistidos', async () => {
    const fetchMock = mockJsonResponse();

    await deleteUser('12');
    await deleteTable(8);

    expect(fetchMock.mock.calls[0][0]).toContain('/users/12');
    expect(fetchMock.mock.calls[0][1]?.method).toBe('DELETE');
    expect(fetchMock.mock.calls[1][0]).toContain('/tables/8');
    expect(fetchMock.mock.calls[1][1]?.method).toBe('DELETE');
  });

  it('actualiza usuario, contraseña y rol desde gestión de cuentas', async () => {
    const fetchMock = mockJsonResponse({
      id: 12,
      username: 'ana-admin',
      role: 'admin',
    });

    await updateUser('12', {
      username: 'ana-admin',
      password: 'nueva-clave',
      role: 'admin',
    });

    expect(fetchMock.mock.calls[0][0]).toContain('/users/12');
    expect(fetchMock.mock.calls[0][1]?.method).toBe('PATCH');
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({
      username: 'ana-admin',
      password: 'nueva-clave',
      role: 'admin',
    });
  });

  it('envía ajustes de stock auditables', async () => {
    const fetchMock = mockJsonResponse({});

    await adjustStock(4, -2, 'merma', 'Rotura');

    expect(fetchMock.mock.calls[0][0]).toContain(
      '/stock/products/4/adjustments'
    );
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({
      quantity_delta: -2,
      movement_type: 'merma',
      note: 'Rotura'
    });
  });

  it('persiste objetivos y cierres diarios', async () => {
    const fetchMock = mockJsonResponse({});

    await createGoal({
      period: 'mensual',
      target_amount: 100000,
      description: 'Junio'
    });
    await createCashClosing('2026-06-09', 120000, 'Cierre normal');

    expect(fetchMock.mock.calls[0][0]).toContain('/goals');
    expect(fetchMock.mock.calls[1][0]).toContain('/cash-closings');
  });

  it('corrige cierres y consulta su historial auditable', async () => {
    const fetchMock = mockJsonResponse([]);

    await updateCashClosing(4, {
      counted_cash: 0,
      notes: 'Conteo corregido'
    });
    await fetchCashClosingRevisions(4);

    expect(fetchMock.mock.calls[0][0]).toContain('/cash-closings/4');
    expect(fetchMock.mock.calls[0][1]?.method).toBe('PATCH');
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({
      counted_cash: 0,
      notes: 'Conteo corregido'
    });
    expect(fetchMock.mock.calls[1][0]).toContain(
      '/cash-closings/4/revisions'
    );
  });

  it('envía períodos diarios y mensuales al mock de AFIP', async () => {
    const fetchMock = mockJsonResponse({
      status: 'sin_pendientes',
      message: 'Sin pendientes',
      sales_count: 0,
      total: 0,
      invoice: null
    });

    await retryInvoicePeriod({
      period: 'diario',
      date: '2026-06-09'
    });
    await retryInvoicePeriod({
      period: 'mensual',
      year: 2026,
      month: 6
    });

    expect(fetchMock.mock.calls[0][0]).toContain('/invoices/retry-period');
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({
      period: 'diario',
      date: '2026-06-09'
    });
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toEqual({
      period: 'mensual',
      year: 2026,
      month: 6
    });
  });

  it('consulta el resumen pendiente diario y mensual', async () => {
    const fetchMock = mockJsonResponse({
      period: 'diario',
      period_start: '2026-06-09T00:00:00',
      period_end: '2026-06-10T00:00:00',
      sales_count: 8,
      total: 8000,
      cash_closing_exists: true,
      can_declare: true,
      blocking_reason: null
    });

    await fetchPendingInvoiceSummary({
      period: 'diario',
      date: '2026-06-09'
    });
    await fetchPendingInvoiceSummary({
      period: 'mensual',
      year: 2026,
      month: 6
    });

    expect(fetchMock.mock.calls[0][0]).toContain(
      '/invoices/pending-summary?period=diario&date=2026-06-09'
    );
    expect(fetchMock.mock.calls[1][0]).toContain(
      '/invoices/pending-summary?period=mensual&year=2026&month=6'
    );
  });

  it('separa validación, reintento y declaración fiscal', async () => {
    const fetchMock = mockJsonResponse({
      can_declare: true,
      status: 'CLOSURE_READY',
      summary: {},
      issues: [],
      existing_closure_id: null,
      message: 'Listo'
    });
    const period = {
      periodFrom: '2026-06-01',
      periodTo: '2026-06-30',
      periodType: 'MONTH' as const,
    };

    await fetchFiscalPeriodSummary(period.periodFrom, period.periodTo);
    await validateFiscalPeriod(period);
    await declareFiscalPeriod(period);

    expect(fetchMock.mock.calls[0][0]).toContain(
      '/closings/summary?from=2026-06-01&to=2026-06-30'
    );
    expect(fetchMock.mock.calls[1][0]).toContain('/closings/validate');
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toEqual(period);
    expect(fetchMock.mock.calls[2][0]).toContain('/closings/declare');
    expect(JSON.parse(String(fetchMock.mock.calls[2][1]?.body))).toEqual(period);
  });

  it('envía al cierre sólo los pagos normalizados', async () => {
    const fetchMock = mockJsonResponse({
      closing: {
        id: 1,
        table_number: 7,
        table_name: null,
        opening_time: '2026-06-09T12:00:00',
        closing_time: '2026-06-09T13:00:00',
        business_date: '2026-06-09',
        people: 2,
        served_by: 1,
        subtotal: 1000,
        discount: 100,
        total: 900,
        amount_received: 1000,
        change: 100,
        status: 'cerrada',
        cash_closing_id: null,
        items: [],
        payments: [{ id: 1, method: 'efectivo', amount: 1000 }],
        invoice: null
      },
      afip_authorized: null,
      warning: null
    });

    await closeTable(7, [{ method: 'efectivo', amount: 1000 }]);

    expect(fetchMock.mock.calls[0][0]).toContain('/tables/7/close');
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({
      payments: [{ method: 'efectivo', amount: 1000 }]
    });
  });

  it('declara la factura sólo al solicitar la impresión del ticket', async () => {
    const fetchMock = mockJsonResponse({
      id: 4,
      closing_id: 12,
      status: 'pendiente'
    });

    await issueClosingTicket(12);

    expect(fetchMock.mock.calls[0][0]).toContain(
      '/closings/12/ticket'
    );
    expect(fetchMock.mock.calls[0][1]?.method).toBe('POST');
  });
});
