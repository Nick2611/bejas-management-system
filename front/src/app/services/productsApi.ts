import { apiRequest } from './apiClient';

export type ProductType = 'cerveza' | 'comida' | 'trago' | 'bebida';

export interface Product {
  id: number;
  name: string;
  type: ProductType;
  price: number;
  qty: number;
  unit: string;
  minimum_qty: number;
  capacity_qty: number | null;
  last_restocked_at: string | null;
}

export interface CreateProductRequest {
  name: string;
  type: ProductType;
  price: number;
  qty: number;
  unit: string;
  minimum_qty?: number;
  capacity_qty?: number | null;
}

export type UpdateProductRequest = Partial<
  Omit<Product, 'id' | 'last_restocked_at'>
>;

function isProductType(value: unknown): value is ProductType {
  return value === 'cerveza'
    || value === 'comida'
    || value === 'trago'
    || value === 'bebida';
}

function parseProduct(value: unknown): Product {
  if (typeof value !== 'object' || value === null) {
    throw new Error('El backend devolvió un producto inválido');
  }
  const product = value as Record<string, unknown>;
  if (
    typeof product.id !== 'number'
    || typeof product.name !== 'string'
    || !isProductType(product.type)
    || typeof product.price !== 'number'
    || typeof product.qty !== 'number'
    || typeof product.unit !== 'string'
  ) {
    throw new Error('El formato de productos del backend no coincide con el frontend');
  }
  return {
    id: product.id,
    name: product.name,
    type: product.type,
    price: product.price,
    qty: product.qty,
    unit: product.unit,
    minimum_qty: typeof product.minimum_qty === 'number' ? product.minimum_qty : 0,
    capacity_qty: typeof product.capacity_qty === 'number' ? product.capacity_qty : null,
    last_restocked_at: typeof product.last_restocked_at === 'string'
      ? product.last_restocked_at
      : null
  };
}

export async function fetchProducts(): Promise<Product[]> {
  const payload = await apiRequest<unknown[]>('/products/all', {}, {
    fallback: 'No se pudieron cargar los productos'
  });
  return payload.map(parseProduct);
}

export async function createProduct(
  payload: CreateProductRequest
): Promise<void> {
  await apiRequest('/products/create', {
    method: 'POST',
    body: JSON.stringify(payload)
  }, { fallback: 'No se pudo crear el producto' });
}

export async function updateProduct(
  id: number,
  payload: UpdateProductRequest
): Promise<void> {
  await apiRequest(`/products/update/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload)
  }, { fallback: 'No se pudo actualizar el producto' });
}

export async function deleteProduct(id: number): Promise<void> {
  await apiRequest(`/products/${id}`, {
    method: 'DELETE'
  }, { fallback: 'No se pudo eliminar el producto' });
}
