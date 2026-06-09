import { useEffect, useMemo, useState } from 'react';
import {
  Calendar,
  Download,
  Edit,
  FileText,
  History,
  RefreshCw,
  Send,
  TrendingUp,
} from 'lucide-react';
import { toast } from 'sonner';

import {
  createCashClosing,
  downloadInvoiceReport,
  fetchCashClosingRevisions,
  fetchCashClosings,
  fetchClosings,
  fetchInvoices,
  fetchMonthlySummary,
  retryInvoice,
  retryInvoicePeriod,
  updateCashClosing,
  type CashClosing,
  type CashClosingRevision,
  type Closing,
  type Invoice,
  type MonthlySummary,
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
import { Textarea } from './ui/textarea';


const today = () => new Date().toLocaleDateString('en-CA');
const currentMonth = () => today().slice(0, 7);
const fieldClassName = (
  'bg-[#0a0a0a] border-2 border-[#5a5a5a] text-[#f5f5dc] '
  + 'focus-visible:border-[#D4AF37] focus-visible:ring-[#D4AF37]/30'
);

export function isValidCountedCash(value: string): boolean {
  if (value.trim() === '') return false;
  const counted = Number(value);
  return Number.isInteger(counted) && counted >= 0;
}

export function Cierre() {
  const [closings, setClosings] = useState<Closing[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [cashClosings, setCashClosings] = useState<CashClosing[]>([]);
  const [monthly, setMonthly] = useState<MonthlySummary | null>(null);
  const [selected, setSelected] = useState<Closing | null>(null);
  const [businessDate, setBusinessDate] = useState(today());
  const [summaryMonth, setSummaryMonth] = useState(currentMonth());
  const [countedCash, setCountedCash] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [editingCashClosing, setEditingCashClosing] = (
    useState<CashClosing | null>(null)
  );
  const [editCountedCash, setEditCountedCash] = useState('');
  const [editNotes, setEditNotes] = useState('');
  const [revisionClosing, setRevisionClosing] = useState<CashClosing | null>(
    null
  );
  const [revisions, setRevisions] = useState<CashClosingRevision[]>([]);
  const [afipDate, setAfipDate] = useState(today());
  const [afipMonth, setAfipMonth] = useState(currentMonth());
  const [processingAfip, setProcessingAfip] = useState(false);

  const load = async () => {
    try {
      const [year, monthNumber] = summaryMonth.split('-').map(Number);
      const [sales, loadedInvoices, cash, month] = await Promise.all([
        fetchClosings(),
        fetchInvoices(),
        fetchCashClosings(),
        fetchMonthlySummary(year, monthNumber)
      ]);
      setClosings(sales);
      setInvoices(loadedInvoices);
      setCashClosings(cash);
      setMonthly(month);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo cargar el módulo de cierre');
    }
  };

  useEffect(() => {
    void load();
  }, [summaryMonth]);

  const salesToday = useMemo(
    () => closings.filter(sale => sale.closing_time.slice(0, 10) === today()),
    [closings]
  );

  const closeCash = async () => {
    if (!isValidCountedCash(countedCash)) {
      toast.error('Ingresá el efectivo contado');
      return;
    }
    const counted = Number(countedCash);
    setSaving(true);
    try {
      const result = await createCashClosing(
        businessDate,
        counted,
        notes
      );
      setCountedCash('');
      setNotes('');
      await load();
      toast.success(
        `Cierre realizado. Diferencia: $${result.difference.toLocaleString('es-AR')}`
      );
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo realizar el cierre');
    } finally {
      setSaving(false);
    }
  };

  const openCashClosingEdit = (cashClosing: CashClosing) => {
    setEditingCashClosing(cashClosing);
    setEditCountedCash(String(cashClosing.counted_cash));
    setEditNotes(cashClosing.notes ?? '');
  };

  const saveCashClosingEdit = async () => {
    if (!editingCashClosing || !isValidCountedCash(editCountedCash)) {
      toast.error('Ingresá el efectivo contado');
      return;
    }
    setSaving(true);
    try {
      const updated = await updateCashClosing(editingCashClosing.id, {
        counted_cash: Number(editCountedCash),
        notes: editNotes.trim() || null
      });
      setEditingCashClosing(null);
      await load();
      toast.success(
        `Cierre corregido. Diferencia: $${updated.difference.toLocaleString('es-AR')}`
      );
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo corregir el cierre');
    } finally {
      setSaving(false);
    }
  };

  const openRevisionHistory = async (cashClosing: CashClosing) => {
    try {
      setRevisions(await fetchCashClosingRevisions(cashClosing.id));
      setRevisionClosing(cashClosing);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo cargar el historial');
    }
  };

  const showAfipResult = (
    result: Awaited<ReturnType<typeof retryInvoicePeriod>>
  ) => {
    const details = result.processed_count > 0
      ? ` ${result.authorized_count} autorizada(s), ${result.failed_count} pendiente(s).`
      : '';
    if (result.status === 'completado') {
      toast.success(`${result.message}.${details}`);
    } else if (
      result.status === 'parcial'
      || result.status === 'sin_pendientes'
    ) {
      toast.warning(`${result.message}.${details}`);
    } else {
      toast.error(`${result.message}.${details}`);
    }
  };

  const processAfipDay = async () => {
    setProcessingAfip(true);
    try {
      const result = await retryInvoicePeriod({
        period: 'diario',
        date: afipDate
      });
      showAfipResult(result);
      await load();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo procesar el día');
    } finally {
      setProcessingAfip(false);
    }
  };

  const processAfipMonth = async () => {
    const [year, month] = afipMonth.split('-').map(Number);
    setProcessingAfip(true);
    try {
      const result = await retryInvoicePeriod({
        period: 'mensual',
        year,
        month
      });
      showAfipResult(result);
      await load();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo procesar el mes');
    } finally {
      setProcessingAfip(false);
    }
  };

  const retry = async (invoice: Invoice) => {
    try {
      const result = await retryInvoice(invoice.id);
      await load();
      if (result.status === 'autorizada') {
        toast.success(`Factura autorizada: ${result.display_number}`);
      } else {
        toast.warning('AFIP continúa sin responder');
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo reintentar');
    }
  };

  return (
    <div className="p-8 space-y-7">
      <div>
        <h1 className="text-[#D4AF37] mb-2">Cierres y Facturación</h1>
        <p className="text-[#a0a0a0]">Ventas, caja y estado del mock de AFIP</p>
      </div>

      <div className="grid md:grid-cols-3 gap-5">
        <Card className="bg-[#1a1a1a] border-[#3a3a3a]">
          <CardContent className="pt-6">
            <p className="text-[#a0a0a0] text-sm">Ventas hoy</p>
            <p className="text-2xl text-[#D4AF37]">
              ${salesToday.reduce((sum, sale) => sum + sale.total, 0).toLocaleString('es-AR')}
            </p>
          </CardContent>
        </Card>
        <Card className="bg-[#1a1a1a] border-[#3a3a3a]">
          <CardContent className="pt-6">
            <p className="text-[#a0a0a0] text-sm">Facturas pendientes</p>
            <p className="text-2xl text-orange-400">
              {invoices.filter(invoice => invoice.status === 'pendiente').length}
            </p>
          </CardContent>
        </Card>
        <Card className="bg-[#1a1a1a] border-[#3a3a3a]">
          <CardContent className="pt-6">
            <p className="text-[#a0a0a0] text-sm">Ventas del mes</p>
            <p className="text-2xl text-[#D4AF37]">
              ${(monthly?.total_sales ?? 0).toLocaleString('es-AR')}
            </p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="ventas">
        <TabsList className="bg-[#1a1a1a]">
          <TabsTrigger value="ventas">Ventas</TabsTrigger>
          <TabsTrigger value="facturas">AFIP</TabsTrigger>
          <TabsTrigger value="diario">Cierre diario</TabsTrigger>
          <TabsTrigger value="mensual">Mensual</TabsTrigger>
        </TabsList>

        <TabsContent value="ventas" className="mt-5">
          <div className="space-y-3">
            {closings.map(sale => (
              <Card
                key={sale.id}
                className="bg-[#1a1a1a] border-[#3a3a3a] cursor-pointer hover:border-[#D4AF37]"
                onClick={() => setSelected(sale)}
              >
                <CardContent className="pt-6 flex justify-between">
                  <div>
                    <p className="text-[#f5f5dc]">
                      {sale.table_name || `Mesa ${sale.table_number}`}
                    </p>
                    <p className="text-xs text-[#a0a0a0]">
                      {new Date(sale.closing_time).toLocaleString('es-AR')}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-[#D4AF37] font-bold">
                      ${sale.total.toLocaleString('es-AR')}
                    </p>
                    <p className="text-xs text-[#a0a0a0]">
                      {sale.invoice?.status ?? 'sin factura'}
                    </p>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="facturas" className="mt-5 space-y-4">
          <div className="grid lg:grid-cols-2 gap-4">
            <Card className="bg-[#1a1a1a] border-[#3a3a3a]">
              <CardHeader>
                <CardTitle className="text-[#D4AF37] text-base">
                  Facturación diaria
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <Input
                  type="date"
                  value={afipDate}
                  onChange={event => setAfipDate(event.target.value)}
                  className={fieldClassName}
                />
                <div className="flex flex-wrap gap-2">
                  <Button
                    onClick={() => void processAfipDay()}
                    disabled={processingAfip || !afipDate}
                    className="bg-[#D4AF37] text-[#0a0a0a]"
                  >
                    <Send className="w-4 h-4 mr-2" />
                    Enviar día a AFIP
                  </Button>
                  <Button
                    onClick={() => void downloadInvoiceReport(afipDate)}
                    disabled={!afipDate}
                    variant="outline"
                    className="border-[#D4AF37] text-[#f5f5dc]"
                  >
                    <Download className="w-4 h-4 mr-2" />
                    Descargar reporte
                  </Button>
                </div>
              </CardContent>
            </Card>
            <Card className="bg-[#1a1a1a] border-[#3a3a3a]">
              <CardHeader>
                <CardTitle className="text-[#D4AF37] text-base">
                  Facturación mensual
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <Input
                  type="month"
                  value={afipMonth}
                  onChange={event => setAfipMonth(event.target.value)}
                  className={fieldClassName}
                />
                <Button
                  onClick={() => void processAfipMonth()}
                  disabled={processingAfip || !afipMonth}
                  className="bg-[#D4AF37] text-[#0a0a0a]"
                >
                  <Send className="w-4 h-4 mr-2" />
                  Enviar mes a AFIP
                </Button>
              </CardContent>
            </Card>
          </div>
          {invoices.map(invoice => (
            <Card key={invoice.id} className="bg-[#1a1a1a] border-[#3a3a3a]">
              <CardContent className="pt-6 flex justify-between items-center">
                <div>
                  <p className="text-[#f5f5dc]">{invoice.display_number}</p>
                  <p className={invoice.status === 'autorizada' ? 'text-green-500' : 'text-orange-400'}>
                    {invoice.status}
                  </p>
                  {invoice.attempts.at(-1)?.error && (
                    <p className="text-xs text-red-400">{invoice.attempts.at(-1)?.error}</p>
                  )}
                </div>
                {invoice.status === 'pendiente' && (
                  <Button onClick={() => void retry(invoice)} variant="outline">
                    <RefreshCw className="w-4 h-4 mr-2" /> Reintentar
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="diario" className="mt-5 space-y-5">
          <Card className="bg-[#1a1a1a] border-[#3a3a3a]">
            <CardHeader><CardTitle className="text-[#D4AF37]">Nuevo cierre de caja</CardTitle></CardHeader>
            <CardContent className="grid md:grid-cols-3 gap-4 items-end">
              <div className="space-y-2">
                <Label className="text-[#f5f5dc]">Fecha comercial</Label>
                <Input
                  type="date"
                  value={businessDate}
                  onChange={event => setBusinessDate(event.target.value)}
                  className={fieldClassName}
                />
              </div>
              <div className="space-y-2">
                <Label className="text-[#f5f5dc]">Efectivo contado</Label>
                <Input
                  type="number"
                  min="0"
                  value={countedCash}
                  placeholder="Ingresá el importe contado"
                  onFocus={event => event.currentTarget.select()}
                  onChange={event => setCountedCash(event.target.value)}
                  className={fieldClassName}
                />
              </div>
              <Button onClick={() => void closeCash()} disabled={saving} className="bg-[#D4AF37] text-[#0a0a0a]">
                <Calendar className="w-4 h-4 mr-2" /> Cerrar día
              </Button>
              <div className="md:col-span-3 space-y-2">
                <Label className="text-[#f5f5dc]">Notas</Label>
                <Textarea
                  placeholder="Observaciones del cierre"
                  value={notes}
                  onChange={event => setNotes(event.target.value)}
                  className={`${fieldClassName} min-h-24`}
                />
              </div>
            </CardContent>
          </Card>
          {cashClosings.map(cash => (
            <Card key={cash.id} className="bg-[#1a1a1a] border-[#3a3a3a]">
              <CardContent className="pt-6 grid md:grid-cols-6 gap-3 items-center">
                <p className="text-[#f5f5dc]">{cash.business_date}</p>
                <p className="text-[#D4AF37]">${cash.total_sales.toLocaleString('es-AR')}</p>
                <p className="text-[#a0a0a0]">{cash.sales_count} ventas</p>
                <p className={cash.difference === 0 ? 'text-green-500' : 'text-orange-400'}>
                  Diferencia: ${cash.difference.toLocaleString('es-AR')}
                </p>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => openCashClosingEdit(cash)}
                  className="border-[#D4AF37] text-[#f5f5dc]"
                >
                  <Edit className="w-4 h-4 mr-2" /> Editar
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void openRevisionHistory(cash)}
                  className="border-[#3a3a3a] text-[#f5f5dc]"
                >
                  <History className="w-4 h-4 mr-2" /> Historial
                </Button>
              </CardContent>
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="mensual" className="mt-5">
          <Card className="bg-[#1a1a1a] border-[#3a3a3a]">
            <CardHeader>
              <CardTitle className="text-[#D4AF37] flex gap-2">
                <TrendingUp /> Resumen mensual
              </CardTitle>
            </CardHeader>
            <CardContent className="grid md:grid-cols-3 gap-5">
              <Input
                type="month"
                value={summaryMonth}
                onChange={event => setSummaryMonth(event.target.value)}
                className="md:col-span-3 max-w-xs"
              />
              <p className="text-[#f5f5dc]">Ventas: {monthly?.sales_count ?? 0}</p>
              <p className="text-[#f5f5dc]">Días activos: {monthly?.active_days ?? 0}</p>
              <p className="text-[#f5f5dc]">Promedio: ${(monthly?.daily_average ?? 0).toLocaleString('es-AR')}</p>
              <p className="text-green-500">Efectivo: ${(monthly?.total_cash ?? 0).toLocaleString('es-AR')}</p>
              <p className="text-blue-400">Crédito: ${(monthly?.total_credit_card ?? 0).toLocaleString('es-AR')}</p>
              <p className="text-purple-400">Débito: ${(monthly?.total_debit_card ?? 0).toLocaleString('es-AR')}</p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog
        open={!!editingCashClosing}
        onOpenChange={open => !open && setEditingCashClosing(null)}
      >
        <DialogContent className="bg-[#1a1a1a] border-[#3a3a3a]">
          <DialogHeader>
            <DialogTitle className="text-[#D4AF37]">
              Corregir cierre {editingCashClosing?.business_date}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label className="text-[#f5f5dc]">Efectivo contado</Label>
              <Input
                type="number"
                min="0"
                value={editCountedCash}
                onFocus={event => event.currentTarget.select()}
                onChange={event => setEditCountedCash(event.target.value)}
                className={fieldClassName}
              />
            </div>
            <div className="space-y-2">
              <Label className="text-[#f5f5dc]">Notas</Label>
              <Textarea
                value={editNotes}
                onChange={event => setEditNotes(event.target.value)}
                className={`${fieldClassName} min-h-24`}
              />
            </div>
            <p className="text-xs text-[#a0a0a0]">
              La corrección quedará registrada en el historial del cierre.
            </p>
            <Button
              onClick={() => void saveCashClosingEdit()}
              disabled={saving}
              className="w-full bg-[#D4AF37] text-[#0a0a0a]"
            >
              {saving ? 'Guardando...' : 'Guardar corrección'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog
        open={!!revisionClosing}
        onOpenChange={open => !open && setRevisionClosing(null)}
      >
        <DialogContent className="bg-[#1a1a1a] border-[#3a3a3a] max-w-2xl max-h-[80vh] overflow-auto">
          <DialogHeader>
            <DialogTitle className="text-[#D4AF37]">
              Historial del cierre {revisionClosing?.business_date}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            {revisions.length === 0 && (
              <p className="text-[#a0a0a0]">
                Este cierre todavía no tiene correcciones.
              </p>
            )}
            {revisions.map(revision => (
              <div
                key={revision.id}
                className="rounded-lg border border-[#3a3a3a] bg-[#2a2a2a] p-4 space-y-2"
              >
                <p className="text-xs text-[#a0a0a0]">
                  {new Date(revision.changed_at).toLocaleString('es-AR')}
                  {' · '}Usuario #{revision.changed_by_id}
                </p>
                <p className="text-[#f5f5dc]">
                  Efectivo: ${revision.previous_counted_cash.toLocaleString('es-AR')}
                  {' → '}
                  ${revision.new_counted_cash.toLocaleString('es-AR')}
                </p>
                <p className="text-sm text-[#a0a0a0]">
                  Notas: {revision.previous_notes || 'Sin notas'}
                  {' → '}
                  {revision.new_notes || 'Sin notas'}
                </p>
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={!!selected} onOpenChange={open => !open && setSelected(null)}>
        <DialogContent className="bg-[#1a1a1a] border-[#3a3a3a] max-w-2xl">
          <DialogHeader>
            <DialogTitle className="text-[#D4AF37] flex gap-2">
              <FileText /> Detalle de venta
            </DialogTitle>
          </DialogHeader>
          {selected && (
            <div className="space-y-3">
              {selected.items.map(item => (
                <div key={item.id} className="flex justify-between p-2 bg-[#2a2a2a] rounded">
                  <span className="text-[#f5f5dc]">{item.quantity} x {item.product_name}</span>
                  <span className="text-[#D4AF37]">${item.subtotal.toLocaleString('es-AR')}</span>
                </div>
              ))}
              <div className="border-t border-[#3a3a3a] pt-3 text-right">
                <p className="text-[#a0a0a0]">Subtotal: ${selected.subtotal.toLocaleString('es-AR')}</p>
                <p className="text-green-500">Descuento: -${selected.discount.toLocaleString('es-AR')}</p>
                <p className="text-xl text-[#D4AF37]">Total: ${selected.total.toLocaleString('es-AR')}</p>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
