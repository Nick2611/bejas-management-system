import { apiRequest } from './apiClient';
import type { User, UserRole } from '../context/AuthContext';

export const fetchUsers = () =>
  apiRequest<User[]>('/users', {}, {
    fallback: 'No se pudieron cargar los usuarios'
  }).then(users => users.map(user => ({ ...user, id: String(user.id) })));

export const createUser = (
  username: string,
  password: string,
  role: UserRole
) => apiRequest('/auth/register', {
  method: 'POST',
  body: JSON.stringify({ username, password, role })
}, { fallback: 'No se pudo registrar el usuario' });

export const deleteUser = (userId: string) =>
  apiRequest<void>(`/users/${userId}`, {
    method: 'DELETE',
  }, { fallback: 'No se pudo eliminar el usuario' });

export const updateUser = (
  userId: string,
  payload: {
    username?: string;
    password?: string;
    role?: UserRole;
  }
) => apiRequest<User>(`/users/${userId}`, {
  method: 'PATCH',
  body: JSON.stringify(payload),
}, { fallback: 'No se pudo actualizar el usuario' });
