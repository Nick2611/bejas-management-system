import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import {
  ArrowRight,
  TableProperties,
  Beer,
  TrendingUp,
  FileText,
  Activity,
  AlertTriangle,
  Clock,
  Calendar,
  Zap,
  BarChart2,
} from 'lucide-react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useAuth } from '../context/AuthContext';
import { fetchTables } from '../services/tablesApi';
import { fetchProducts, type Product } from '../services/productsApi';
import {
  fetchKpiSummary,
  fetchSalesHistory,
  type DailyKpiPoint,
  type DailySalesHistory,
} from '../services/businessApi';

interface DashboardStats {
  mesasActivas: number;
  barrilesOptimos: number;
  productosLowStock: number;
  ventasHoy: number;
}

export function calculateInventoryStats(products: Product[]) {
  const beers = products.filter(p => p.type === 'cerveza');
  return {
    barrilesOptimos: beers.filter(p => {
      if (p.capacity_qty === null) return p.qty > p.minimum_qty;
      return p.qty >= p.capacity_qty * 0.7;
    }).length,
    productosLowStock: products.filter(p => p.qty <= p.minimum_qty).length,
  };
}

function fmtPeso(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${Math.round(n / 1_000)}k`;
  return `$${n.toLocaleString('es-AR')}`;
}

function fmtDate(iso: string): string {
  const [, m, d] = iso.split('-');
  return `${parseInt(d)}/${parseInt(m)}`;
}

function isWeekend(iso: string): boolean {
  const day = new Date(iso + 'T12:00:00').getDay();
  return day === 5 || day === 6; // Fri or Sat (local)
}

interface TooltipProps {
  active?: boolean;
  payload?: Array<{ payload: DailyKpiPoint }>;
}

function SalesTooltip({ active, payload }: TooltipProps) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const [year, mon, day] = d.date.split('-');
  const label = new Date(`${year}-${mon}-${day}T12:00:00`).toLocaleDateString('es-AR', {
    weekday: 'long', day: 'numeric', month: 'long',
  });
  return (
    <div className="bg-[#111111] border border-amber-500/25 rounded-xl p-3 shadow-2xl text-xs min-w-[160px]">
      <p className="text-amber-400 font-semibold mb-2 capitalize">{label}</p>
      <p className="text-white font-bold text-sm mb-1">{d.total_sales.toLocaleString('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 0 })}</p>
      <p className="text-zinc-400">{d.sales_count} {d.sales_count === 1 ? 'cierre' : 'cierres'}</p>
      <p className="text-zinc-400">{d.total_people} personas</p>
    </div>
  );
}

export function Dashboard() {
  const { user, isAdmin } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashboardStats>({
    mesasActivas: 0,
    barrilesOptimos: 0,
    productosLowStock: 0,
    ventasHoy: 0,
  });
  const [now, setNow] = useState(new Date());
  const [history, setHistory] = useState<DailySalesHistory | null>(null);
  const [historyDays, setHistoryDays] = useState<30 | 60>(60);
  const [historyLoading, setHistoryLoading] = useState(false);

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const load = async () => {
      let mesasActivas = 0, barrilesOptimos = 0, productosLowStock = 0, ventasHoy = 0;

      const [tablesResult, productsResult] = await Promise.allSettled([
        fetchTables(),
        fetchProducts(),
      ]);

      if (tablesResult.status === 'fulfilled') {
        mesasActivas = tablesResult.value.filter(
          m => m.people > 0 || m.items.length > 0
        ).length;
      }
      if (productsResult.status === 'fulfilled') {
        const inv = calculateInventoryStats(productsResult.value);
        barrilesOptimos = inv.barrilesOptimos;
        productosLowStock = inv.productosLowStock;
      }
      if (isAdmin) {
        try { ventasHoy = (await fetchKpiSummary()).daily.total_sales; } catch { /* noop */ }
      }

      setStats({ mesasActivas, barrilesOptimos, productosLowStock, ventasHoy });
    };
    void load();
  }, [isAdmin]);

  useEffect(() => {
    if (!isAdmin) return;
    setHistoryLoading(true);
    fetchSalesHistory(historyDays)
      .then(setHistory)
      .catch(() => setHistory(null))
      .finally(() => setHistoryLoading(false));
  }, [isAdmin, historyDays]);

  const statCards = [
    {
      label: 'Mesas Activas',
      value: String(stats.mesasActivas),
      sub: 'En servicio ahora',
      icon: TableProperties,
      color: 'text-amber-400',
      iconBg: 'bg-amber-400/10',
      border: 'border-amber-500/20',
    },
    {
      label: 'Barriles Óptimos',
      value: String(stats.barrilesOptimos),
      sub: 'Stock en buen nivel',
      icon: Beer,
      color: 'text-emerald-400',
      iconBg: 'bg-emerald-400/10',
      border: 'border-emerald-500/20',
    },
    {
      label: 'Stock Bajo',
      value: String(stats.productosLowStock),
      sub: 'Productos bajo mínimo',
      icon: AlertTriangle,
      color: stats.productosLowStock > 0 ? 'text-red-400' : 'text-zinc-500',
      iconBg: stats.productosLowStock > 0 ? 'bg-red-400/10' : 'bg-zinc-800/40',
      border: stats.productosLowStock > 0 ? 'border-red-500/20' : 'border-white/[0.08]',
    },
    ...(isAdmin
      ? [{
          label: 'Ventas Hoy',
          value: `$${stats.ventasHoy.toLocaleString('es-AR')}`,
          sub: 'Facturación del día',
          icon: TrendingUp,
          color: 'text-amber-400',
          iconBg: 'bg-amber-400/10',
          border: 'border-amber-500/20',
        }]
      : []),
  ];

  const quickLinks = [
    { label: 'Gestión de Mesas', path: '/mesas', icon: TableProperties, desc: 'Mesas, pedidos y cierres' },
    { label: 'Control de Stock', path: '/stock', icon: Beer, desc: 'Inventario y productos' },
    ...(isAdmin ? [{ label: 'Cierres y Facturación', path: '/cierre', icon: FileText, desc: 'Balances y tickets AFIP' }] : []),
  ];

  // Chart data — inject weekend flag for potential dot coloring
  const chartData = (history?.days ?? []).map(d => ({
    ...d,
    weekend: isWeekend(d.date) ? d.total_sales : null,
    label: fmtDate(d.date),
  }));

  const yTickFormatter = (v: number) => fmtPeso(v);
  const xInterval = chartData.length > 30
    ? Math.ceil(chartData.length / 8) - 1
    : Math.ceil(chartData.length / 6) - 1;

  return (
    <div className="relative min-h-screen bg-[#080808] text-white">
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute top-0 left-1/3 h-[500px] w-[500px] rounded-full bg-amber-400/[0.04] blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 h-64 w-64 rounded-full bg-amber-700/[0.04] blur-3xl" />
      </div>

      <div className="relative p-8 max-w-7xl mx-auto space-y-8">

        {/* Header */}
        <div>
          <p className="mb-2 text-[10px] font-semibold tracking-[0.26em] text-amber-400/80 uppercase">
            Panel de control
          </p>
          <h1 className="text-3xl font-semibold tracking-tight text-white">
            Bienvenido,{' '}
            <span className="bg-gradient-to-r from-amber-200 via-amber-400 to-amber-600 bg-clip-text text-transparent">
              {user?.username}
            </span>
          </h1>
          <p className="mt-1.5 text-sm text-zinc-600">Estación de Cervezas Bejas</p>
        </div>

        {/* Stats */}
        <div className={`grid grid-cols-1 sm:grid-cols-2 gap-4 ${isAdmin ? 'lg:grid-cols-4' : 'lg:grid-cols-3'}`}>
          {statCards.map(card => {
            const Icon = card.icon;
            return (
              <div
                key={card.label}
                className={`rounded-2xl border ${card.border} bg-[#111111] p-5 transition-all duration-200 hover:scale-[1.015] hover:shadow-xl`}
              >
                <div className="flex items-start justify-between mb-4">
                  <div className={`rounded-xl ${card.iconBg} p-2.5`}>
                    <Icon className={`h-5 w-5 ${card.color}`} />
                  </div>
                </div>
                <div className={`text-3xl font-bold ${card.color} mb-1`}>{card.value}</div>
                <p className="text-sm font-medium text-zinc-300">{card.label}</p>
                <p className="text-xs text-zinc-600 mt-0.5">{card.sub}</p>
              </div>
            );
          })}
        </div>

        {/* Sales history chart — admin only */}
        {isAdmin && (
          <div className="rounded-2xl border border-white/[0.08] bg-[#111111] p-6">
            {/* Chart header */}
            <div className="flex items-center justify-between mb-6 flex-wrap gap-4">
              <div className="flex items-center gap-2">
                <BarChart2 className="h-4 w-4 text-amber-400" />
                <h2 className="text-[11px] font-semibold tracking-[0.18em] text-amber-400 uppercase">
                  Evolución de Ventas
                </h2>
              </div>
              <div className="flex rounded-lg overflow-hidden border border-white/[0.08]">
                {([30, 60] as const).map(d => (
                  <button
                    key={d}
                    type="button"
                    onClick={() => setHistoryDays(d)}
                    className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                      historyDays === d
                        ? 'bg-amber-400/15 text-amber-400'
                        : 'text-zinc-500 hover:text-zinc-300'
                    }`}
                  >
                    {d} días
                  </button>
                ))}
              </div>
            </div>

            {/* Summary row */}
            {history && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
                {[
                  { label: 'Total período', value: fmtPeso(history.total_sales) },
                  { label: 'Día récord', value: fmtPeso(history.max_day) },
                  { label: 'Promedio diario', value: fmtPeso(history.avg_per_day) },
                  { label: 'Días con ventas', value: `${history.active_days} días` },
                ].map(item => (
                  <div key={item.label} className="rounded-xl bg-white/[0.03] border border-white/[0.06] px-4 py-3">
                    <p className="text-xs text-zinc-500 mb-1">{item.label}</p>
                    <p className="text-base font-bold text-amber-400">{item.value}</p>
                  </div>
                ))}
              </div>
            )}

            {/* Chart */}
            {historyLoading && (
              <div className="h-64 flex items-center justify-center">
                <p className="text-zinc-600 text-sm">Cargando datos...</p>
              </div>
            )}

            {!historyLoading && chartData.length === 0 && (
              <div className="h-64 flex flex-col items-center justify-center gap-2">
                <BarChart2 className="h-8 w-8 text-zinc-700" />
                <p className="text-zinc-600 text-sm">Sin datos de ventas en este período</p>
              </div>
            )}

            {!historyLoading && chartData.length > 0 && (
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="salesGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#D4AF37" stopOpacity={0.25} />
                      <stop offset="95%" stopColor="#D4AF37" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="weekendGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.35} />
                      <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#ffffff08" vertical={false} />
                  <XAxis
                    dataKey="label"
                    interval={xInterval}
                    tick={{ fill: '#71717a', fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tickFormatter={yTickFormatter}
                    tick={{ fill: '#71717a', fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    width={52}
                  />
                  <Tooltip content={<SalesTooltip />} cursor={{ stroke: '#D4AF37', strokeWidth: 1, strokeOpacity: 0.3 }} />
                  <Area
                    type="monotone"
                    dataKey="total_sales"
                    stroke="#D4AF37"
                    strokeWidth={2}
                    fill="url(#salesGradient)"
                    dot={false}
                    activeDot={{ r: 4, fill: '#D4AF37', stroke: '#0a0a0a', strokeWidth: 2 }}
                  />
                  {/* Weekend overlay */}
                  <Area
                    type="monotone"
                    dataKey="weekend"
                    stroke="#f59e0b"
                    strokeWidth={0}
                    fill="url(#weekendGradient)"
                    dot={false}
                    activeDot={false}
                    legendType="none"
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}

            {/* Legend */}
            {!historyLoading && chartData.length > 0 && (
              <div className="flex items-center gap-4 mt-3 justify-end">
                <span className="flex items-center gap-1.5 text-[11px] text-zinc-500">
                  <span className="h-2 w-2 rounded-full bg-amber-400 inline-block" />
                  Ventas diarias
                </span>
                <span className="flex items-center gap-1.5 text-[11px] text-zinc-500">
                  <span className="h-2 w-2 rounded-full bg-amber-500/60 inline-block" />
                  Viernes y sábados
                </span>
              </div>
            )}
          </div>
        )}

        {/* Bottom grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* System status */}
          <div className="rounded-2xl border border-white/[0.08] bg-[#111111] p-6">
            <div className="flex items-center gap-2 mb-6">
              <Activity className="h-4 w-4 text-amber-400" />
              <h2 className="text-[11px] font-semibold tracking-[0.18em] text-amber-400 uppercase">
                Estado del Sistema
              </h2>
            </div>
            <div className="space-y-0">
              <div className="flex items-center justify-between py-3.5 border-b border-white/[0.05]">
                <span className="text-sm text-zinc-500">Servicio</span>
                <span className="flex items-center gap-2 text-sm font-medium text-emerald-400">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Operativo
                </span>
              </div>
              <div className="flex items-center justify-between py-3.5 border-b border-white/[0.05]">
                <span className="flex items-center gap-2 text-sm text-zinc-500">
                  <Clock className="h-3.5 w-3.5" /> Hora actual
                </span>
                <span className="font-mono text-sm font-medium text-amber-400">
                  {now.toLocaleTimeString('es-AR')}
                </span>
              </div>
              <div className="flex items-center justify-between py-3.5">
                <span className="flex items-center gap-2 text-sm text-zinc-500">
                  <Calendar className="h-3.5 w-3.5" /> Fecha
                </span>
                <span className="text-sm font-medium text-zinc-300">
                  {now.toLocaleDateString('es-AR', { weekday: 'long', day: 'numeric', month: 'long' })}
                </span>
              </div>
            </div>
          </div>

          {/* Quick access */}
          <div className="rounded-2xl border border-white/[0.08] bg-[#111111] p-6">
            <div className="flex items-center gap-2 mb-6">
              <Zap className="h-4 w-4 text-amber-400" />
              <h2 className="text-[11px] font-semibold tracking-[0.18em] text-amber-400 uppercase">
                Acceso Rápido
              </h2>
            </div>
            <div className="space-y-2">
              {quickLinks.map(link => {
                const Icon = link.icon;
                return (
                  <button
                    key={link.path}
                    type="button"
                    onClick={() => navigate(link.path)}
                    className="group w-full flex items-center gap-3 px-4 py-3 rounded-xl bg-white/[0.03] border border-white/[0.07] text-left hover:bg-white/[0.06] hover:border-amber-500/20 transition-all duration-150"
                  >
                    <div className="rounded-lg bg-amber-400/10 p-2 shrink-0">
                      <Icon className="h-4 w-4 text-amber-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-zinc-300 group-hover:text-white transition-colors">
                        {link.label}
                      </p>
                      <p className="text-xs text-zinc-600">{link.desc}</p>
                    </div>
                    <ArrowRight className="h-4 w-4 text-zinc-700 group-hover:text-amber-400 group-hover:translate-x-0.5 transition-all duration-150 shrink-0" />
                  </button>
                );
              })}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
