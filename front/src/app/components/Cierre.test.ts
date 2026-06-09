import { describe, expect, it } from 'vitest';

import { isValidCountedCash } from './Cierre';


describe('validación del efectivo contado', () => {
  it('rechaza el campo vacío', () => {
    expect(isValidCountedCash('')).toBe(false);
    expect(isValidCountedCash('   ')).toBe(false);
  });

  it('acepta cero como conteo explícito', () => {
    expect(isValidCountedCash('0')).toBe(true);
  });

  it('rechaza negativos, decimales y texto', () => {
    expect(isValidCountedCash('-1')).toBe(false);
    expect(isValidCountedCash('1.5')).toBe(false);
    expect(isValidCountedCash('abc')).toBe(false);
  });
});
