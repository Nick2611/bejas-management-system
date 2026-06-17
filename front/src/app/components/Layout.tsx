import { Outlet, useNavigate, useLocation } from 'react-router';
import { useAuth } from '../context/AuthContext';
import { Button } from './ui/button';
import { LogOut, TableProperties, Beer, FileText, BarChart, UtensilsCrossed, Target } from 'lucide-react';
import logo from '../../assets/bejas_logo.png';

export function Layout() {
  const { user, logout, isAdmin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  const navItems = [
    { path: '/dashboard', label: 'Dashboard', icon: BarChart },
    { path: '/mesas', label: 'Mesas', icon: TableProperties },
    { path: '/stock', label: 'Stock', icon: Beer },
    { path: '/kpis', label: 'KPIs', icon: Target, adminOnly: true },
    { path: '/cierre', label: 'Cierre', icon: FileText, adminOnly: true },
    { path: '/configuracion', label: 'Configuración', icon: UtensilsCrossed, adminOnly: true }
  ];

  return (
    <div className="min-h-screen bg-[#0a0a0a] flex">
      {/* Sidebar */}
      <div className="w-64 bg-[#1a1a1a] border-r border-[#3a3a3a] flex flex-col">
        <div className="p-6 border-b border-[#3a3a3a]">
          <div className="relative mx-auto h-36 w-36">
            <div className="absolute inset-5 rounded-full bg-amber-400/15 blur-2xl" />
            <img
              src={logo}
              alt="Estación de Cervezas Bejas"
              className="relative h-full w-full rounded-full object-contain drop-shadow-[0_12px_22px_rgba(0,0,0,0.45)]"
            />
          </div>
          <div className="mt-4 text-center">
            <p className="text-[#D4AF37]">{user?.username}</p>
            <p className="text-xs text-[#a0a0a0] capitalize">{user?.role}</p>
          </div>
        </div>

        <nav className="flex-1 p-4 space-y-2">
          {navItems.map((item) => {
            if (item.adminOnly && !isAdmin) return null;
            
            const Icon = item.icon;
            const isActive = location.pathname === item.path;

            return (
              <Button
                key={item.path}
                onClick={() => navigate(item.path)}
                variant={isActive ? 'default' : 'ghost'}
                className={`w-full justify-start ${
                  isActive 
                    ? 'bg-[#D4AF37] text-[#0a0a0a] hover:bg-[#B8860B]' 
                    : 'text-[#f5f5dc] hover:bg-[#2a2a2a] hover:text-[#D4AF37]'
                }`}
              >
                <Icon className="w-5 h-5 mr-3" />
                {item.label}
              </Button>
            );
          })}
        </nav>

        <div className="p-4 border-t border-[#3a3a3a]">
          <Button
            onClick={handleLogout}
            variant="outline"
            className="w-full justify-start border-[#3a3a3a] text-[#f5f5dc] hover:bg-[#2a2a2a] hover:text-[#ef4444]"
          >
            <LogOut className="w-5 h-5 mr-3" />
            Cerrar Sesión
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-auto">
        <Outlet />
      </div>
    </div>
  );
}
