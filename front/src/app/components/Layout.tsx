import { Outlet, useNavigate, useLocation } from 'react-router';
import { useAuth } from '../context/AuthContext';
import {
  LogOut, TableProperties, Beer, FileText, BarChart,
  UtensilsCrossed, Target, ChevronRight,
} from 'lucide-react';
import logo from '../../assets/bejas_logo.png';

const navItems = [
  { path: '/dashboard', label: 'Dashboard', icon: BarChart },
  { path: '/mesas', label: 'Mesas', icon: TableProperties },
  { path: '/stock', label: 'Stock', icon: Beer },
  { path: '/kpis', label: 'KPIs', icon: Target, adminOnly: true },
  { path: '/cierre', label: 'Cierre', icon: FileText, adminOnly: true },
  { path: '/configuracion', label: 'Configuración', icon: UtensilsCrossed, adminOnly: true },
];

export function Layout() {
  const { user, logout, isAdmin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <div className="min-h-screen bg-[#080808] flex">
      <aside className="w-64 bg-[#0f0f0f] border-r border-white/[0.08] flex flex-col relative overflow-hidden shrink-0">
        <div className="pointer-events-none absolute -top-24 -left-24 h-64 w-64 rounded-full bg-amber-400/[0.06] blur-3xl" />
        <div className="pointer-events-none absolute bottom-0 right-0 h-48 w-48 rounded-full bg-amber-700/[0.05] blur-3xl" />

        {/* Logo */}
        <div className="relative px-6 pt-8 pb-6 border-b border-white/[0.06]">
          <div className="relative mx-auto h-36 w-36">
            <div className="absolute inset-5 rounded-full bg-amber-400/20 blur-2xl" />
            <img
              src={logo}
              alt="Bejas"
              className="relative h-full w-full rounded-full object-contain drop-shadow-[0_12px_22px_rgba(0,0,0,0.5)]"
            />
          </div>
          <p className="mt-4 text-center text-[10px] font-semibold tracking-[0.22em] text-amber-400/80 uppercase">
            Estación de Cervezas
          </p>
        </div>

        {/* User */}
        <div className="px-4 pt-4">
          <div className="flex items-center gap-3 px-3 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06]">
            <div className="h-8 w-8 rounded-full bg-amber-400/15 border border-amber-400/20 flex items-center justify-center text-amber-400 text-sm font-semibold uppercase shrink-0">
              {user?.username?.[0]}
            </div>
            <div className="min-w-0">
              <p className="text-sm font-medium text-zinc-200 truncate">{user?.username}</p>
              <p className="text-[11px] text-zinc-500 capitalize">{user?.role}</p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-4 pt-3 pb-2 space-y-0.5">
          {navItems.map((item) => {
            if (item.adminOnly && !isAdmin) return null;
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <button
                key={item.path}
                type="button"
                onClick={() => navigate(item.path)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 ${
                  isActive
                    ? 'bg-amber-400/[0.12] text-amber-400 border border-amber-400/20'
                    : 'text-zinc-500 hover:text-zinc-200 hover:bg-white/[0.04] border border-transparent'
                }`}
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span className="flex-1 text-left">{item.label}</span>
                {isActive && <ChevronRight className="w-3 h-3 text-amber-400/50 shrink-0" />}
              </button>
            );
          })}
        </nav>

        {/* Logout */}
        <div className="px-4 pb-6 pt-2 border-t border-white/[0.06]">
          <button
            type="button"
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-zinc-500 hover:text-red-400 hover:bg-red-950/20 border border-transparent hover:border-red-900/25 transition-all duration-150"
          >
            <LogOut className="w-4 h-4 shrink-0" />
            Cerrar Sesión
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
