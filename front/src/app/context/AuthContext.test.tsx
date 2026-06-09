import { act, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { UNAUTHORIZED_EVENT } from '../services/apiClient';
import { AuthProvider, useAuth } from './AuthContext';


function AuthProbe() {
  const { isAdmin, isAuthenticated, isAuthReady, user } = useAuth();
  if (!isAuthReady) return <span>loading</span>;
  return (
    <span>
      {isAuthenticated ? `${user?.username}:${isAdmin}` : 'anonymous'}
    </span>
  );
}


describe('AuthProvider', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it('restaura un admin validando el JWT con el backend', async () => {
    localStorage.setItem('bejas_access_token', 'valid-token');
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        sub: 'nico',
        user_id: 1,
        role: 'admin',
        exp: Math.floor(Date.now() / 1000) + 3600
      }), { status: 200 })
    );

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>
    );

    expect(await screen.findByText('nico:true')).toBeInTheDocument();
  });

  it('cierra la sesión cuando el cliente recibe un 401', async () => {
    localStorage.setItem('bejas_access_token', 'valid-token');
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        sub: 'empleado',
        user_id: 2,
        role: 'empleado',
        exp: Math.floor(Date.now() / 1000) + 3600
      }), { status: 200 })
    );

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>
    );
    expect(await screen.findByText('empleado:false')).toBeInTheDocument();

    act(() => window.dispatchEvent(new Event(UNAUTHORIZED_EVENT)));

    await waitFor(() => {
      expect(screen.getByText('anonymous')).toBeInTheDocument();
    });
    expect(localStorage.getItem('bejas_access_token')).toBeNull();
  });
});
