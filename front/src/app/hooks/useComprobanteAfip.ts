import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { getComprobantePdf, getInvoice } from '../services/businessApi';
import type { InvoiceStatus } from '../services/businessApi';

const POLL_INTERVAL_MS = 1500;
const MAX_ATTEMPTS = 20; // ~30 segundos

const PENDING_STATUSES = new Set<InvoiceStatus>([
  'INVOICE_PENDING',
  'INVOICE_QUEUED',
  'INVOICE_AUTHORIZING',
  'INVOICE_RETRY_PENDING',
]);

export function useComprobanteAfip() {
  const [polling, setPolling]         = useState(false);
  const [timedOut, setTimedOut]       = useState(false);
  const [downloadingId, setDownloadingId] = useState<number | null>(null);

  // refs para controlar el loop sin causar re-renders
  const activeRef  = useRef(false);
  const timerRef   = useRef<ReturnType<typeof setTimeout> | null>(null);

  const stopPolling = useCallback(() => {
    activeRef.current = false;
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    setPolling(false);
    setDownloadingId(null);
  }, []);

  // Limpieza al desmontar el componente que usa el hook
  useEffect(() => {
    return () => {
      activeRef.current = false;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const descargar = useCallback((invoiceId: number) => {
    if (polling) return;
    setPolling(true);
    setTimedOut(false);
    setDownloadingId(invoiceId);
    activeRef.current = true;
    let attempts = 0;

    const tick = async () => {
      if (!activeRef.current) return;
      attempts += 1;

      // Timeout después de MAX_ATTEMPTS intentos
      if (attempts > MAX_ATTEMPTS) {
        stopPolling();
        setTimedOut(true);
        return;
      }

      try {
        const invoice = await getInvoice(invoiceId);
        if (!activeRef.current) return;

        if (invoice.status === 'INVOICE_AUTHORIZED') {
          stopPolling();
          try {
            const blob = await getComprobantePdf(invoiceId);
            const url  = URL.createObjectURL(blob);
            window.open(url, '_blank');
            // Liberar la URL de objeto después de que el navegador la use
            setTimeout(() => URL.revokeObjectURL(url), 60_000);
          } catch {
            toast.error('No se pudo descargar el comprobante PDF');
          }
          return;
        }

        if (invoice.status === 'INVOICE_REJECTED') {
          stopPolling();
          toast.error(
            `Comprobante rechazado por AFIP: ${invoice.rejection_reason ?? 'Error desconocido'}`
          );
          return;
        }

        if (invoice.status === 'INVOICE_CANCELLED') {
          stopPolling();
          toast.error('El comprobante fue cancelado');
          return;
        }

        // Sigue pendiente — programar próximo intento
        if (activeRef.current && PENDING_STATUSES.has(invoice.status)) {
          timerRef.current = setTimeout(() => void tick(), POLL_INTERVAL_MS);
        }
      } catch {
        // Error de red transitorio — seguir intentando hasta el timeout
        if (activeRef.current) {
          timerRef.current = setTimeout(() => void tick(), POLL_INTERVAL_MS);
        }
      }
    };

    void tick();
  }, [polling, stopPolling]);

  const reintentar = useCallback(
    (invoiceId: number) => {
      setTimedOut(false);
      descargar(invoiceId);
    },
    [descargar],
  );

  return { polling, timedOut, downloadingId, descargar, reintentar, stopPolling };
}