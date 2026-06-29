import { useEffect, useState } from 'react';
import {
  Banknote,
  CreditCard,
  FileText,
  Loader2,
  Printer,
  Smartphone,
  Trash2,
} from 'lucide-react';
import { toast } from 'sonner';
import { useComprobanteAfip } from '../hooks/useComprobanteAfip';

import type { ProductType } from '../services/productsApi';
import type {
  CloseTableResponse,
  PaymentMethod,
} from '../services/tablesApi';
import { issueClosingTicket } from '../services/tablesApi';
import { Button } from './ui/button';
import { Checkbox } from './ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import { Input } from './ui/input';
import { Label } from './ui/label';


interface Mesa {
  id: string;
  numero: number;
  nombrePersonalizado?: string;
  estado: 'libre' | 'ocupada' | 'reservada';
  personas: number;
  horaInicio?: string;
  consumo: number;
  detalleConsumo?: DetalleConsumo[];
}

interface DetalleConsumo {
  itemId: string;
  productId: string;
  nombre: string;
  tipo: ProductType;
  cantidad: number;
  precioUnitario: number;
  subtotal: number;
}

export interface MetodoPago {
  tipo: PaymentMethod;
  monto: number;
}

interface MetodoPagoForm {
  tipo: PaymentMethod;
  monto: string;
}

interface PreCierreMesaProps {
  mesa: Mesa | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRemoveItem: (
    tableNumber: number,
    itemId: number,
    quantity: number
  ) => Promise<void>;
  onConfirmarCierre?: (
    tableNumber: number,
    metodosPago: MetodoPago[]
  ) => Promise<CloseTableResponse>;
}

export function calculateCashDiscount(subtotal: number): number {
  return Math.round(subtotal * 0.1);
}

export function splitPaymentTotal(total: number): [number, number] {
  const first = Math.floor(total / 2);
  return [first, total - first];
}

export function isEditablePaymentAmount(value: string): boolean {
  return value === '' || /^\d+$/.test(value);
}

export function PreCierreMesa({
  mesa,
  open,
  onOpenChange,
  onRemoveItem,
  onConfirmarCierre,
}: PreCierreMesaProps) {
  const [detalles, setDetalles] = useState<DetalleConsumo[]>([]);
  const [metodosPago, setMetodosPago] = useState<MetodoPagoForm[]>([]);
  const [mostrarConfirmacion, setMostrarConfirmacion] = useState(false);
  const [cierreCompletado, setCierreCompletado] =
    useState<CloseTableResponse | null>(null);
  const [itemEliminando, setItemEliminando] = useState<string | null>(null);
  const [cerrando, setCerrando] = useState(false);
  const [issuingTicket, setIssuingTicket] = useState(false);

  const { polling: pollingAfip, timedOut: afipTimedOut, descargar: descargarAfip, reintentar: reintentarAfip, stopPolling: stopAfip } = useComprobanteAfip();

  useEffect(() => {
    if (!open) return;
    setDetalles(mesa?.detalleConsumo ?? []);
    setMetodosPago([]);
    setMostrarConfirmacion(false);
    setCierreCompletado(null);
    setItemEliminando(null);
  }, [mesa?.id, open]);

  if (!mesa) return null;

  const calcularSubtotal = () =>
    detalles.reduce((sum, item) => sum + item.subtotal, 0);

  const calcularDescuento = () => {
    const tieneEfectivo = metodosPago.some(
      metodo => metodo.tipo === 'efectivo'
    );
    return tieneEfectivo ? calculateCashDiscount(calcularSubtotal()) : 0;
  };

  const calcularTotal = () => calcularSubtotal() - calcularDescuento();

  const montoNumerico = (value: string) => {
    const amount = Number(value);
    return Number.isFinite(amount) ? Math.round(amount) : 0;
  };

  const totalPagado = () =>
    metodosPago.reduce(
      (sum, metodo) => sum + montoNumerico(metodo.monto),
      0,
    );

  const toggleMetodoPago = (tipo: PaymentMethod) => {
    const existe = metodosPago.some(metodo => metodo.tipo === tipo);
    if (existe) {
      const restantes = metodosPago.filter(metodo => metodo.tipo !== tipo);
      if (restantes.length === 1) {
        const subtotal = calcularSubtotal();
        const total = subtotal - (
          restantes[0].tipo === 'efectivo'
            ? calculateCashDiscount(subtotal)
            : 0
        );
        setMetodosPago([{ ...restantes[0], monto: String(total) }]);
      } else {
        setMetodosPago(restantes);
      }
      return;
    }

    if (metodosPago.length >= 2) {
      toast.error('Máximo 2 métodos de pago');
      return;
    }

    const subtotal = calcularSubtotal();
    const tieneEfectivo = tipo === 'efectivo'
      || metodosPago.some(metodo => metodo.tipo === 'efectivo');
    const total = subtotal - (
      tieneEfectivo ? calculateCashDiscount(subtotal) : 0
    );

    if (metodosPago.length === 0) {
      setMetodosPago([{ tipo, monto: String(total) }]);
      return;
    }

    const [primerMonto, segundoMonto] = splitPaymentTotal(total);
    setMetodosPago([
      { ...metodosPago[0], monto: String(primerMonto) },
      { tipo, monto: String(segundoMonto) },
    ]);
  };

  const actualizarMontoMetodo = (tipo: PaymentMethod, monto: string) => {
    if (!isEditablePaymentAmount(monto)) return;
    setMetodosPago(actuales => actuales.map(metodo =>
      metodo.tipo === tipo ? { ...metodo, monto } : metodo
    ));
  };

  const eliminarItem = async (item: DetalleConsumo) => {
    setItemEliminando(item.itemId);
    try {
      await onRemoveItem(mesa.numero, Number(item.itemId), item.cantidad);
      setDetalles(actuales => {
        const siguientes = actuales.filter(
          detalle => detalle.itemId !== item.itemId
        );
        if (siguientes.length === 0) setMetodosPago([]);
        return siguientes;
      });
      toast.success('Producto eliminado del consumo y stock restaurado');
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : 'No se pudo quitar el producto'
      );
    } finally {
      setItemEliminando(null);
    }
  };

  const imprimirTicket = () => {
    window.print();
  };

  const handleDescargarAfip = async () => {
    if (!cierreCompletado) return;
    let invoiceId = cierreCompletado.closing.invoice?.id;
    if (!invoiceId) {
      setIssuingTicket(true);
      try {
        const invoice = await issueClosingTicket(cierreCompletado.closing.id);
        setCierreCompletado(actual => actual
          ? { ...actual, closing: { ...actual.closing, invoice } }
          : actual);
        invoiceId = invoice.id;
      } catch (error) {
        toast.error(
          error instanceof Error ? error.message : 'No se pudo emitir el comprobante fiscal'
        );
        return;
      } finally {
        setIssuingTicket(false);
      }
    }
    descargarAfip(invoiceId);
  };

  const handleConfirmarCierre = () => {
    const total = calcularTotal();
    if (total > 0 && metodosPago.length === 0) {
      toast.error('Debe seleccionar al menos un método de pago');
      return;
    }
    if (metodosPago.some(metodo => montoNumerico(metodo.monto) <= 0)) {
      toast.error('Cada método seleccionado debe tener un monto mayor a cero');
      return;
    }
    if (totalPagado() < total) {
      toast.error('Los montos ingresados no alcanzan a cubrir el total');
      return;
    }
    setMostrarConfirmacion(true);
  };

  const confirmarCierreFinal = async () => {
    if (!onConfirmarCierre) return;
    setCerrando(true);
    try {
      const response = await onConfirmarCierre(
        mesa.numero,
        metodosPago.map(metodo => ({
          tipo: metodo.tipo,
          monto: montoNumerico(metodo.monto),
        })),
      );
      setCierreCompletado(response);
      setMostrarConfirmacion(false);
      if (response.warning) {
        toast.warning(response.warning);
      } else {
        toast.success('Mesa cerrada correctamente');
      }
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : 'No se pudo cerrar la mesa'
      );
    } finally {
      setCerrando(false);
    }
  };

  const cerrarResultado = () => { stopAfip(); onOpenChange(false); };

  const metodosDisponibles = [
    {
      tipo: 'efectivo' as const,
      label: 'Efectivo',
      icon: Banknote,
      color: 'text-green-500',
    },
    {
      tipo: 'tarjeta_credito' as const,
      label: 'Tarjeta Crédito',
      icon: CreditCard,
      color: 'text-blue-500',
    },
    {
      tipo: 'tarjeta_debito' as const,
      label: 'Tarjeta Débito',
      icon: CreditCard,
      color: 'text-purple-500',
    },
    {
      tipo: 'mercado_pago' as const,
      label: 'Mercado Pago',
      icon: Smartphone,
      color: 'text-cyan-500',
    },
  ];

  if (cierreCompletado) {
    const closing = cierreCompletado.closing;
    return (
      <Dialog open={open} onOpenChange={cerrarResultado}>
        <DialogContent className="bg-[#1a1a1a] border-[#3a3a3a] max-w-md">
          <DialogHeader>
            <DialogTitle className="text-[#D4AF37]">Mesa cerrada</DialogTitle>
            <DialogDescription className="text-[#a0a0a0]">
              La venta quedó registrada.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="p-4 bg-[#2a2a2a] rounded-lg border border-[#3a3a3a] space-y-2">
              <div className="flex justify-between text-[#f5f5dc]">
                <span>Total</span>
                <strong>${closing.total.toLocaleString('es-AR')}</strong>
              </div>
              <div className="flex justify-between text-[#a0a0a0]">
                <span>Recibido</span>
                <span>${closing.amount_received.toLocaleString('es-AR')}</span>
              </div>
              <div className="flex justify-between text-green-400">
                <span>Vuelto</span>
                <span>${closing.change.toLocaleString('es-AR')}</span>
              </div>
              {closing.invoice && (
                <p className="pt-2 text-sm text-[#D4AF37] border-t border-[#3a3a3a]">
                  Factura {closing.invoice.display_number}: {closing.invoice.status}
                </p>
              )}
              {cierreCompletado.warning && (
                <p className="pt-2 text-sm text-orange-400">
                  {cierreCompletado.warning}
                </p>
              )}
            </div>

            <Button
              onClick={cerrarResultado}
              variant="outline"
              className="w-full border-[#3a3a3a] text-[#f5f5dc] hover:bg-[#3a3a3a]"
            >
              Cerrar
            </Button>

            <div className="space-y-2">
              {afipTimedOut ? (
                <>
                  <p className="text-xs text-orange-400 text-center">
                    El comprobante está demorando más de lo normal. Reintentá en unos segundos.
                  </p>
                  <Button
                    onClick={() => void handleDescargarAfip()}
                    variant="outline"
                    className="w-full border-[#D4AF37] text-[#D4AF37] hover:bg-[#D4AF37]/10"
                  >
                    <FileText className="w-4 h-4 mr-2" />
                    Reintentar comprobante AFIP
                  </Button>
                </>
              ) : (
                <Button
                  onClick={() => void handleDescargarAfip()}
                  disabled={issuingTicket || pollingAfip}
                  className="w-full bg-[#0d2d0d] hover:bg-[#113511] border border-[#2a6a2a] text-green-400 disabled:opacity-60"
                >
                  {issuingTicket ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Emitiendo comprobante...
                    </>
                  ) : pollingAfip ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Generando comprobante...
                    </>
                  ) : (
                    <>
                      <FileText className="w-4 h-4 mr-2" />
                      {closing.invoice ? 'Ver comprobante AFIP' : 'Generar comprobante AFIP'}
                    </>
                  )}
                </Button>
              )}
            </div>
          </div>

        </DialogContent>
      </Dialog>
    );
  }

  if (mostrarConfirmacion) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="bg-[#1a1a1a] border-[#3a3a3a] max-w-md">
          <DialogHeader>
            <DialogTitle className="text-[#D4AF37]">
              Confirmar Cierre de Mesa
            </DialogTitle>
            <DialogDescription className="text-[#a0a0a0]">
              ¿Está seguro que desea cerrar esta mesa?
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="p-4 bg-[#2a2a2a] rounded-lg border border-[#3a3a3a]">
              <p className="text-[#f5f5dc] font-semibold text-lg text-center">
                Total: ${calcularTotal().toLocaleString('es-AR')}
              </p>
              <div className="mt-2 text-sm text-[#a0a0a0]">
                {metodosPago.map(metodo => (
                  <div key={metodo.tipo} className="flex justify-between">
                    <span>{metodo.tipo.replaceAll('_', ' ').toUpperCase()}</span>
                    <span>
                      ${montoNumerico(metodo.monto).toLocaleString('es-AR')}
                    </span>
                  </div>
                ))}
                {totalPagado() > calcularTotal() && (
                  <div className="flex justify-between text-green-400 mt-2">
                    <span>Vuelto</span>
                    <span>
                      ${(totalPagado() - calcularTotal()).toLocaleString('es-AR')}
                    </span>
                  </div>
                )}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Button
                onClick={() => setMostrarConfirmacion(false)}
                variant="outline"
                className="border-[#3a3a3a] text-[#f5f5dc] hover:bg-[#3a3a3a]"
              >
                Cancelar
              </Button>
              <Button
                onClick={() => void confirmarCierreFinal()}
                disabled={cerrando}
                className="bg-[#D4AF37] hover:bg-[#B8860B] text-[#0a0a0a]"
              >
                {cerrando ? 'Cerrando...' : 'Confirmar Cierre'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <>
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-[#1a1a1a] border-[#3a3a3a] max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-[#D4AF37]">
            Pre-Cierre: {mesa.nombrePersonalizado || `Mesa ${mesa.numero}`}
          </DialogTitle>
          <DialogDescription className="text-[#a0a0a0]">
            Verifique los detalles y seleccione el método de pago
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          <div className="grid grid-cols-3 gap-4 p-4 bg-[#2a2a2a] rounded-lg border border-[#3a3a3a]">
            <div>
              <p className="text-xs text-[#a0a0a0]">Mesa</p>
              <p className="text-[#f5f5dc] font-semibold">
                {mesa.nombrePersonalizado || `Mesa ${mesa.numero}`}
              </p>
            </div>
            <div>
              <p className="text-xs text-[#a0a0a0]">Personas</p>
              <p className="text-[#f5f5dc] font-semibold">{mesa.personas}</p>
            </div>
            <div>
              <p className="text-xs text-[#a0a0a0]">Hora Inicio</p>
              <p className="text-[#f5f5dc] font-semibold">
                {mesa.horaInicio
                  ? new Date(mesa.horaInicio).toLocaleTimeString('es-AR')
                  : '-'}
              </p>
            </div>
          </div>

          <div>
            <h3 className="text-[#D4AF37] mb-3">Detalle de Consumo</h3>
            <div className="space-y-2">
              {detalles.length === 0 && (
                <div className="p-4 text-center bg-[#2a2a2a] rounded-lg border border-[#3a3a3a] text-[#a0a0a0]">
                  La mesa no tiene consumos. Puede cerrarse con total $0.
                </div>
              )}
              {detalles.map(item => (
                <div
                  key={item.itemId}
                  className="p-3 bg-[#2a2a2a] rounded-lg border border-[#3a3a3a]"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <p className="text-[#f5f5dc] font-medium">{item.nombre}</p>
                      <p className="text-sm text-[#a0a0a0]">
                        Cantidad: {item.cantidad} x $
                        {item.precioUnitario.toLocaleString('es-AR')}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      <p className="text-[#D4AF37] font-semibold">
                        ${item.subtotal.toLocaleString('es-AR')}
                      </p>
                      <Button
                        onClick={() => void eliminarItem(item)}
                        disabled={itemEliminando === item.itemId}
                        size="sm"
                        variant="ghost"
                        className="text-red-500 hover:bg-[#3a3a3a]"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {calcularTotal() > 0 && (
            <div>
              <h3 className="text-[#D4AF37] mb-3">Método de Pago</h3>
              <div className="grid grid-cols-2 gap-3 mb-4">
                {metodosDisponibles.map(metodo => {
                  const Icon = metodo.icon;
                  const seleccionado = metodosPago.some(
                    item => item.tipo === metodo.tipo
                  );
                  return (
                    <button
                      type="button"
                      key={metodo.tipo}
                      onClick={() => toggleMetodoPago(metodo.tipo)}
                      className={`p-3 rounded-lg border-2 cursor-pointer transition-colors text-left ${
                        seleccionado
                          ? 'border-[#D4AF37] bg-[#2a2a2a]'
                          : 'border-[#3a3a3a] bg-[#1a1a1a] hover:border-[#D4AF37] hover:bg-[#242424]'
                      }`}
                    >
                      <span className="flex items-center gap-2">
                        <Checkbox checked={seleccionado} />
                        <Icon className={`w-5 h-5 ${metodo.color}`} />
                        <span className="text-[#f5f5dc]">{metodo.label}</span>
                      </span>
                    </button>
                  );
                })}
              </div>

              {metodosPago.length > 0 && (
                <div className="space-y-3 p-4 bg-[#2a2a2a] rounded-lg border border-[#3a3a3a]">
                  {metodosPago.map(metodo => (
                    <div key={metodo.tipo}>
                      <Label className="text-[#f5f5dc]">
                        Monto - {metodo.tipo.replaceAll('_', ' ').toUpperCase()}
                      </Label>
                      <Input
                        type="text"
                        inputMode="numeric"
                        value={metodo.monto}
                        onChange={event =>
                          actualizarMontoMetodo(metodo.tipo, event.target.value)
                        }
                        className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="p-4 bg-[#2a2a2a] rounded-lg border-2 border-[#D4AF37]">
            <div className="space-y-2">
              <div className="flex justify-between text-[#f5f5dc]">
                <span>Subtotal:</span>
                <span>${calcularSubtotal().toLocaleString('es-AR')}</span>
              </div>
              {calcularDescuento() > 0 && (
                <div className="flex justify-between text-green-500">
                  <span>Descuento (10% efectivo):</span>
                  <span>
                    -${calcularDescuento().toLocaleString('es-AR')}
                  </span>
                </div>
              )}
              <div className="flex justify-between text-[#D4AF37] text-xl font-bold pt-2 border-t border-[#3a3a3a]">
                <span>TOTAL:</span>
                <span>${calcularTotal().toLocaleString('es-AR')}</span>
              </div>
              {totalPagado() > calcularTotal() && (
                <div className="flex justify-between text-green-400">
                  <span>Vuelto:</span>
                  <span>
                    ${(totalPagado() - calcularTotal()).toLocaleString('es-AR')}
                  </span>
                </div>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Button
              onClick={imprimirTicket}
              variant="outline"
              className="border-[#3a3a3a] text-[#f5f5dc] hover:bg-[#3a3a3a]"
            >
              <Printer className="w-4 h-4 mr-2" />
              Imprimir resumen
            </Button>
            <Button
              onClick={handleConfirmarCierre}
              disabled={!onConfirmarCierre}
              className="bg-[#D4AF37] hover:bg-[#B8860B] text-[#0a0a0a]"
            >
              Continuar al Cierre
            </Button>
          </div>
        </div>

      </DialogContent>
    </Dialog>

    <div className="print-ticket">
      <h1>BEJAS - CERVECERÍA</h1>
      <p>{mesa.nombrePersonalizado || `Mesa ${mesa.numero}`}</p>
      <p>{new Date().toLocaleString('es-AR')}</p>
      <hr />
      <h2>Detalle</h2>
      {detalles.length === 0 ? (
        <p>Sin consumos</p>
      ) : detalles.map(item => (
        <div key={item.itemId} className="ticket-row">
          <span className="ticket-row-name">
            {item.nombre} ({item.cantidad}x)
          </span>
          <span className="ticket-row-price">
            ${item.subtotal.toLocaleString('es-AR')}
          </span>
        </div>
      ))}
      <hr />
      <div className="ticket-row">
        <span>Subtotal</span>
        <span>${calcularSubtotal().toLocaleString('es-AR')}</span>
      </div>
      {calcularDescuento() > 0 && (
        <div className="ticket-row">
          <span>Descuento efectivo 10%</span>
          <span>-${calcularDescuento().toLocaleString('es-AR')}</span>
        </div>
      )}
      <div className="ticket-row" style={{ fontWeight: 'bold' }}>
        <span>TOTAL</span>
        <span>${calcularTotal().toLocaleString('es-AR')}</span>
      </div>
      {metodosPago.length > 0 && <hr />}
      {metodosPago.map(metodo => (
        <div key={metodo.tipo} className="ticket-row">
          <span>{metodo.tipo.replaceAll('_', ' ').toUpperCase()}</span>
          <span>${montoNumerico(metodo.monto).toLocaleString('es-AR')}</span>
        </div>
      ))}
      {totalPagado() > calcularTotal() && (
        <div className="ticket-row">
          <span>Vuelto</span>
          <span>${(totalPagado() - calcularTotal()).toLocaleString('es-AR')}</span>
        </div>
      )}
      <hr />
      <p style={{ textAlign: 'center' }}>Gracias por su visita</p>
    </div>
    </>
  );
}
