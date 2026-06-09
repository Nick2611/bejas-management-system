import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  apiRequest,
  getApiErrorMessage,
  UNAUTHORIZED_EVENT
} from './apiClient';


describe('apiRequest', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it('envía JSON y el JWT almacenado', async () => {
    localStorage.setItem('bejas_access_token', 'token-123');
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      })
    );

    await apiRequest('/products/all');

    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock.mock.calls[0][1]?.headers).toMatchObject({
      Accept: 'application/json',
      Authorization: 'Bearer token-123'
    });
  });

  it('notifica una sesión vencida ante un 401 privado', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Token inválido' }), {
        status: 401
      })
    );
    const listener = vi.fn();
    window.addEventListener(UNAUTHORIZED_EVENT, listener);

    await expect(apiRequest('/tables')).rejects.toThrow('Token inválido');

    expect(listener).toHaveBeenCalledOnce();
    window.removeEventListener(UNAUTHORIZED_EVENT, listener);
  });
});


describe('getApiErrorMessage', () => {
  it('combina los mensajes de validación de FastAPI', () => {
    expect(getApiErrorMessage(
      { detail: [{ msg: 'Campo requerido' }, { msg: 'Valor inválido' }] },
      422,
      'Error'
    )).toBe('Campo requerido. Valor inválido');
  });
});
