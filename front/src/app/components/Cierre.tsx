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
  declareFiscalPeriod,
  createCashClosing,
  fetchCashClosingRevisions,
  fetchCashClosings,
  fetchClosings,
  fetchFiscalPeriodSummary,
  fetchInvoices,
  fetchMonthlySummary,
  retryInvoice,
  retryInvoicePeriod,
  updateCashClosing,
  validateFiscalPeriod,
  type CashClosing,
  type CashClosingRevision,
  type ClosureValidation,
  type Closing,
  type FiscalClosure,
  type FiscalPeriodSummary,
  type FiscalPeriodType,
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
const monthBounds = (value: string) => {
  const [year, month] = value.split('-').map(Number);
  const lastDay = new Date(Date.UTC(year, month, 0)).getUTCDate();
  return {
    from: `${value}-01`,
    to: `${value}-${String(lastDay).padStart(2, '0')}`,
  };
};
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
  const [periodType, setPeriodType] = useState<FiscalPeriodType>('DAY');
  const [fiscalDay, setFiscalDay] = useState(today());
  const [fiscalMonth, setFiscalMonth] = useState(currentMonth());
  const [customFrom, setCustomFrom] = useState(today());
  const [customTo, setCustomTo] = useState(today());
  const [processingAfip, setProcessingAfip] = useState(false);
  const [declaringPeriod, setDeclaringPeriod] = useState(false);
  const [fiscalSummary, setFiscalSummary] = (
    useState<FiscalPeriodSummary | null>(null)
  );
  const [validation, setValidation] = (
    useState<ClosureValidation | null>(null)
  );
  const [declaredClosure, setDeclaredClosure] = (
    useState<FiscalClosure | null>(null)
  );

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

  const fiscalRange = useMemo(() => {
    if (periodType === 'DAY') {
      return { from: fiscalDay, to: fiscalDay };
    }
    if (periodType === 'MONTH') {
      return monthBounds(fiscalMonth);
    }
    return { from: customFrom, to: customTo };
  }, [periodType, fiscalDay, fiscalMonth, customFrom, customTo]);

  const fiscalRequest = useMemo(() => ({
    periodFrom: fiscalRange.from,
    periodTo: fiscalRange.to,
    periodType,
  }), [fiscalRange, periodType]);

  const loadFiscalSummary = async () => {
    if (!fiscalRange.from || !fiscalRange.to) return;
    try {
      setFiscalSummary(
        await fetchFiscalPeriodSummary(fiscalRange.from, fiscalRange.to)
      );
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : 'No se pudo cargar el resumen fiscal'
      );
    }
  };

  useEffect(() => {
    setValidation(null);
    setDeclaredClosure(null);
    void loadFiscalSummary();
  }, [fiscalRange.from, fiscalRange.to, periodType]);

  const salesToday = useMemo(
    () => closings.filter(sale => sale.business_date === today()),
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
      setValidation(null);
      await Promise.all([load(), loadFiscalSummary()]);
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

  const validatePeriod = async () => {
    setProcessingAfip(true);
    try {
      const result = await validateFiscalPeriod(fiscalRequest);
      setValidation(result);
      setFiscalSummary(result.summary);
      if (result.can_declare) toast.success(result.message);
      else toast.warning(result.message);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : 'No se pudo validar el período'
      );
    } finally {
      setProcessingAfip(false);
    }
  };

  const retryPeriod = async () => {
    setProcessingAfip(true);
    try {
      const result = await retryInvoicePeriod({
        periodFrom: fiscalRange.from,
        periodTo: fiscalRange.to,
      });
      if (result.status === 'encolado') toast.success(result.message);
      else if (result.status === 'sin_pendientes') toast.warning(result.message);
      else toast.error(result.message);
      setValidation(null);
      await Promise.all([load(), loadFiscalSummary()]);
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : 'No se pudieron reintentar los comprobantes'
      );
    } finally {
      setProcessingAfip(false);
    }
  };

  const declarePeriod = async () => {
    setProcessingAfip(true);
    setDeclaringPeriod(true);
    try {
      const [result] = await Promise.all([
        declareFiscalPeriod(fiscalRequest),
        new Promise(resolve => window.setTimeout(resolve, 1800)),
      ]);
      setDeclaredClosure(result.closure);
      setValidation(current => current ? {
        ...current,
        status: 'CLOSURE_DECLARED',
        message: result.message,
      } : current);
      toast.success(result.message);
      await Promise.all([load(), loadFiscalSummary()]);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : 'No se pudo declarar el período'
      );
    } finally {
      setDeclaringPeriod(false);
      setProcessingAfip(false);
    }
  };

  const downloadClosureReport = () => {
    if (!declaredClosure) return;
    const blob = new Blob(
      [JSON.stringify(declaredClosure, null, 2)],
      { type: 'application/json' }
    );
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = (
      `declaracion-fiscal-${declaredClosure.period_from}`
      + `-${declaredClosure.period_to}.json`
    );
    link.click();
    URL.revokeObjectURL(url);
  };

  const retry = async (invoice: Invoice) => {
    try {
      const result = await retryInvoice(invoice.id);
      await load();
      if (result.status === 'INVOICE_AUTHORIZED') {
        toast.success(`Factura autorizada: ${result.display_number}`);
      } else {
        toast.success('El comprobante fue encolado para un nuevo intento');
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo reintentar');
    }
  };

  return (
    <div className="p-8 space-y-7">
      {declaringPeriod && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
          role="status"
          aria-live="polite"
          aria-label="Comunicando la declaración fiscal con ARCA"
        >
          <Card className="w-[min(92vw,430px)] border-[#D4AF37] bg-[#151515]">
            <CardContent className="flex flex-col items-center gap-4 px-8 py-10 text-center">
              <RefreshCw className="h-10 w-10 animate-spin text-[#D4AF37]" />
              <div>
                <p className="text-lg font-semibold text-[#f5f5dc]">
                  Comunicando con ARCA
                </p>
                <p className="mt-2 text-sm text-[#a0a0a0]">
                  Estamos validando y registrando la declaración fiscal simulada.
                </p>
              </div>
              <p className="text-xs text-[#D4AF37]">
                No cierres esta pantalla hasta recibir la confirmación.
              </p>
            </CardContent>
          </Card>
        </div>
      )}
      <div>
        <h1 className="text-[#D4AF37] mb-2">Cierres y Facturación</h1>
        <p className="text-[#a0a0a0]">
          Ventas individuales, conciliación de caja y declaración fiscal
        </p>
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
              {invoices.filter(invoice => [
                'INVOICE_PENDING',
                'INVOICE_QUEUED',
                'INVOICE_AUTHORIZING',
                'INVOICE_RETRY_PENDING',
              ].includes(invoice.status)).length}
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
          <Card className="bg-[#1a1a1a] border-[#3a3a3a]">
            <CardHeader>
              <CardTitle className="text-[#D4AF37]">
                Declaración fiscal del período
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="grid md:grid-cols-4 gap-3 items-end">
                <div className="space-y-2">
                  <Label className="text-[#f5f5dc]">Tipo de período</Label>
                  <select
                    value={periodType}
                    onChange={event => setPeriodType(
                      event.target.value as FiscalPeriodType
                    )}
                    className={`${fieldClassName} h-10 w-full rounded-md px-3`}
                  >
                    <option value="DAY">Día específico</option>
                    <option value="MONTH">Mes completo</option>
                    <option value="CUSTOM">Rango de fechas</option>
                  </select>
                </div>
                {periodType === 'DAY' && (
                  <div className="space-y-2 md:col-span-2">
                    <Label className="text-[#f5f5dc]">Día</Label>
                    <Input
                      type="date"
                      value={fiscalDay}
                      onChange={event => setFiscalDay(event.target.value)}
                      className={fieldClassName}
                    />
                  </div>
                )}
                {periodType === 'MONTH' && (
                  <div className="space-y-2 md:col-span-2">
                    <Label className="text-[#f5f5dc]">Mes</Label>
                    <Input
                      type="month"
                      value={fiscalMonth}
                      onChange={event => setFiscalMonth(event.target.value)}
                      className={fieldClassName}
                    />
                  </div>
                )}
                {periodType === 'CUSTOM' && (
                  <>
                    <div className="space-y-2">
                      <Label className="text-[#f5f5dc]">Desde</Label>
                      <Input
                        type="date"
                        value={customFrom}
                        onChange={event => setCustomFrom(event.target.value)}
                        className={fieldClassName}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-[#f5f5dc]">Hasta</Label>
                      <Input
                        type="date"
                        value={customTo}
                        onChange={event => setCustomTo(event.target.value)}
                        className={fieldClassName}
                      />
                    </div>
                  </>
                )}
                <Button
                  onClick={() => void validatePeriod()}
                  disabled={processingAfip}
                  variant="outline"
                  className="border-[#D4AF37] text-[#f5f5dc]"
                >
                  <FileText className="w-4 h-4 mr-2" />
                  Validar período
                </Button>
              </div>

              <div className="flex flex-wrap gap-2">
                <Button
                  onClick={() => void retryPeriod()}
                  disabled={processingAfip}
                  variant="outline"
                  className="border-orange-400 text-orange-300"
                >
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Reintentar comprobantes pendientes
                </Button>
                <Button
                  onClick={() => void declarePeriod()}
                  disabled={
                    processingAfip
                    || !validation?.can_declare
                    || validation.status === 'CLOSURE_DECLARED'
                  }
                  className="bg-[#D4AF37] text-[#0a0a0a]"
                >
                  <Send className="w-4 h-4 mr-2" />
                  Declarar período
                </Button>
                <Button
                  onClick={downloadClosureReport}
                  disabled={!declaredClosure}
                  variant="outline"
                  className="border-[#3a3a3a] text-[#f5f5dc]"
                >
                  <Download className="w-4 h-4 mr-2" />
                  Generar reporte fiscal
                </Button>
              </div>

              {validation && (
                <div className={
                  `rounded-md border p-3 ${
                    validation.can_declare
                      ? 'border-green-700 bg-green-950/20 text-green-300'
                      : 'border-orange-700 bg-orange-950/20 text-orange-300'
                  }`
                }>
                  {validation.message}
                </div>
              )}
            </CardContent>
          </Card>

          {fiscalSummary && (
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {[
                ['Ventas', fiscalSummary.sales_count],
                ['Total vendido', `$${fiscalSummary.total_sales_amount.toLocaleString('es-AR')}`],
                ['Facturas', fiscalSummary.invoices_count],
                ['Autorizadas', fiscalSummary.authorized_invoices_count],
                ['Pendientes', fiscalSummary.pending_invoices_count],
                ['Rechazadas', fiscalSummary.rejected_invoices_count],
                ['Ventas sin factura', fiscalSummary.sales_without_invoice_count],
                ['Total autorizado', `$${fiscalSummary.total_authorized_amount.toLocaleString('es-AR')}`],
                ['Total pendiente', `$${fiscalSummary.total_pending_amount.toLocaleString('es-AR')}`],
                ['Total rechazado', `$${fiscalSummary.total_rejected_amount.toLocaleString('es-AR')}`],
              ].map(([label, value]) => (
                <Card
                  key={String(label)}
                  className="bg-[#1a1a1a] border-[#3a3a3a]"
                >
                  <CardContent className="pt-5">
                    <p className="text-xs text-[#a0a0a0]">{label}</p>
                    <p className="text-xl text-[#f5f5dc]">{value}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {validation && validation.issues.length > 0 && (
            <Card className="bg-[#1a1a1a] border-[#3a3a3a]">
              <CardHeader>
                <CardTitle className="text-orange-300">
                  Inconsistencias detectadas
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {validation.issues.map((issue, index) => (
                  <div
                    key={`${issue.issue_type}-${issue.invoice_id}-${index}`}
                    className="rounded-md border border-[#3a3a3a] p-3"
                  >
                    <div className="flex flex-wrap justify-between gap-2">
                      <p className="font-semibold text-[#f5f5dc]">
                        {issue.issue_type}
                      </p>
                      <span className={
                        issue.severity === 'BLOCKING'
                          ? 'text-red-400'
                          : 'text-yellow-400'
                      }>
                        {issue.severity}
                      </span>
                    </div>
                    <p className="text-sm text-[#d0d0d0]">
                      {issue.description}
                    </p>
                    <p className="text-xs text-[#a0a0a0] mt-1">
                      Venta: {issue.sale_id ?? '-'} · Factura:{' '}
                      {issue.invoice_id ?? '-'}
                    </p>
                    <p className="text-xs text-[#D4AF37] mt-1">
                      Acción sugerida: {issue.suggested_action}
                    </p>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {invoices.map(invoice => (
            <Card key={invoice.id} className="bg-[#1a1a1a] border-[#3a3a3a]">
              <CardContent className="pt-6 flex justify-between items-center">
                <div>
                  <p className="text-[#f5f5dc]">{invoice.display_number}</p>
                  <p className="text-sm text-[#D4AF37]">
                    {invoice.declaration_type === 'ticket'
                      ? 'Ticket individual'
                      : 'Factura histórica'}
                  </p>
                  <p className="text-xs text-[#a0a0a0]">
                    {invoice.sales_count} venta(s) ·{' '}
                    ${invoice.total.toLocaleString('es-AR')}
                  </p>
                  <p className={
                    invoice.status === 'INVOICE_AUTHORIZED'
                      ? 'text-green-500'
                      : invoice.status === 'INVOICE_REJECTED'
                        ? 'text-red-400'
                        : 'text-orange-400'
                  }>
                    {invoice.status}
                  </p>
                  {invoice.authorization_code && (
                    <p className="text-xs text-green-400">
                      CAE: {invoice.authorization_code}
                    </p>
                  )}
                  {invoice.rejection_reason && (
                    <p className="text-xs text-red-400">
                      {invoice.rejection_reason}
                    </p>
                  )}
                </div>
                {[
                  'INVOICE_PENDING',
                  'INVOICE_REJECTED',
                  'INVOICE_RETRY_PENDING',
                ].includes(invoice.status) && (
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
