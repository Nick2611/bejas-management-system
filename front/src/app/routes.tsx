import { createBrowserRouter, Navigate } from 'react-router';
import { Login } from './components/Login';
import { Layout } from './components/Layout';
import { Dashboard } from './components/Dashboard';
import { Mesas } from './components/Mesas';
import { Stock } from './components/Stock';
import { Configuracion } from './components/Configuracion';
import { Cierre } from './components/Cierre';
import { KPIs } from './components/KPIs';
import { useAuth } from './context/AuthContext';

// Componente para proteger rutas
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isAuthReady } = useAuth();

  if (!isAuthReady) return null;

  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }
  
  return <>{children}</>;
}

// Componente para rutas solo de admin
function AdminRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isAdmin, isAuthReady } = useAuth();

  if (!isAuthReady) return null;

  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  if (!isAdmin) {
    return <Navigate to="/dashboard" replace />;
  }
  
  return <>{children}</>;
}

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Login />
  },
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <Layout />
      </ProtectedRoute>
    ),
    children: [
      {
        path: 'dashboard',
        element: <Dashboard />
      },
      {
        path: 'mesas',
        element: <Mesas />
      },
      {
        path: 'stock',
        element: <Stock />
      },
      {
        path: 'kpis',
        element: (
          <AdminRoute>
            <KPIs />
          </AdminRoute>
        )
      },
      {
        path: 'configuracion',
        element: (
          <AdminRoute>
            <Configuracion />
          </AdminRoute>
        )
      },
      {
        path: 'cierre',
        element: (
          <AdminRoute>
            <Cierre />
          </AdminRoute>
        )
      }
    ]
  },
  {
    path: '*',
    element: <Navigate to="/" replace />
  }
]);
