import { useEffect, useState } from 'react';
import { Edit, Plus, Target, Trash2, Trophy } from 'lucide-react';
import { toast } from 'sonner';

import {
  createGoal,
  deleteGoal,
  fetchGoals,
  fetchKpiSummary,
  updateGoal,
  type Goal,
  type KpiSummary,
} from '../services/businessApi';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';


type Period = Goal['period'];
type EditingGoal = Omit<Goal, 'target_amount'> & {
  target_amount: string;
};

export function KPIs() {
  const [goals, setGoals] = useState<Goal[]>([]);
  const [summary, setSummary] = useState<KpiSummary | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<EditingGoal | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    period: 'diario' as Period,
    target_amount: '',
    description: ''
  });

  const load = async () => {
    try {
      const [loadedGoals, loadedSummary] = await Promise.all([
        fetchGoals(),
        fetchKpiSummary()
      ]);
      setGoals(loadedGoals);
      setSummary(loadedSummary);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudieron cargar los KPI');
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const create = async () => {
    const amount = Number(form.target_amount);
    if (!Number.isInteger(amount) || amount <= 0) {
      toast.error('El objetivo debe ser un entero mayor a cero');
      return;
    }
    setSaving(true);
    try {
      await createGoal({
        period: form.period,
        target_amount: amount,
        description: form.description || undefined
      });
      setDialogOpen(false);
      setForm({ period: 'diario', target_amount: '', description: '' });
      await load();
      toast.success('Objetivo creado');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo crear el objetivo');
    } finally {
      setSaving(false);
    }
  };

  const saveEdit = async () => {
    if (!editing) return;
    const targetAmount = Number(editing.target_amount);
    if (!Number.isInteger(targetAmount) || targetAmount <= 0) {
      toast.error('El objetivo debe ser un entero mayor a cero');
      return;
    }
    setSaving(true);
    try {
      await updateGoal(editing.id, {
        period: editing.period,
        target_amount: targetAmount,
        description: editing.description
      });
      setEditing(null);
      await load();
      toast.success('Objetivo actualizado');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo actualizar');
    } finally {
      setSaving(false);
    }
  };

  const remove = async (goal: Goal) => {
    try {
      await deleteGoal(goal.id);
      await load();
      toast.success('Objetivo eliminado');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo eliminar');
    }
  };

  const periodSummary = (period: Period) => {
    if (!summary) return { total_sales: 0, sales_count: 0 };
    return period === 'diario'
      ? summary.daily
      : period === 'semanal'
        ? summary.weekly
        : summary.monthly;
  };

  const renderGoals = (period: Period) => {
    const filtered = goals.filter(goal => goal.period === period);
    if (!filtered.length) {
      return (
        <Card className="bg-[#1a1a1a] border-[#3a3a3a]">
          <CardContent className="py-10 text-center text-[#a0a0a0]">
            No hay objetivos para este período.
          </CardContent>
        </Card>
      );
    }
    return (
      <div className="grid lg:grid-cols-2 gap-5">
        {filtered.map(goal => {
          const completed = goal.progress >= 100;
          return (
            <Card
              key={goal.id}
              className={`bg-[#1a1a1a] border-2 ${completed ? 'border-green-500' : 'border-[#3a3a3a]'}`}
            >
              <CardHeader>
                <CardTitle className="text-[#f5f5dc] flex justify-between">
                  <span className="flex gap-2">
                    {completed && <Trophy className="text-green-500" />}
                    {goal.description || `Objetivo ${goal.period}`}
                  </span>
                  <span>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setEditing({
                        ...goal,
                        target_amount: String(goal.target_amount)
                      })}
                    >
                      <Edit className="w-4 h-4 text-[#D4AF37]" />
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => void remove(goal)}>
                      <Trash2 className="w-4 h-4 text-red-500" />
                    </Button>
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex justify-between">
                  <span className="text-[#D4AF37] font-bold">
                    ${goal.current_sales.toLocaleString('es-AR')}
                  </span>
                  <span className="text-[#f5f5dc]">
                    ${goal.target_amount.toLocaleString('es-AR')}
                  </span>
                </div>
                <div className="h-3 bg-[#3a3a3a] rounded">
                  <div
                    className={`h-3 rounded ${completed ? 'bg-green-500' : 'bg-[#D4AF37]'}`}
                    style={{ width: `${Math.min(goal.progress, 100)}%` }}
                  />
                </div>
                <div className="flex justify-between text-xs text-[#a0a0a0]">
                  <span>{goal.start_date}</span>
                  <span>{goal.progress.toFixed(1)}%</span>
                  <span>{goal.end_date}</span>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    );
  };

  return (
    <div className="p-8 space-y-7">
      <div className="flex justify-between">
        <div>
          <h1 className="text-[#D4AF37] mb-2">KPIs y Objetivos</h1>
          <p className="text-[#a0a0a0]">Datos calculados desde las ventas persistidas</p>
        </div>
        <Button onClick={() => setDialogOpen(true)} className="bg-[#D4AF37] text-[#0a0a0a]">
          <Plus className="w-4 h-4 mr-2" /> Nuevo objetivo
        </Button>
      </div>

      <div className="grid md:grid-cols-3 gap-5">
        {(['diario', 'semanal', 'mensual'] as Period[]).map(period => {
          const current = periodSummary(period);
          return (
            <Card
              key={period}
              className="bg-[#1a1a1a] border-[#3a3a3a] transition-colors hover:border-[#D4AF37] hover:bg-[#202020]"
            >
              <CardHeader>
                <CardTitle className="text-[#f5f5dc] capitalize flex gap-2">
                  <Target className="text-[#D4AF37]" /> {period}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl text-[#D4AF37]">
                  ${current.total_sales.toLocaleString('es-AR')}
                </p>
                <p className="text-xs text-[#a0a0a0]">{current.sales_count} ventas</p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <Card className="bg-[#1a1a1a] border-[#3a3a3a]">
        <CardHeader>
          <CardTitle className="text-[#D4AF37]">
            Mesas cerradas por empleado este mes
          </CardTitle>
        </CardHeader>
        <CardContent>
          {!summary?.employee_performance.length ? (
            <p className="text-[#a0a0a0]">
              Todavía no hay cierres registrados este mes.
            </p>
          ) : (
            <div className="space-y-2">
              {summary.employee_performance.map((employee, index) => (
                <div
                  key={employee.user_id}
                  className="grid grid-cols-[3rem_1fr_auto_auto] gap-3 items-center p-3 rounded-lg border border-[#3a3a3a] transition-colors hover:border-[#D4AF37] hover:bg-[#242424]"
                >
                  <span className="text-[#D4AF37] font-bold">#{index + 1}</span>
                  <span className="text-[#f5f5dc]">{employee.username}</span>
                  <span className="text-[#a0a0a0]">
                    {employee.closed_tables} mesas
                  </span>
                  <span className="text-[#D4AF37]">
                    ${employee.total_sales.toLocaleString('es-AR')}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Tabs defaultValue="diario">
        <TabsList className="bg-[#1a1a1a]">
          <TabsTrigger value="diario">Diario</TabsTrigger>
          <TabsTrigger value="semanal">Semanal</TabsTrigger>
          <TabsTrigger value="mensual">Mensual</TabsTrigger>
        </TabsList>
        {(['diario', 'semanal', 'mensual'] as Period[]).map(period => (
          <TabsContent key={period} value={period} className="mt-5">
            {renderGoals(period)}
          </TabsContent>
        ))}
      </Tabs>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="bg-[#1a1a1a] border-[#3a3a3a]">
          <DialogHeader><DialogTitle className="text-[#D4AF37]">Nuevo objetivo</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <Label className="text-[#f5f5dc]">Período</Label>
            <select
              value={form.period}
              onChange={event => setForm({ ...form, period: event.target.value as Period })}
              className="w-full h-9 bg-[#0a0a0a] border border-[#3a3a3a] text-[#f5f5dc] rounded px-3"
            >
              <option value="diario">Diario</option>
              <option value="semanal">Semanal</option>
              <option value="mensual">Mensual</option>
            </select>
            <Input type="number" placeholder="Monto" value={form.target_amount} onChange={event => setForm({ ...form, target_amount: event.target.value })} />
            <Input placeholder="Descripción" value={form.description} onChange={event => setForm({ ...form, description: event.target.value })} />
            <Button onClick={() => void create()} disabled={saving} className="w-full bg-[#D4AF37] text-[#0a0a0a]">Crear</Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={!!editing} onOpenChange={open => !open && setEditing(null)}>
        <DialogContent className="bg-[#1a1a1a] border-[#3a3a3a]">
          <DialogHeader><DialogTitle className="text-[#D4AF37]">Editar objetivo</DialogTitle></DialogHeader>
          {editing && (
            <div className="space-y-4">
              <select
                value={editing.period}
                onChange={event => setEditing({
                  ...editing,
                  period: event.target.value as Period
                })}
                className="w-full h-9 bg-[#0a0a0a] border border-[#3a3a3a] text-[#f5f5dc] rounded px-3"
              >
                <option value="diario">Diario</option>
                <option value="semanal">Semanal</option>
                <option value="mensual">Mensual</option>
              </select>
              <Input type="number" value={editing.target_amount} onChange={event => setEditing({ ...editing, target_amount: event.target.value })} />
              <Input value={editing.description ?? ''} onChange={event => setEditing({ ...editing, description: event.target.value })} />
              <Button onClick={() => void saveEdit()} disabled={saving} className="w-full bg-[#D4AF37] text-[#0a0a0a]">Guardar</Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
