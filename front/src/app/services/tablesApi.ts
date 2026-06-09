import { apiRequest } from './apiClient';
import type { Closing } from './businessApi';

export interface TableItem {
  id: number;
  product_id: number;
  quantity: number;
  curr_price: number;
}

export interface Table {
  id: number;
  table_number: number;
  table_name: string | null;
  opening_time: string;
  people: number;
  items: TableItem[];
}

export interface CreateTableRequest {
  table_number: number;
  table_name?: string | null;
  people?: number;
}

export interface UpdateTableRequest {
  table_name?: string | null;
}

export interface AddTableProductRequest {
  product_id: number;
  quantity: number;
}

export type PaymentMethod =
  | 'efectivo'
  | 'tarjeta_credito'
  | 'tarjeta_debito'
  | 'mercado_pago';

export interface CloseTablePayment {
  method: PaymentMethod;
  amount: number;
}

export interface CloseTableResponse {
  closing: Closing;
  afip_authorized: boolean | null;
  warning: string | null;
}

function parseTable(value: unknown): Table {
  if (typeof value !== 'object' || value === null) {
    throw new Error('El backend devolvió una mesa inválida');
  }
  const table = value as Record<string, unknown>;
  if (
    typeof table.id !== 'number'
    || typeof table.table_number !== 'number'
    || !(typeof table.table_name === 'string' || table.table_name === null)
    || typeof table.opening_time !== 'string'
    || typeof table.people !== 'number'
    || !Array.isArray(table.items)
  ) {
    throw new Error('El formato de mesas del backend no coincide con el frontend');
  }
  return table as unknown as Table;
}

export async function fetchTables(): Promise<Table[]> {
  const payload = await apiRequest<unknown[]>('/tables', {}, {
    fallback: 'No se pudieron cargar las mesas'
  });
  return payload.map(parseTable);
}

export async function fetchTable(tableNumber: number): Promise<Table> {
  return parseTable(await apiRequest(`/tables/${tableNumber}`, {}, {
    fallback: 'No se pudo cargar la mesa'
  }));
}

export async function createTable(payload: CreateTableRequest): Promise<Table> {
  return parseTable(await apiRequest('/tables', {
    method: 'POST',
    body: JSON.stringify(payload)
  }, { fallback: 'No se pudo crear la mesa' }));
}

export async function updateTable(
  tableNumber: number,
  payload: UpdateTableRequest
): Promise<Table> {
  return parseTable(await apiRequest(`/tables/${tableNumber}`, {
    method: 'PATCH',
    body: JSON.stringify(payload)
  }, { fallback: 'No se pudo actualizar la mesa' }));
}

export async function deleteTable(tableNumber: number): Promise<void> {
  await apiRequest(`/tables/${tableNumber}`, {
    method: 'DELETE',
  }, { fallback: 'No se pudo eliminar la mesa' });
}

export async function occupyTable(
  tableNumber: number,
  people: number
): Promise<Table> {
  return parseTable(await apiRequest(`/tables/${tableNumber}/occupancy`, {
    method: 'PATCH',
    body: JSON.stringify({ people })
  }, { fallback: 'No se pudo ocupar la mesa' }));
}

export async function addTableProducts(
  tableNumber: number,
  payload: AddTableProductRequest[]
): Promise<void> {
  await apiRequest(`/tables/${tableNumber}/items`, {
    method: 'POST',
    body: JSON.stringify(payload)
  }, { fallback: 'No se pudo agregar el pedido' });
}

export async function removeTableProduct(
  tableNumber: number,
  itemId: number,
  quantityToRemove: number
): Promise<void> {
  await apiRequest(`/tables/${tableNumber}/items/${itemId}`, {
    method: 'PATCH',
    body: JSON.stringify({ quantity_to_remove: quantityToRemove })
  }, { fallback: 'No se pudo quitar el producto' });
}

export async function removeTablePeople(
  tableNumber: number,
  quantityToRemove: number
): Promise<void> {
  await apiRequest(`/tables/${tableNumber}/people`, {
    method: 'PATCH',
    body: JSON.stringify({ quantity_to_remove: quantityToRemove })
  }, { fallback: 'No se pudieron quitar personas de la mesa' });
}

export async function closeTable(
  tableNumber: number,
  payments: CloseTablePayment[]
): Promise<CloseTableResponse> {
  return apiRequest(`/tables/${tableNumber}/close`, {
    method: 'POST',
    body: JSON.stringify({ payments })
  }, { fallback: 'No se pudo cerrar la mesa' });
}
