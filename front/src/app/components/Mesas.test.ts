import { describe, expect, it } from 'vitest';

import { normalizeOrderQuantity } from './Mesas';


describe('cantidad directa del pedido', () => {
  it('acepta una cantidad ingresada manualmente', () => {
    expect(normalizeOrderQuantity('12', 20)).toBe(12);
  });

  it('limita la cantidad al stock disponible', () => {
    expect(normalizeOrderQuantity('30', 8)).toBe(8);
  });

  it('permite vaciar el campo y elimina la cantidad', () => {
    expect(normalizeOrderQuantity('', 8)).toBe(0);
  });
});
