import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { Dashboard } from './Dashboard';
import { fetchTables } from '../services/tablesApi';
import { fetchProducts } from '../services/productsApi';


const useAuthMock = vi.fn();
const navigateMock = vi.fn();

vi.mock('react-router', () => ({
  useNavigate: () => navigateMock
}));

vi.mock('../context/AuthContext', () => ({
  useAuth: () => useAuthMock()
}));

vi.mock('../services/tablesApi', () => ({
  fetchTables: vi.fn().mockResolvedValue([])
}));

vi.mock('../services/productsApi', () => ({
  fetchProducts: vi.fn().mockResolvedValue([])
}));

vi.mock('../services/businessApi', () => ({
  fetchKpiSummary: vi.fn().mockResolvedValue({
    daily: { total_sales: 0, sales_count: 0 },
    weekly: { total_sales: 0, sales_count: 0 },
    monthly: { total_sales: 0, sales_count: 0 }
  })
}));


describe('Dashboard permissions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(fetchTables).mockResolvedValue([]);
    vi.mocked(fetchProducts).mockResolvedValue([]);
  });

  it('oculta ventas del día a empleados', () => {
    useAuthMock.mockReturnValue({
      user: { username: 'empleado' },
      isAdmin: false
    });

    render(<Dashboard />);

    expect(screen.queryByText('Ventas Hoy')).not.toBeInTheDocument();
  });

  it('muestra ventas del día a administradores', () => {
    useAuthMock.mockReturnValue({
      user: { username: 'admin' },
      isAdmin: true
    });

    render(<Dashboard />);

    expect(screen.getByText('Ventas Hoy')).toBeInTheDocument();
  });

  it('navega desde accesos rápidos y oculta cierres a empleados', () => {
    useAuthMock.mockReturnValue({
      user: { username: 'empleado' },
      isAdmin: false
    });

    render(<Dashboard />);

    fireEvent.click(screen.getByRole('button', { name: /Gestión de mesas/i }));
    expect(navigateMock).toHaveBeenCalledWith('/mesas');
    fireEvent.click(screen.getByRole('button', { name: /Control de stock/i }));
    expect(navigateMock).toHaveBeenCalledWith('/stock');
    expect(
      screen.queryByRole('button', { name: /Cierres y facturación/i })
    ).not.toBeInTheDocument();
  });

  it('permite al administrador navegar a cierres', () => {
    useAuthMock.mockReturnValue({
      user: { username: 'admin' },
      isAdmin: true
    });

    render(<Dashboard />);

    fireEvent.click(
      screen.getByRole('button', { name: /Cierres y facturación/i })
    );
    expect(navigateMock).toHaveBeenCalledWith('/cierre');
  });

  it('cuenta stock bajo de todos los tipos de producto', async () => {
    useAuthMock.mockReturnValue({
      user: { username: 'empleado' },
      isAdmin: false
    });
    vi.mocked(fetchProducts).mockResolvedValue([
      {
        id: 7,
        name: 'Empanadas',
        type: 'comida',
        price: 1800,
        qty: 19,
        unit: 'unidad',
        minimum_qty: 20,
        capacity_qty: 150,
        last_restocked_at: null
      }
    ]);

    render(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText('Productos bajo mínimo')).toBeInTheDocument();
      expect(screen.getByText('1')).toBeInTheDocument();
    });
  });

  it('mantiene la alerta de stock aunque falle la carga de mesas', async () => {
    useAuthMock.mockReturnValue({
      user: { username: 'empleado' },
      isAdmin: false
    });
    vi.mocked(fetchTables).mockRejectedValue(new Error('Mesas no disponibles'));
    vi.mocked(fetchProducts).mockResolvedValue([
      {
        id: 1,
        name: 'IPA',
        type: 'cerveza',
        price: 4800,
        qty: 5,
        unit: 'pinta',
        minimum_qty: 15,
        capacity_qty: 100,
        last_restocked_at: null
      }
    ]);

    render(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText('Productos bajo mínimo')).toBeInTheDocument();
      expect(screen.getByText('1')).toBeInTheDocument();
    });
  });
});
