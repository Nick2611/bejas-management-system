import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import {
  ArrowRight,
  TableProperties,
  Beer,
  TrendingUp,
  FileText,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { fetchTables } from '../services/tablesApi';
import { fetchProducts, type Product } from '../services/productsApi';
import { fetchKpiSummary } from '../services/businessApi';

interface DashboardStats {
  mesasActivas: number;
  barrilesOptimos: number;
  productosLowStock: number;
  ventasHoy: number;
}

export function calculateInventoryStats(products: Product[]) {
  const beers = products.filter(product => product.type === 'cerveza');

  return {
    barrilesOptimos: beers.filter(product => {
      if (product.capacity_qty === null) {
        return product.qty > product.minimum_qty;
      }
      return product.qty >= product.capacity_qty * 0.7;
    }).length,
    productosLowStock: products.filter(
      product => product.qty <= product.minimum_qty
    ).length
  };
}

export function Dashboard() {
  const { user, isAdmin } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashboardStats>({
    mesasActivas: 0,
    barrilesOptimos: 0,
    productosLowStock: 0,
    ventasHoy: 0
  });

  useEffect(() => {
    const cargarEstadisticas = async () => {
      let mesasActivas = 0;
      let barrilesOptimos = 0;
      let productosLowStock = 0;
      let ventasHoy = 0;

      const [tablesResult, productsResult] = await Promise.allSettled([
        fetchTables(),
        fetchProducts()
      ]);

      if (tablesResult.status === 'fulfilled') {
        mesasActivas = tablesResult.value.filter(
          mesa => mesa.people > 0 || mesa.items.length > 0
        ).length;
      }

      if (productsResult.status === 'fulfilled') {
        const inventory = calculateInventoryStats(productsResult.value);
        barrilesOptimos = inventory.barrilesOptimos;
        productosLowStock = inventory.productosLowStock;
      }

      if (isAdmin) {
        try {
          const kpis = await fetchKpiSummary();
          ventasHoy = kpis.daily.total_sales;
        } catch {
          ventasHoy = 0;
        }
      }

      setStats({
        mesasActivas,
        barrilesOptimos,
        productosLowStock,
        ventasHoy
      });
    };

    void cargarEstadisticas();
  }, [isAdmin]);

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-[#D4AF37] mb-2">Bienvenido, {user?.username}</h1>
        <p className="text-[#a0a0a0]">Panel de control - Estación de Cervezas Bejas</p>
      </div>

      <div className={`grid grid-cols-1 md:grid-cols-2 gap-6 ${
        isAdmin ? 'lg:grid-cols-4' : 'lg:grid-cols-3'
      }`}>
        <Card className="bg-[#1a1a1a] border-[#3a3a3a]">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm text-[#f5f5dc]">Mesas Activas</CardTitle>
            <TableProperties className="h-4 w-4 text-[#D4AF37]" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl text-[#D4AF37]">{stats.mesasActivas}</div>
            <p className="text-xs text-[#a0a0a0] mt-1">En servicio</p>
          </CardContent>
        </Card>

        <Card className="bg-[#1a1a1a] border-[#3a3a3a]">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm text-[#f5f5dc]">Barriles Óptimos</CardTitle>
            <Beer className="h-4 w-4 text-[#22c55e]" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl text-[#22c55e]">{stats.barrilesOptimos}</div>
            <p className="text-xs text-[#a0a0a0] mt-1">Stock verde</p>
          </CardContent>
        </Card>

        <Card className="bg-[#1a1a1a] border-[#3a3a3a]">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm text-[#f5f5dc]">Stock Bajo</CardTitle>
            <Beer className="h-4 w-4 text-[#ef4444]" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl text-[#ef4444]">{stats.productosLowStock}</div>
            <p className="text-xs text-[#a0a0a0] mt-1">Productos bajo mínimo</p>
          </CardContent>
        </Card>

        {isAdmin && (
          <Card className="bg-[#1a1a1a] border-[#3a3a3a]">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm text-[#f5f5dc]">Ventas Hoy</CardTitle>
              <TrendingUp className="h-4 w-4 text-[#D4AF37]" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl text-[#D4AF37]">
                ${stats.ventasHoy.toLocaleString('es-AR')}
              </div>
              <p className="text-xs text-[#a0a0a0] mt-1">Facturación diaria</p>
            </CardContent>
          </Card>
        )}
      </div>

      <div className="mt-8 grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="bg-[#1a1a1a] border-[#3a3a3a]">
          <CardHeader>
            <CardTitle className="text-[#D4AF37]">Resumen del Sistema</CardTitle>
            <CardDescription className="text-[#a0a0a0]">
              Estado general de Bejas
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-[#f5f5dc]">Estado del servicio</span>
              <span className="text-[#22c55e]">Operativo</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[#f5f5dc]">Hora actual</span>
              <span className="text-[#D4AF37]">{new Date().toLocaleTimeString('es-AR')}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[#f5f5dc]">Fecha</span>
              <span className="text-[#D4AF37]">{new Date().toLocaleDateString('es-AR')}</span>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-[#1a1a1a] border-[#3a3a3a]">
          <CardHeader>
            <CardTitle className="text-[#D4AF37]">Accesos Rápidos</CardTitle>
            <CardDescription className="text-[#a0a0a0]">
              Funciones principales del sistema
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <button
              type="button"
              onClick={() => navigate('/mesas')}
              className="w-full p-3 bg-[#2a2a2a] rounded-lg border border-[#3a3a3a] text-left text-[#f5f5dc] flex items-center justify-between hover:border-[#D4AF37] hover:text-[#D4AF37] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D4AF37]"
            >
              <span className="flex items-center gap-2">
                <TableProperties className="w-4 h-4" /> Gestión de mesas
              </span>
              <ArrowRight className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => navigate('/stock')}
              className="w-full p-3 bg-[#2a2a2a] rounded-lg border border-[#3a3a3a] text-left text-[#f5f5dc] flex items-center justify-between hover:border-[#D4AF37] hover:text-[#D4AF37] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D4AF37]"
            >
              <span className="flex items-center gap-2">
                <Beer className="w-4 h-4" /> Control de stock
              </span>
              <ArrowRight className="w-4 h-4" />
            </button>
            {isAdmin && (
              <button
                type="button"
                onClick={() => navigate('/cierre')}
                className="w-full p-3 bg-[#2a2a2a] rounded-lg border border-[#3a3a3a] text-left text-[#f5f5dc] flex items-center justify-between hover:border-[#D4AF37] hover:text-[#D4AF37] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D4AF37]"
              >
                <span className="flex items-center gap-2">
                  <FileText className="w-4 h-4" /> Cierres y facturación
                </span>
                <ArrowRight className="w-4 h-4" />
              </button>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
