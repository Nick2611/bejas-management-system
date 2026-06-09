import { useState } from 'react';
import { useNavigate } from 'react-router';
import { toast } from 'sonner';

import logo from 'figma:asset/3ff1d6d16d7d52145a898cdfc527422ef88cd4c9.png';
import { useAuth } from '../context/AuthContext';
import { Button } from './ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Input } from './ui/input';
import { Label } from './ui/label';


export function Login() {
  const [loginData, setLoginData] = useState({ username: '', password: '' });
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleLogin = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsLoggingIn(true);
    try {
      const result = await login(
        loginData.username.trim(),
        loginData.password
      );
      if (result.success) {
        toast.success('¡Bienvenido a Bejas!');
        navigate('/dashboard');
      } else {
        toast.error(result.message);
      }
    } finally {
      setIsLoggingIn(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0a0a0a] p-4">
      <div className="w-full max-w-md">
        <div className="flex justify-center mb-8">
          <img src={logo} alt="Bejas Logo" className="w-48 h-48 object-contain" />
        </div>
        <Card className="bg-[#1a1a1a] border-[#3a3a3a]">
          <CardHeader>
            <CardTitle className="text-[#D4AF37]">Acceso al Sistema</CardTitle>
            <CardDescription className="text-[#a0a0a0]">
              Ingresa tus credenciales para continuar
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleLogin} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="username" className="text-[#f5f5dc]">Usuario</Label>
                <Input
                  id="username"
                  value={loginData.username}
                  onChange={event => setLoginData({
                    ...loginData,
                    username: event.target.value
                  })}
                  className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password" className="text-[#f5f5dc]">Contraseña</Label>
                <Input
                  id="password"
                  type="password"
                  value={loginData.password}
                  onChange={event => setLoginData({
                    ...loginData,
                    password: event.target.value
                  })}
                  className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
                  required
                />
              </div>
              <Button
                type="submit"
                disabled={isLoggingIn}
                className="w-full bg-[#D4AF37] hover:bg-[#B8860B] text-[#0a0a0a]"
              >
                {isLoggingIn ? 'Ingresando...' : 'Ingresar'}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
