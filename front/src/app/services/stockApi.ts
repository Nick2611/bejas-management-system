import { apiRequest } from './apiClient';

export type ManualMovementType =
  | 'ajuste_manual'
  | 'reposicion'
  | 'merma'
  | 'correccion';

export interface StockMovement {
  id: number;
  product_id: number;
  product_name: string;
  closing_id: number | null;
  created_by_id: number | null;
  movement_type: string;
  quantity_delta: number;
  stock_before: number;
  stock_after: number;
  created_at: string;
  note: string | null;
}

export const fetchStockMovements = (productId?: number) =>
  apiRequest<StockMovement[]>(
    `/stock/movements${productId ? `?product_id=${productId}` : ''}`,
    {},
    { fallback: 'No se pudo cargar el historial de stock' }
  );

export const adjustStock = (
  productId: number,
  quantityDelta: number,
  movementType: ManualMovementType,
  note?: string
) => apiRequest(`/stock/products/${productId}/adjustments`, {
  method: 'POST',
  body: JSON.stringify({
    quantity_delta: quantityDelta,
    movement_type: movementType,
    note: note || null
  })
}, { fallback: 'No se pudo ajustar el stock' });
