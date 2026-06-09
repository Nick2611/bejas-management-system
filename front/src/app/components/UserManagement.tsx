import { useEffect, useState } from 'react';
import { Edit, Plus, Trash2, UserCog } from 'lucide-react';
import { toast } from 'sonner';

import type { UserRole } from '../context/AuthContext';
import { useAuth } from '../context/AuthContext';
import {
  createUser,
  deleteUser,
  fetchUsers,
  updateUser,
} from '../services/usersApi';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import { Input } from './ui/input';
import { Label } from './ui/label';


interface ManagedUser {
  id: string;
  username: string;
  role: UserRole;
}

export function UserManagement() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [editing, setEditing] = useState<ManagedUser | null>(null);
  const [editPassword, setEditPassword] = useState('');
  const [form, setForm] = useState({
    username: '',
    password: '',
    role: 'empleado' as UserRole,
  });
  const [saving, setSaving] = useState(false);

  const loadUsers = async () => {
    try {
      setUsers(await fetchUsers());
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : 'No se pudieron cargar los usuarios'
      );
    }
  };

  useEffect(() => {
    void loadUsers();
  }, []);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      await createUser(form.username.trim(), form.password, form.role);
      setForm({ username: '', password: '', role: 'empleado' });
      await loadUsers();
      toast.success('Usuario creado');
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : 'No se pudo crear el usuario'
      );
    } finally {
      setSaving(false);
    }
  };

  const openEdit = (user: ManagedUser) => {
    setEditing({ ...user });
    setEditPassword('');
  };

  const saveEdit = async () => {
    if (!editing) return;
    if (!editing.username.trim()) {
      toast.error('El nombre de usuario no puede estar vacío');
      return;
    }

    setSaving(true);
    try {
      await updateUser(editing.id, {
        username: editing.username.trim(),
        role: editing.role,
        ...(editPassword ? { password: editPassword } : {}),
      });
      setEditing(null);
      setEditPassword('');
      await loadUsers();
      toast.success('Usuario actualizado');
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : 'No se pudo actualizar el usuario'
      );
    } finally {
      setSaving(false);
    }
  };

  const remove = async (userId: string) => {
    try {
      await deleteUser(userId);
      await loadUsers();
      toast.success('Usuario eliminado');
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : 'No se pudo eliminar el usuario'
      );
    }
  };

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="text-[#D4AF37] mb-2">Usuarios</h1>
        <p className="text-[#a0a0a0]">
          Crea y administra perfiles de acceso
        </p>
      </div>

      <Card className="bg-[#1a1a1a] border-[#3a3a3a]">
        <CardHeader>
          <CardTitle className="text-[#D4AF37] flex items-center gap-2">
            <Plus className="w-5 h-5" /> Nuevo perfil
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="grid md:grid-cols-4 gap-4 items-end">
            <div className="space-y-2">
              <Label className="text-[#f5f5dc]">Usuario</Label>
              <Input
                value={form.username}
                onChange={event =>
                  setForm({ ...form, username: event.target.value })
                }
                className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
                required
              />
            </div>
            <div className="space-y-2">
              <Label className="text-[#f5f5dc]">Contraseña</Label>
              <Input
                type="password"
                value={form.password}
                onChange={event =>
                  setForm({ ...form, password: event.target.value })
                }
                className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
                required
              />
            </div>
            <div className="space-y-2">
              <Label className="text-[#f5f5dc]">Rol</Label>
              <select
                value={form.role}
                onChange={event =>
                  setForm({
                    ...form,
                    role: event.target.value as UserRole,
                  })
                }
                className="w-full h-9 rounded-md bg-[#0a0a0a] border border-[#3a3a3a] text-[#f5f5dc] px-3"
              >
                <option value="empleado">Empleado</option>
                <option value="admin">Administrador</option>
              </select>
            </div>
            <Button
              type="submit"
              disabled={saving}
              className="bg-[#D4AF37] text-[#0a0a0a]"
            >
              {saving ? 'Creando...' : 'Crear usuario'}
            </Button>
          </form>
        </CardContent>
      </Card>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {users.map(user => (
          <Card key={user.id} className="bg-[#1a1a1a] border-[#3a3a3a]">
            <CardContent className="pt-6 flex items-center gap-3">
              <UserCog className="text-[#D4AF37]" />
              <div className="flex-1">
                <p className="text-[#f5f5dc] font-semibold">{user.username}</p>
                <p className="text-sm text-[#a0a0a0] capitalize">{user.role}</p>
              </div>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => openEdit(user)}
                className="text-[#D4AF37] hover:bg-[#2a2a2a]"
                title="Editar usuario"
              >
                <Edit className="w-4 h-4" />
              </Button>
              {user.role !== 'admin' && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => void remove(user.id)}
                  className="text-red-400 hover:text-red-300 hover:bg-red-950/40"
                  title="Eliminar empleado"
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <Dialog
        open={editing !== null}
        onOpenChange={open => {
          if (!open) {
            setEditing(null);
            setEditPassword('');
          }
        }}
      >
        <DialogContent className="bg-[#1a1a1a] border-[#3a3a3a]">
          <DialogHeader>
            <DialogTitle className="text-[#D4AF37]">
              Editar perfil
            </DialogTitle>
            <DialogDescription className="text-[#a0a0a0]">
              Dejá la contraseña vacía para conservar la actual.
            </DialogDescription>
          </DialogHeader>
          {editing && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label className="text-[#f5f5dc]">Usuario</Label>
                <Input
                  value={editing.username}
                  onChange={event =>
                    setEditing({
                      ...editing,
                      username: event.target.value,
                    })
                  }
                  className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-[#f5f5dc]">Nueva contraseña</Label>
                <Input
                  type="password"
                  value={editPassword}
                  onChange={event => setEditPassword(event.target.value)}
                  placeholder="Sin cambios"
                  className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-[#f5f5dc]">Rol</Label>
                <select
                  value={editing.role}
                  disabled={editing.id === currentUser?.id}
                  onChange={event =>
                    setEditing({
                      ...editing,
                      role: event.target.value as UserRole,
                    })
                  }
                  className="w-full h-9 rounded-md bg-[#0a0a0a] border border-[#3a3a3a] text-[#f5f5dc] px-3"
                >
                  <option value="empleado">Empleado</option>
                  <option value="admin">Administrador</option>
                </select>
                {editing.id === currentUser?.id && (
                  <p className="text-xs text-[#a0a0a0]">
                    No podés cambiar tu propio rol durante la sesión.
                  </p>
                )}
              </div>
              <Button
                onClick={() => void saveEdit()}
                disabled={saving}
                className="w-full bg-[#D4AF37] text-[#0a0a0a] hover:bg-[#B8860B]"
              >
                {saving ? 'Guardando...' : 'Guardar cambios'}
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
