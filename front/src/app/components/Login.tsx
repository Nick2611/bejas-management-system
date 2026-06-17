import { useState } from 'react';
import { useNavigate } from 'react-router';
import {
  ArrowRight,
  Eye,
  EyeOff,
  LoaderCircle,
  LockKeyhole,
  ShieldCheck,
  UserRound,
} from 'lucide-react';
import { toast } from 'sonner';

import logo from '../../assets/bejas_logo.png';
import { useAuth } from '../context/AuthContext';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';

export function Login() {
  const [loginData, setLoginData] = useState({ username: '', password: '' });
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
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
    <main className="relative min-h-screen overflow-hidden bg-[#080808] text-white">
      <div
        className="pointer-events-none absolute inset-0 opacity-80"
        style={{
          backgroundImage:
            'radial-gradient(circle at 12% 15%, rgba(251, 191, 36, 0.14), transparent 30%), radial-gradient(circle at 88% 90%, rgba(161, 98, 7, 0.12), transparent 28%)',
        }}
      />
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.018)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.018)_1px,transparent_1px)] bg-[size:48px_48px] [mask-image:linear-gradient(to_bottom,black,transparent_85%)]" />

      <div className="relative mx-auto flex min-h-screen w-full max-w-7xl items-center px-4 py-6 sm:px-8 lg:px-12 lg:py-10">
        <div className="grid w-full min-w-0 grid-cols-[minmax(0,1fr)] overflow-hidden rounded-[2rem] border border-white/10 bg-[#111111]/90 shadow-[0_32px_90px_rgba(0,0,0,0.55)] backdrop-blur-xl lg:min-h-[680px] lg:grid-cols-[minmax(0,1.08fr)_minmax(0,0.92fr)]">
          <section className="relative hidden overflow-hidden border-r border-white/10 lg:flex lg:flex-col lg:justify-between lg:p-12">
            <div className="pointer-events-none absolute -left-28 -top-32 h-96 w-96 rounded-full bg-amber-400/10 blur-3xl" />
            <div className="pointer-events-none absolute -bottom-40 right-0 h-96 w-96 rounded-full bg-amber-700/10 blur-3xl" />

            <div className="relative">
              <span className="inline-flex items-center gap-2 rounded-full border border-amber-300/20 bg-amber-300/10 px-3 py-1.5 text-xs font-medium tracking-[0.18em] text-amber-200 uppercase">
                <ShieldCheck className="h-3.5 w-3.5" />
                Gestión interna
              </span>
            </div>

            <div className="relative flex flex-1 flex-col items-center justify-center py-6 text-center">
              <div className="relative">
                <div className="absolute inset-10 rounded-full bg-amber-300/20 blur-[55px]" />
                <img
                  src={logo}
                  alt="Estación de Cervezas Bejas"
                  className="relative h-auto w-full max-w-[390px] object-contain drop-shadow-[0_25px_45px_rgba(0,0,0,0.55)]"
                />
              </div>
              <div className="-mt-3 max-w-lg">
                <p className="text-xs font-semibold tracking-[0.32em] text-amber-300 uppercase">
                  Estación de cervezas
                </p>
                <h1 className="mt-4 text-4xl font-semibold tracking-tight text-white">
                  Todo tu negocio,
                  <span className="block bg-gradient-to-r from-amber-200 via-amber-400 to-amber-600 bg-clip-text text-transparent">
                    en un solo lugar.
                  </span>
                </h1>
                <p className="mx-auto mt-4 max-w-md text-sm leading-6 text-zinc-400">
                  Controlá mesas, stock y rendimiento desde una experiencia
                  simple, rápida y centralizada.
                </p>
              </div>
            </div>

            <div className="relative flex items-center justify-between border-t border-white/10 pt-6 text-xs text-zinc-500">
              <span>BEJAS</span>
              <span>Panel de administración</span>
            </div>
          </section>

          <section className="flex min-w-0 items-center justify-center px-5 py-8 sm:px-10 sm:py-12 lg:px-14">
            <div className="w-full min-w-0 max-w-md">
              <div className="mb-8 flex justify-center lg:hidden">
                <div className="relative">
                  <div className="absolute inset-5 rounded-full bg-amber-400/15 blur-2xl" />
                  <img
                    src={logo}
                    alt="Estación de Cervezas Bejas"
                    className="relative h-40 w-40 rounded-full object-contain drop-shadow-[0_18px_30px_rgba(0,0,0,0.45)] sm:h-48 sm:w-48"
                  />
                </div>
              </div>

              <div className="mb-8">
                <p className="mb-3 text-xs font-semibold tracking-[0.24em] text-amber-400 uppercase">
                  Bienvenido de nuevo
                </p>
                <h2 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">
                  Ingresá a tu cuenta
                </h2>
                <p className="mt-3 text-sm leading-6 text-zinc-400">
                  Usá tus credenciales para acceder al panel de Bejas.
                </p>
              </div>

              <form onSubmit={handleLogin} className="space-y-5">
                <div className="space-y-2">
                  <Label
                    htmlFor="username"
                    className="text-sm font-medium text-zinc-200"
                  >
                    Usuario
                  </Label>
                  <div className="group relative">
                    <UserRound className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500 transition-colors group-focus-within:text-amber-400" />
                    <Input
                      id="username"
                      name="username"
                      autoComplete="username"
                      placeholder="Ingresá tu usuario"
                      value={loginData.username}
                      onChange={event => setLoginData({
                        ...loginData,
                        username: event.target.value
                      })}
                      className="h-12 rounded-xl border-white/10 bg-white/[0.04] pl-11 text-white placeholder:text-zinc-600 transition-colors hover:border-white/20 focus-visible:border-amber-400/60 focus-visible:ring-2 focus-visible:ring-amber-400/15"
                      required
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label
                    htmlFor="password"
                    className="text-sm font-medium text-zinc-200"
                  >
                    Contraseña
                  </Label>
                  <div className="group relative">
                    <LockKeyhole className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500 transition-colors group-focus-within:text-amber-400" />
                    <Input
                      id="password"
                      name="password"
                      type={showPassword ? 'text' : 'password'}
                      autoComplete="current-password"
                      placeholder="Ingresá tu contraseña"
                      value={loginData.password}
                      onChange={event => setLoginData({
                        ...loginData,
                        password: event.target.value
                      })}
                      className="h-12 rounded-xl border-white/10 bg-white/[0.04] px-11 text-white placeholder:text-zinc-600 transition-colors hover:border-white/20 focus-visible:border-amber-400/60 focus-visible:ring-2 focus-visible:ring-amber-400/15"
                      required
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(current => !current)}
                      className="absolute right-3 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-lg text-zinc-500 transition-colors hover:bg-white/5 hover:text-zinc-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/50"
                      aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                    >
                      {showPassword ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                </div>

                <Button
                  type="submit"
                  disabled={isLoggingIn}
                  className="group mt-2 h-12 w-full rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 font-semibold text-[#171005] shadow-[0_12px_30px_rgba(217,119,6,0.18)] transition-all hover:from-amber-400 hover:to-amber-500 hover:shadow-[0_14px_35px_rgba(217,119,6,0.28)] focus-visible:ring-2 focus-visible:ring-amber-300/50 disabled:opacity-70"
                >
                  {isLoggingIn ? (
                    <>
                      <LoaderCircle className="h-4 w-4 animate-spin" />
                      Ingresando...
                    </>
                  ) : (
                    <>
                      Ingresar al sistema
                      <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                    </>
                  )}
                </Button>
              </form>

              <div className="mt-8 flex items-center justify-center gap-2 border-t border-white/10 pt-6 text-xs text-zinc-600">
                <LockKeyhole className="h-3.5 w-3.5" />
                <span>Acceso seguro y exclusivo para el personal</span>
              </div>
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
