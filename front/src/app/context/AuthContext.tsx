import React, { createContext, useContext, useEffect, useState } from 'react';

import { apiRequest, UNAUTHORIZED_EVENT } from '../services/apiClient';

export type UserRole = 'admin' | 'empleado';

export interface User {
  id: string;
  username: string;
  role: UserRole;
}

interface JwtClaims extends Record<string, unknown> {
  sub?: string;
  user_id?: string | number;
  username?: string;
  role?: string;
  exp?: number;
}

interface LoginResponse {
  access_token: string;
  token_type?: string;
}

export type LoginResult =
  | { success: true }
  | { success: false; message: string };

interface AuthContextType {
  user: User | null;
  login: (username: string, password: string) => Promise<LoginResult>;
  logout: () => void;
  isAuthenticated: boolean;
  isAdmin: boolean;
  isAuthReady: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function isUserRole(role: unknown): role is UserRole {
  return role === 'admin' || role === 'empleado';
}

function getUserFromClaims(claims: JwtClaims): User | null {
  if (typeof claims.exp === 'number' && claims.exp * 1000 <= Date.now()) {
    return null;
  }
  const username = claims.username ?? claims.sub;
  if (!username) return null;
  return {
    id: String(claims.user_id ?? username),
    username: String(username),
    role: isUserRole(claims.role) ? claims.role : 'empleado'
  };
}

async function validateAccessToken(token: string): Promise<User | null> {
  try {
    const claims = await apiRequest<JwtClaims>('/auth/validate', {}, { token });
    return getUserFromClaims(claims);
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isAuthReady, setIsAuthReady] = useState(false);

  const logout = () => {
    setUser(null);
    localStorage.removeItem('bejas_user');
    localStorage.removeItem('bejas_access_token');
    localStorage.removeItem('bejas_token_type');
  };

  useEffect(() => {
    const restoreSession = async () => {
      const token = localStorage.getItem('bejas_access_token');
      const restoredUser = token ? await validateAccessToken(token) : null;
      if (restoredUser) {
        setUser(restoredUser);
        localStorage.setItem('bejas_user', JSON.stringify(restoredUser));
      } else {
        logout();
      }
      setIsAuthReady(true);
    };
    void restoreSession();
  }, []);

  useEffect(() => {
    const handleUnauthorized = () => logout();
    window.addEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
    return () => window.removeEventListener(
      UNAUTHORIZED_EVENT,
      handleUnauthorized
    );
  }, []);

  const login = async (
    username: string,
    password: string
  ): Promise<LoginResult> => {
    try {
      const payload = await apiRequest<LoginResponse>('/auth', {
        method: 'POST',
        body: JSON.stringify({ username, password })
      }, {
        auth: false,
        fallback: 'No se pudo iniciar sesión'
      });
      if (!payload.access_token) {
        return {
          success: false,
          message: 'El backend no devolvió un token de acceso'
        };
      }
      const loggedInUser = await validateAccessToken(payload.access_token);
      if (!loggedInUser) {
        return {
          success: false,
          message: 'El backend no pudo validar la sesión'
        };
      }
      setUser(loggedInUser);
      localStorage.setItem('bejas_user', JSON.stringify(loggedInUser));
      localStorage.setItem('bejas_access_token', payload.access_token);
      localStorage.setItem('bejas_token_type', payload.token_type ?? 'bearer');
      return { success: true };
    } catch (error) {
      return {
        success: false,
        message: error instanceof Error
          ? error.message
          : 'No se pudo conectar con el backend'
      };
    }
  };

  return (
    <AuthContext.Provider value={{
      user,
      login,
      logout,
      isAuthenticated: !!user,
      isAdmin: user?.role === 'admin',
      isAuthReady
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
