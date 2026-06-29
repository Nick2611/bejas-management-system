import { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from './ui/dialog';
import {
  Plus,
  Users,
  DollarSign,
  Clock,
  Minus,
  Edit,
  CheckCircle2,
  Trash2,
  LayoutGrid,
} from 'lucide-react';
import { toast } from 'sonner';
import { PreCierreMesa } from './PreCierreMesa';
import { useAuth } from '../context/AuthContext';
import { fetchProducts, type ProductType } from '../services/productsApi';
import {
  addTableProducts,
  closeTable,
  createTable,
  deleteTable,
  fetchTable,
  fetchTables,
  occupyTable,
  removeTablePeople,
  removeTableProduct,
  updateTable,
  type Table,
} from '../services/tablesApi';

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

interface MenuItem {
  id: string;
  nombre: string;
  precio: number;
  tipo: ProductType;
  disponible: number;
}

interface ItemPedido {
  itemId: string;
  cantidad: number;
}

const MESAS_PREDETERMINADAS = [
  { table_number: 1, table_name: 'Barra Individual' },
  { table_number: 2, table_name: 'Mesa Interna 1' },
  { table_number: 3, table_name: 'Mesa Interna 2' },
  { table_number: 4, table_name: 'Mesa Externa 1' },
  { table_number: 5, table_name: 'Mesa Externa 2' },
  { table_number: 6, table_name: 'Mesa Externa 3' },
];

type GroupKey = 'barra' | 'interna' | 'externa' | 'otra';

const GROUP_LABELS: Record<GroupKey, string> = {
  barra: 'Barra',
  interna: 'Mesas Internas',
  externa: 'Mesas Externas',
  otra: 'Otras Mesas',
};

function getMesaGroup(mesa: Mesa): GroupKey {
  const name = (mesa.nombrePersonalizado ?? '').toLowerCase();
  if (name.includes('barra')) return 'barra';
  if (name.includes('interna')) return 'interna';
  if (name.includes('externa')) return 'externa';
  return 'otra';
}

export function normalizeOrderQuantity(value: string, available: number): number {
  if (value.trim() === '') return 0;
  const quantity = Number(value);
  if (!Number.isFinite(quantity) || quantity <= 0) return 0;
  return Math.min(Math.trunc(quantity), Math.max(available, 0));
}

function mapTable(table: Table, menuItems: MenuItem[]): Mesa {
  const detalleConsumo = table.items.map((item): DetalleConsumo => {
    const producto = menuItems.find(m => Number(m.id) === item.product_id);
    return {
      itemId: String(item.id),
      productId: String(item.product_id),
      nombre: producto?.nombre ?? `Producto #${item.product_id}`,
      tipo: producto?.tipo ?? 'comida',
      cantidad: item.quantity,
      precioUnitario: item.curr_price,
      subtotal: item.quantity * item.curr_price,
    };
  });
  return {
    id: String(table.id),
    numero: table.table_number,
    nombrePersonalizado: table.table_name ?? undefined,
    estado: table.people > 0 || table.items.length > 0 ? 'ocupada' : 'libre',
    personas: table.people,
    horaInicio: table.opening_time,
    consumo: detalleConsumo.reduce((t, i) => t + i.subtotal, 0),
    detalleConsumo,
  };
}

const PRODUCT_SECTIONS: { tipo: ProductType; label: string }[] = [
  { tipo: 'cerveza', label: 'Cervezas' },
  { tipo: 'comida', label: 'Comidas' },
  { tipo: 'trago', label: 'Tragos' },
  { tipo: 'bebida', label: 'Bebidas sin Alcohol' },
];

export function Mesas() {
  const { isAdmin } = useAuth();
  const [mesas, setMesas] = useState<Mesa[]>([]);
  const [nuevaMesa, setNuevaMesa] = useState({ numero: '', nombre: '' });
  const [selectedMesaId, setSelectedMesaId] = useState('');
  const [editingMesa, setEditingMesa] = useState<Mesa | null>(null);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [pedido, setPedido] = useState<ItemPedido[]>([]);
  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [consumoDialogOpen, setConsumoDialogOpen] = useState(false);
  const [preCierreDialogOpen, setPreCierreDialogOpen] = useState(false);
  const [mesaParaCierre, setMesaParaCierre] = useState<Mesa | null>(null);
  const [ocuparDialogOpen, setOcuparDialogOpen] = useState(false);
  const [mesaParaOcupar, setMesaParaOcupar] = useState<Mesa | null>(null);
  const [personasOcupar, setPersonasOcupar] = useState('2');
  const [quitarPersonasDialogOpen, setQuitarPersonasDialogOpen] = useState(false);
  const [mesaParaQuitarPersonas, setMesaParaQuitarPersonas] = useState<Mesa | null>(null);
  const [personasAQuitar, setPersonasAQuitar] = useState('1');
  const [procesandoMesa, setProcesandoMesa] = useState(false);

  useEffect(() => { void cargarDatos(); }, []);

  const cargarDatos = async () => {
    try {
      const [productosDb, mesasDb] = await Promise.all([fetchProducts(), fetchTables()]);

      // Auto-create any missing default tables on first load
      const existentes = new Set(mesasDb.map(m => m.table_number));
      const toCreate = MESAS_PREDETERMINADAS.filter(m => !existentes.has(m.table_number));
      let mesasFinales = mesasDb;
      if (toCreate.length > 0) {
        await Promise.all(
          toCreate.map(m => createTable({ table_number: m.table_number, table_name: m.table_name, people: 0 }))
        );
        mesasFinales = await fetchTables();
      }

      const menu = productosDb.map((p): MenuItem => ({
        id: String(p.id),
        nombre: p.name,
        precio: p.price,
        tipo: p.type,
        disponible: p.qty,
      }));
      setMenuItems(menu);
      setMesas(mesasFinales.map(m => mapTable(m, menu)));
    } catch (error) {
      setMesas([]);
      setMenuItems([]);
      toast.error(error instanceof Error ? error.message : 'No se pudieron cargar las mesas');
    }
  };

  const cargarMenu = async () => {
    const productosDb = await fetchProducts();
    const menu = productosDb.map((p): MenuItem => ({
      id: String(p.id),
      nombre: p.name,
      precio: p.price,
      tipo: p.type,
      disponible: p.qty,
    }));
    setMenuItems(menu);
    return menu;
  };

  const recargarMesa = async (tableNumber: number) => {
    const [mesaDb, menu] = await Promise.all([fetchTable(tableNumber), cargarMenu()]);
    const mesaActualizada = mapTable(mesaDb, menu);
    setMesas(prev => prev.map(m => m.numero === tableNumber ? mesaActualizada : m));
    setMesaParaCierre(prev => prev?.numero === tableNumber ? mesaActualizada : prev);
    return mesaActualizada;
  };

  const crearMesa = async () => {
    const numero = Number(nuevaMesa.numero);
    if (mesas.find(m => m.numero === numero)) {
      toast.error('Ya existe una mesa con ese número');
      return;
    }
    if (!Number.isInteger(numero) || numero <= 0) {
      toast.error('El número de mesa debe ser un entero mayor a 0');
      return;
    }
    setProcesandoMesa(true);
    try {
      await createTable({ table_number: numero, table_name: nuevaMesa.nombre.trim() || null, people: 0 });
      await cargarDatos();
      setDialogOpen(false);
      setNuevaMesa({ numero: '', nombre: '' });
      toast.success('Mesa creada exitosamente');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo crear la mesa');
    } finally {
      setProcesandoMesa(false);
    }
  };

  const inicializarPredeterminadas = async () => {
    const existentes = new Set(mesas.map(m => m.numero));
    const toCreate = MESAS_PREDETERMINADAS.filter(m => !existentes.has(m.table_number));
    if (toCreate.length === 0) {
      toast.info('Las mesas predeterminadas ya están creadas');
      return;
    }
    setProcesandoMesa(true);
    try {
      await Promise.all(
        toCreate.map(m => createTable({ table_number: m.table_number, table_name: m.table_name, people: 0 }))
      );
      await cargarDatos();
      toast.success(`${toCreate.length} mesa${toCreate.length !== 1 ? 's' : ''} creada${toCreate.length !== 1 ? 's' : ''}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudieron crear las mesas');
    } finally {
      setProcesandoMesa(false);
    }
  };

  const eliminarMesa = async (mesa: Mesa) => {
    setProcesandoMesa(true);
    try {
      await deleteTable(mesa.numero);
      await cargarDatos();
      toast.success(`Mesa ${mesa.numero} eliminada`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo eliminar la mesa');
    } finally {
      setProcesandoMesa(false);
    }
  };

  const editarMesa = (mesa: Mesa) => {
    setEditingMesa({ ...mesa });
    setEditDialogOpen(true);
  };

  const guardarEdicionMesa = async () => {
    if (!editingMesa) return;
    setProcesandoMesa(true);
    try {
      await updateTable(editingMesa.numero, { table_name: editingMesa.nombrePersonalizado?.trim() || null });
      await recargarMesa(editingMesa.numero);
      setEditDialogOpen(false);
      toast.success('Mesa actualizada');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo actualizar la mesa');
    } finally {
      setProcesandoMesa(false);
    }
  };

  const abrirOcuparMesa = (id: string) => {
    const mesa = mesas.find(m => m.id === id);
    if (mesa) {
      setMesaParaOcupar(mesa);
      setPersonasOcupar(String(Math.max(1, mesa.personas || 2)));
      setOcuparDialogOpen(true);
    }
  };

  const ocuparMesa = async () => {
    if (!mesaParaOcupar) return;
    const personas = Number(personasOcupar);
    if (!Number.isInteger(personas) || personas <= 0) {
      toast.error('La cantidad de personas debe ser un entero mayor a 0');
      return;
    }
    setProcesandoMesa(true);
    try {
      await occupyTable(mesaParaOcupar.numero, personas);
      await recargarMesa(mesaParaOcupar.numero);
      setOcuparDialogOpen(false);
      setMesaParaOcupar(null);
      toast.success('Mesa ocupada');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo ocupar la mesa');
    } finally {
      setProcesandoMesa(false);
    }
  };

  const abrirQuitarPersonas = (mesa: Mesa) => {
    setMesaParaQuitarPersonas(mesa);
    setPersonasAQuitar('1');
    setQuitarPersonasDialogOpen(true);
  };

  const quitarPersonas = async () => {
    if (!mesaParaQuitarPersonas) return;
    const cantidad = Number(personasAQuitar);
    if (!Number.isInteger(cantidad) || cantidad <= 0 || cantidad > mesaParaQuitarPersonas.personas) {
      toast.error(`Ingresá una cantidad entre 1 y ${mesaParaQuitarPersonas.personas}`);
      return;
    }
    setProcesandoMesa(true);
    try {
      await removeTablePeople(mesaParaQuitarPersonas.numero, cantidad);
      await recargarMesa(mesaParaQuitarPersonas.numero);
      setQuitarPersonasDialogOpen(false);
      setMesaParaQuitarPersonas(null);
      toast.success(`${cantidad} persona(s) removida(s)`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudieron quitar personas');
    } finally {
      setProcesandoMesa(false);
    }
  };

  const abrirPreCierre = async (id: string) => {
    const mesa = mesas.find(m => m.id === id);
    if (!mesa) return;
    try {
      const mesaActualizada = await recargarMesa(mesa.numero);
      setMesaParaCierre(mesaActualizada);
      setPreCierreDialogOpen(true);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo cargar el detalle de la mesa');
    }
  };

  const quitarConsumo = async (tableNumber: number, itemId: number, quantity: number) => {
    await removeTableProduct(tableNumber, itemId, quantity);
    await recargarMesa(tableNumber);
  };

  const confirmarCierre = async (
    tableNumber: number,
    payments: Array<{ tipo: 'efectivo' | 'tarjeta_credito' | 'tarjeta_debito' | 'mercado_pago'; monto: number }>
  ) => {
    return closeTable(tableNumber, payments.map(p => ({ method: p.tipo, amount: Math.round(p.monto) })));
  };

  const actualizarCantidadItem = (itemId: string, value: string, available: number) => {
    const cantidad = normalizeOrderQuantity(value, available);
    setPedido(prev => {
      const existe = prev.some(i => i.itemId === itemId);
      if (cantidad === 0) return prev.filter(i => i.itemId !== itemId);
      if (existe) return prev.map(i => i.itemId === itemId ? { ...i, cantidad } : i);
      return [...prev, { itemId, cantidad }];
    });
  };

  const incrementarItem = (itemId: string, available: number) => {
    setPedido(prev => {
      const existe = prev.find(p => p.itemId === itemId);
      if (existe) {
        if (existe.cantidad >= available) return prev;
        return prev.map(p => p.itemId === itemId ? { ...p, cantidad: p.cantidad + 1 } : p);
      }
      return available > 0 ? [...prev, { itemId, cantidad: 1 }] : prev;
    });
  };

  const decrementarItem = (itemId: string) => {
    setPedido(prev => {
      const existe = prev.find(p => p.itemId === itemId);
      if (!existe) return prev;
      if (existe.cantidad === 1) return prev.filter(p => p.itemId !== itemId);
      return prev.map(p => p.itemId === itemId ? { ...p, cantidad: p.cantidad - 1 } : p);
    });
  };

  const calcularTotalPedido = () =>
    pedido.reduce((sum, item) => {
      const menuItem = menuItems.find(m => m.id === item.itemId);
      return sum + (menuItem?.precio ?? 0) * item.cantidad;
    }, 0);

  const mesasOrdenadas = [...mesas].sort((a, b) => a.numero - b.numero);

  const grupos = (['barra', 'interna', 'externa', 'otra'] as GroupKey[]).reduce<Partial<Record<GroupKey, Mesa[]>>>(
    (acc, key) => {
      const group = mesasOrdenadas.filter(m => getMesaGroup(m) === key);
      if (group.length > 0) acc[key] = group;
      return acc;
    },
    {}
  );

  const hayGruposNombrados = (['barra', 'interna', 'externa'] as GroupKey[]).some(k => k in grupos);

  const renderMesaCard = (mesa: Mesa) => (
    <div
      key={mesa.id}
      className={`rounded-2xl border-2 p-6 transition-all duration-200 ${
        mesa.estado === 'ocupada'
          ? 'bg-[#17130a] border-amber-500/35 shadow-[0_0_24px_rgba(245,158,11,0.06)]'
          : 'bg-[#111111] border-white/[0.08] hover:border-white/[0.14]'
      }`}
    >
      {/* Card header */}
      <div className="flex items-start justify-between mb-5">
        <div>
          <h3 className="font-semibold text-zinc-200 text-base">
            {mesa.nombrePersonalizado || `Mesa ${mesa.numero}`}
          </h3>
          <div className="mt-2">
            {mesa.estado === 'ocupada' ? (
              <span className="inline-flex items-center gap-1.5 text-sm font-medium text-amber-400">
                <span className="h-2 w-2 rounded-full bg-amber-400 animate-pulse" />
                Ocupada
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 text-sm font-medium text-emerald-400">
                <span className="h-2 w-2 rounded-full bg-emerald-400" />
                Disponible
              </span>
            )}
          </div>
        </div>
        <div className="flex gap-1">
          {isAdmin && (
            <button
              type="button"
              onClick={() => editarMesa(mesa)}
              className="rounded-lg p-2 text-zinc-600 hover:text-amber-400 hover:bg-amber-400/10 transition-all"
              title="Editar mesa"
            >
              <Edit className="h-4 w-4" />
            </button>
          )}
          {mesa.estado === 'libre' && (
            <button
              type="button"
              onClick={() => void eliminarMesa(mesa)}
              disabled={procesandoMesa}
              className="rounded-lg p-2 text-zinc-700 hover:text-red-400 hover:bg-red-950/30 transition-all disabled:opacity-40"
              title="Eliminar mesa"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* Ocupada: detalles */}
      {mesa.estado === 'ocupada' && (
        <div className="space-y-3 mb-5 p-4 rounded-xl bg-white/[0.03] border border-white/[0.05]">
          <div className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-2 text-zinc-500">
              <Users className="h-4 w-4" /> Personas
            </span>
            <div className="flex items-center gap-2">
              <span className="text-zinc-300 font-medium">{mesa.personas}</span>
              {mesa.personas > 0 && (
                <button
                  type="button"
                  onClick={() => abrirQuitarPersonas(mesa)}
                  className="text-red-400/70 hover:text-red-400 transition-colors text-xs"
                >
                  Quitar
                </button>
              )}
            </div>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-2 text-zinc-500">
              <Clock className="h-4 w-4" /> Desde
            </span>
            <span className="text-zinc-400 font-mono">
              {mesa.horaInicio
                ? new Date(mesa.horaInicio).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })
                : '-'}
            </span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-2 text-zinc-500">
              <DollarSign className="h-4 w-4" /> Total
            </span>
            <span className="font-semibold text-amber-400">${mesa.consumo.toLocaleString('es-AR')}</span>
          </div>
        </div>
      )}

      {/* Actions */}
      {mesa.estado === 'ocupada' ? (
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => { setSelectedMesaId(mesa.id); setPedido([]); setConsumoDialogOpen(true); }}
            className="flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl text-sm font-medium bg-white/[0.04] border border-white/[0.09] text-zinc-400 hover:text-zinc-200 hover:border-white/[0.16] transition-all"
          >
            <Plus className="h-4 w-4" /> Pedido
          </button>
          <button
            type="button"
            onClick={() => void abrirPreCierre(mesa.id)}
            className="flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl text-sm font-semibold bg-gradient-to-r from-amber-500 to-amber-600 text-[#0a0a0a] hover:from-amber-400 hover:to-amber-500 transition-all"
          >
            <CheckCircle2 className="h-4 w-4" /> Detalle
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => abrirOcuparMesa(mesa.id)}
          className="w-full flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-semibold bg-emerald-500/[0.12] border border-emerald-500/25 text-emerald-400 hover:bg-emerald-500/[0.18] hover:border-emerald-500/40 transition-all"
        >
          <Users className="h-4 w-4" /> Ocupar Mesa
        </button>
      )}
    </div>
  );

  const inputClass = 'bg-white/[0.04] border-white/10 text-zinc-200 placeholder:text-zinc-600 focus-visible:border-amber-400/50 focus-visible:ring-1 focus-visible:ring-amber-400/20';
  const labelClass = 'text-sm font-medium text-zinc-300';
  const dialogClass = 'bg-[#111111] border-white/10 text-white';
  const btnOutlineClass = 'border-white/10 text-zinc-300 hover:bg-white/[0.05] hover:text-zinc-100';
  const btnGoldClass = 'bg-gradient-to-r from-amber-500 to-amber-600 text-[#0a0a0a] font-semibold hover:from-amber-400 hover:to-amber-500';

  return (
    <div className="relative min-h-screen bg-[#080808] text-white">
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute top-0 right-1/4 h-96 w-96 rounded-full bg-amber-400/[0.03] blur-3xl" />
      </div>

      <div className="relative p-8 max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8 flex items-start justify-between gap-4 flex-wrap">
          <div>
            <p className="mb-2 text-[10px] font-semibold tracking-[0.26em] text-amber-400/80 uppercase">
              Gestión
            </p>
            <h1 className="text-3xl font-semibold tracking-tight text-white">Mesas</h1>
            <p className="mt-1 text-sm text-zinc-600">Control de mesas y pedidos</p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
              <DialogTrigger asChild>
                <button
                  type="button"
                  className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold bg-gradient-to-r from-amber-500 to-amber-600 text-[#0a0a0a] hover:from-amber-400 hover:to-amber-500 transition-all"
                >
                  <Plus className="h-4 w-4" /> Nueva Mesa
                </button>
              </DialogTrigger>
              <DialogContent className={dialogClass}>
                <DialogHeader>
                  <DialogTitle className="text-amber-400">Crear Nueva Mesa</DialogTitle>
                  <DialogDescription className="text-zinc-500">
                    Ingresá los datos de la nueva mesa
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 pt-2">
                  <div className="space-y-2">
                    <Label className={labelClass}>Número de Mesa</Label>
                    <Input
                      type="number"
                      value={nuevaMesa.numero}
                      onChange={e => setNuevaMesa({ ...nuevaMesa, numero: e.target.value })}
                      className={inputClass}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className={labelClass}>Nombre personalizado (opcional)</Label>
                    <Input
                      type="text"
                      placeholder="Ej: Mesa VIP, Terraza..."
                      value={nuevaMesa.nombre}
                      onChange={e => setNuevaMesa({ ...nuevaMesa, nombre: e.target.value })}
                      className={inputClass}
                    />
                  </div>
                  <Button onClick={crearMesa} disabled={procesandoMesa} className={`w-full ${btnGoldClass}`}>
                    {procesandoMesa ? 'Creando...' : 'Crear Mesa'}
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* Empty state */}
        {mesasOrdenadas.length === 0 && (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <p className="text-zinc-500 text-sm">Cargando mesas...</p>
          </div>
        )}

        {/* Tables grid — grouped */}
        {mesasOrdenadas.length > 0 && hayGruposNombrados ? (
          <div className="space-y-8">
            {(['barra', 'interna', 'externa', 'otra'] as GroupKey[]).map(key => {
              const group = grupos[key];
              if (!group) return null;
              return (
                <div key={key}>
                  <div className="flex items-center gap-3 mb-4">
                    <h2 className="text-xs font-semibold tracking-[0.18em] text-amber-400/70 uppercase">
                      {GROUP_LABELS[key]}
                    </h2>
                    <span className="text-xs text-zinc-600">{group.length} mesa{group.length !== 1 ? 's' : ''}</span>
                    <div className="flex-1 h-px bg-white/[0.05]" />
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                    {group.map(renderMesaCard)}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          mesasOrdenadas.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {mesasOrdenadas.map(renderMesaCard)}
            </div>
          )
        )}
      </div>

      {/* Dialog editar mesa */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className={dialogClass}>
          <DialogHeader>
            <DialogTitle className="text-amber-400">Editar Mesa</DialogTitle>
          </DialogHeader>
          {editingMesa && (
            <div className="space-y-4 pt-2">
              <div className="space-y-2">
                <Label className={labelClass}>Número de Mesa</Label>
                <Input type="number" value={editingMesa.numero} disabled className="bg-white/[0.02] border-white/[0.06] text-zinc-500" />
                <p className="text-xs text-zinc-600">El número no se puede modificar.</p>
              </div>
              <div className="space-y-2">
                <Label className={labelClass}>Nombre personalizado</Label>
                <Input
                  type="text"
                  placeholder="Ej: Mesa Interna, Mesa VIP..."
                  value={editingMesa.nombrePersonalizado || ''}
                  onChange={e => setEditingMesa({ ...editingMesa, nombrePersonalizado: e.target.value })}
                  className={inputClass}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Button onClick={() => setEditDialogOpen(false)} variant="outline" className={btnOutlineClass}>Cancelar</Button>
                <Button onClick={guardarEdicionMesa} disabled={procesandoMesa} className={btnGoldClass}>
                  {procesandoMesa ? 'Guardando...' : 'Guardar'}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Dialog consumo */}
      <Dialog
        open={consumoDialogOpen}
        onOpenChange={open => {
          setConsumoDialogOpen(open);
          if (open) void cargarMenu().catch(e => toast.error(e instanceof Error ? e.message : 'No se pudo cargar el menú'));
        }}
      >
        <DialogContent className={`${dialogClass} max-w-3xl max-h-[85vh] overflow-hidden flex flex-col`}>
          <DialogHeader>
            <DialogTitle className="text-amber-400">Agregar Pedido</DialogTitle>
            <DialogDescription className="text-zinc-500">Seleccioná los productos y cantidades</DialogDescription>
          </DialogHeader>

          <div className="overflow-y-auto flex-1 pr-1 space-y-5">
            {PRODUCT_SECTIONS.map(({ tipo, label }) => {
              const items = menuItems.filter(i => i.tipo === tipo);
              if (items.length === 0) return null;
              return (
                <div key={tipo}>
                  <h3 className="text-[11px] font-semibold tracking-[0.18em] text-amber-400/80 uppercase mb-3 sticky top-0 bg-[#111111] py-1 z-10">
                    {label}
                  </h3>
                  <div className="grid grid-cols-2 gap-2">
                    {items.map(item => {
                      const cantidad = pedido.find(p => p.itemId === item.id)?.cantidad ?? 0;
                      return (
                        <div key={item.id} className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.08]">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-sm font-medium text-zinc-200 truncate">{item.nombre}</span>
                            <span className="text-xs text-amber-400 shrink-0 ml-2">${(item.precio / 1000).toFixed(1)}k</span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <button
                              type="button"
                              onClick={() => decrementarItem(item.id)}
                              disabled={cantidad === 0}
                              className="h-7 w-7 rounded-lg border border-white/10 text-zinc-400 hover:border-white/20 hover:text-zinc-200 flex items-center justify-center transition-all disabled:opacity-30"
                            >
                              <Minus className="h-3 w-3" />
                            </button>
                            <Input
                              type="number"
                              min="0"
                              max={item.disponible}
                              step="1"
                              value={cantidad || ''}
                              placeholder="0"
                              aria-label={`Cantidad de ${item.nombre}`}
                              onFocus={e => e.currentTarget.select()}
                              onChange={e => actualizarCantidadItem(item.id, e.target.value, item.disponible)}
                              className="h-7 w-14 px-1 text-center text-sm bg-white/[0.04] border-white/10 text-zinc-200"
                            />
                            <button
                              type="button"
                              onClick={() => incrementarItem(item.id, item.disponible)}
                              disabled={cantidad >= item.disponible}
                              className="h-7 w-7 rounded-lg bg-amber-500/80 hover:bg-amber-400 text-[#0a0a0a] flex items-center justify-center transition-all disabled:opacity-30"
                            >
                              <Plus className="h-3 w-3" />
                            </button>
                          </div>
                          <p className="mt-1.5 text-[11px] text-zinc-600">Disponible: {item.disponible}</p>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="pt-4 border-t border-white/[0.08] space-y-3">
            {pedido.length > 0 && (
              <div className="flex items-center justify-between px-4 py-3 rounded-xl border-2 border-amber-500/30 bg-amber-400/[0.06]">
                <span className="text-sm font-medium text-zinc-300">Total del Pedido</span>
                <span className="text-xl font-bold text-amber-400">${calcularTotalPedido().toLocaleString('es-AR')}</span>
              </div>
            )}
            <Button
              onClick={agregarConsumo}
              disabled={procesandoMesa || pedido.length === 0}
              className={`w-full h-11 ${btnGoldClass}`}
            >
              {procesandoMesa ? 'Agregando...' : 'Confirmar Pedido'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Pre-cierre */}
      <PreCierreMesa
        mesa={mesaParaCierre}
        open={preCierreDialogOpen}
        onOpenChange={open => {
          setPreCierreDialogOpen(open);
          if (!open && mesaParaCierre) { void cargarDatos(); setMesaParaCierre(null); }
        }}
        onRemoveItem={quitarConsumo}
        onConfirmarCierre={confirmarCierre}
      />

      {/* Dialog ocupar */}
      <Dialog open={ocuparDialogOpen} onOpenChange={setOcuparDialogOpen}>
        <DialogContent className={`${dialogClass} max-w-sm`}>
          <DialogHeader>
            <DialogTitle className="text-amber-400">Ocupar Mesa</DialogTitle>
            <DialogDescription className="text-zinc-500">Ingresá el número de personas</DialogDescription>
          </DialogHeader>
          <div className="space-y-5 pt-2">
            <div className="space-y-2">
              <Label className={labelClass}>Número de personas</Label>
              <Input
                type="number"
                value={personasOcupar}
                onChange={e => setPersonasOcupar(e.target.value)}
                className={inputClass}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Button onClick={() => setOcuparDialogOpen(false)} variant="outline" className={btnOutlineClass}>Cancelar</Button>
              <Button onClick={() => void ocuparMesa()} disabled={procesandoMesa} className={btnGoldClass}>
                {procesandoMesa ? 'Guardando...' : 'Ocupar'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Dialog quitar personas */}
      <Dialog open={quitarPersonasDialogOpen} onOpenChange={setQuitarPersonasDialogOpen}>
        <DialogContent className={`${dialogClass} max-w-sm`}>
          <DialogHeader>
            <DialogTitle className="text-amber-400">Quitar personas</DialogTitle>
            <DialogDescription className="text-zinc-500">
              {mesaParaQuitarPersonas
                ? `${mesaParaQuitarPersonas.nombrePersonalizado || `Mesa ${mesaParaQuitarPersonas.numero}`} — ${mesaParaQuitarPersonas.personas} persona(s)`
                : 'Indicá cuántas personas querés quitar'}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-2">
            <div className="space-y-2">
              <Label className={labelClass}>Cantidad a quitar</Label>
              <Input
                type="number"
                min="1"
                max={mesaParaQuitarPersonas?.personas}
                step="1"
                value={personasAQuitar}
                onChange={e => setPersonasAQuitar(e.target.value)}
                className={inputClass}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Button onClick={() => setQuitarPersonasDialogOpen(false)} variant="outline" className={btnOutlineClass}>Cancelar</Button>
              <Button onClick={() => void quitarPersonas()} disabled={procesandoMesa} className="bg-red-600 hover:bg-red-500 text-white font-semibold">
                {procesandoMesa ? 'Quitando...' : 'Quitar'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );

  async function agregarConsumo() {
    const mesa = mesas.find(i => i.id === selectedMesaId);
    const total = calcularTotalPedido();
    if (!mesa || pedido.length === 0 || total === 0) {
      toast.error('Agrega al menos un ítem al pedido');
      return;
    }
    setProcesandoMesa(true);
    try {
      await addTableProducts(mesa.numero, pedido.map(i => ({ product_id: Number(i.itemId), quantity: i.cantidad })));
      await recargarMesa(mesa.numero);
      setPedido([]);
      setConsumoDialogOpen(false);
      toast.success(`Consumo agregado: $${total.toLocaleString('es-AR')}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo agregar el pedido');
    } finally {
      setProcesandoMesa(false);
    }
  }
}
