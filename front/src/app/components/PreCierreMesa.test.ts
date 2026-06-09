import { describe, expect, it } from 'vitest';

import {
  calculateCashDiscount,
  isEditablePaymentAmount,
  splitPaymentTotal,
} from './PreCierreMesa';


describe('cálculos de cierre de mesa', () => {
  it('redondea el descuento como el backend para montos impares', () => {
    expect(calculateCashDiscount(1005)).toBe(101);
    expect(1005 - calculateCashDiscount(1005)).toBe(904);
  });

  it('divide pagos enteros sin perder el peso sobrante', () => {
    const payments = splitPaymentTotal(901);

    expect(payments).toEqual([450, 451]);
    expect(payments[0] + payments[1]).toBe(901);
  });

  it('permite borrar por completo un monto antes de reemplazarlo', () => {
    expect(isEditablePaymentAmount('')).toBe(true);
    expect(isEditablePaymentAmount('12500')).toBe(true);
    expect(isEditablePaymentAmount('12.5')).toBe(false);
  });
});
