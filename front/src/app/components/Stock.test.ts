import { describe, expect, it } from 'vitest';

import {
  getStockAdjustmentHint,
  getStockAdjustmentMaximum,
  limitStockAdjustment,
} from './Stock';


describe('límites del ajuste de stock', () => {
  it('limita una reposición al espacio disponible', () => {
    expect(limitStockAdjustment(
      '20',
      'add',
      { qty: 28, capacity_qty: 30 },
    )).toBe('2');
  });

  it('limita una merma al stock actual', () => {
    expect(limitStockAdjustment(
      '20',
      'subtract',
      { qty: 8, capacity_qty: 30 },
    )).toBe('8');
  });

  it('no limita reposiciones sin capacidad configurada', () => {
    expect(limitStockAdjustment(
      '20',
      'add',
      { qty: 8, capacity_qty: null },
    )).toBe('20');
  });

  it('tolera que el producto se limpie mientras se cierra el diálogo', () => {
    expect(getStockAdjustmentMaximum(null, 'add')).toBeUndefined();
    expect(getStockAdjustmentHint(null, 'add')).toBe('');
  });

  it('calcula el máximo y el mensaje sin lecturas inseguras', () => {
    const product = { qty: 28, capacity_qty: 30 };

    expect(getStockAdjustmentMaximum(product, 'add')).toBe(2);
    expect(getStockAdjustmentHint(product, 'add')).toBe(
      'Máximo a agregar: 2'
    );
  });
});
