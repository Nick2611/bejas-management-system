import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createCashClosing,
  createGoal,
  fetchCashClosingRevisions,
  retryInvoicePeriod,
  updateCashClosing,
} from './businessApi';
import { adjustStock } from './stockApi';
import { closeTable, deleteTable } from './tablesApi';
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
      processed_count: 0,
      authorized_count: 0,
      failed_count: 0,
      invoices: []
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

  it('envía al cierre sólo los pagos normalizados', async () => {
    const fetchMock = mockJsonResponse({
      closing: {
        id: 1,
        table_number: 7,
        table_name: null,
        opening_time: '2026-06-09T12:00:00',
        closing_time: '2026-06-09T13:00:00',
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
});
