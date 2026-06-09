import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from './ui/dialog';
import {
  Plus,
  Users,
  DollarSign,
  Clock,
  Minus,
  Edit,
  CheckCircle2,
  Trash2,
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
  type Table
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

export function normalizeOrderQuantity(
  value: string,
  available: number
): number {
  if (value.trim() === '') return 0;

  const quantity = Number(value);
  if (!Number.isFinite(quantity) || quantity <= 0) return 0;

  return Math.min(Math.trunc(quantity), Math.max(available, 0));
}

function mapTable(table: Table, menuItems: MenuItem[]): Mesa {
  const detalleConsumo = table.items.map((item): DetalleConsumo => {
    const producto = menuItems.find(menuItem => Number(menuItem.id) === item.product_id);

    return {
      itemId: String(item.id),
      productId: String(item.product_id),
      nombre: producto?.nombre ?? `Producto #${item.product_id}`,
      tipo: producto?.tipo ?? 'comida',
      cantidad: item.quantity,
      precioUnitario: item.curr_price,
      subtotal: item.quantity * item.curr_price
    };
  });

  return {
    id: String(table.id),
    numero: table.table_number,
    nombrePersonalizado: table.table_name ?? undefined,
    estado: table.people > 0 || table.items.length > 0 ? 'ocupada' : 'libre',
    personas: table.people,
    horaInicio: table.opening_time,
    consumo: detalleConsumo.reduce((total, item) => total + item.subtotal, 0),
    detalleConsumo
  };
}

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

  useEffect(() => {
    void cargarDatos();
  }, []);

  const cargarDatos = async () => {
    try {
      const [productosDb, mesasDb] = await Promise.all([
        fetchProducts(),
        fetchTables()
      ]);
      const menu = productosDb.map((producto): MenuItem => ({
        id: String(producto.id),
        nombre: producto.name,
        precio: producto.price,
        tipo: producto.type,
        disponible: producto.qty
      }));

      setMenuItems(menu);
      setMesas(mesasDb.map(mesa => mapTable(mesa, menu)));
    } catch (error) {
      setMesas([]);
      setMenuItems([]);
      toast.error(error instanceof Error ? error.message : 'No se pudieron cargar las mesas');
    }
  };

  const cargarMenu = async () => {
    const productosDb = await fetchProducts();
    const menu = productosDb.map((producto): MenuItem => ({
      id: String(producto.id),
      nombre: producto.name,
      precio: producto.price,
      tipo: producto.type,
      disponible: producto.qty
    }));
    setMenuItems(menu);
    return menu;
  };

  const recargarMesa = async (tableNumber: number) => {
    const [mesaDb, menu] = await Promise.all([
      fetchTable(tableNumber),
      cargarMenu()
    ]);
    const mesaActualizada = mapTable(mesaDb, menu);

    setMesas(actuales => actuales.map(mesa =>
      mesa.numero === tableNumber ? mesaActualizada : mesa
    ));
    setMesaParaCierre(actual => actual?.numero === tableNumber ? mesaActualizada : actual);
    return mesaActualizada;
  };

  const crearMesa = async () => {
    const numero = Number(nuevaMesa.numero);
    const mesaExistente = mesas.find(m => m.numero === numero);
    if (mesaExistente) {
      toast.error('Ya existe una mesa con ese número');
      return;
    }

    if (!Number.isInteger(numero) || numero <= 0) {
      toast.error('El número de mesa debe ser un entero mayor a 0');
      return;
    }

    setProcesandoMesa(true);
    try {
      await createTable({
        table_number: numero,
        table_name: nuevaMesa.nombre.trim() || null,
        people: 0
      });
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

  const eliminarMesa = async (mesa: Mesa) => {
    setProcesandoMesa(true);
    try {
      await deleteTable(mesa.numero);
      await cargarDatos();
      toast.success(`Mesa ${mesa.numero} eliminada`);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : 'No se pudo eliminar la mesa'
      );
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
      await updateTable(editingMesa.numero, {
        table_name: editingMesa.nombrePersonalizado?.trim() || null
      });
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
    if (
      !Number.isInteger(cantidad)
      || cantidad <= 0
      || cantidad > mesaParaQuitarPersonas.personas
    ) {
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

  const quitarConsumo = async (
    tableNumber: number,
    itemId: number,
    quantity: number
  ) => {
    await removeTableProduct(tableNumber, itemId, quantity);
    await recargarMesa(tableNumber);
  };

  const confirmarCierre = async (
    tableNumber: number,
    payments: Array<{
      tipo: 'efectivo' | 'tarjeta_credito' | 'tarjeta_debito' | 'mercado_pago';
      monto: number;
    }>
  ) => {
    const response = await closeTable(
      tableNumber,
      payments.map(payment => ({
        method: payment.tipo,
        amount: Math.round(payment.monto)
      }))
    );
    return response;
  };

  const actualizarCantidadItem = (
    itemId: string,
    value: string,
    available: number
  ) => {
    const cantidad = normalizeOrderQuantity(value, available);

    setPedido(prev => {
      const existe = prev.some(item => item.itemId === itemId);
      if (cantidad === 0) {
        return prev.filter(item => item.itemId !== itemId);
      }
      if (existe) {
        return prev.map(item =>
          item.itemId === itemId ? { ...item, cantidad } : item
        );
      }
      return [...prev, { itemId, cantidad }];
    });
  };

  const incrementarItem = (itemId: string, available: number) => {
    setPedido(prev => {
      const existe = prev.find(p => p.itemId === itemId);
      if (existe) {
        if (existe.cantidad >= available) return prev;
        return prev.map(p => 
          p.itemId === itemId 
            ? { ...p, cantidad: p.cantidad + 1 }
            : p
        );
      }
      return available > 0 ? [...prev, { itemId, cantidad: 1 }] : prev;
    });
  };

  const decrementarItem = (itemId: string) => {
    setPedido(prev => {
      const existe = prev.find(p => p.itemId === itemId);
      if (!existe) return prev;
      
      if (existe.cantidad === 1) {
        return prev.filter(p => p.itemId !== itemId);
      }
      
      return prev.map(p =>
        p.itemId === itemId
          ? { ...p, cantidad: p.cantidad - 1 }
          : p
      );
    });
  };

  const calcularTotalPedido = () => {
    return pedido.reduce((sum, item) => {
      const menuItem = menuItems.find(m => m.id === item.itemId);
      return sum + (menuItem?.precio || 0) * item.cantidad;
    }, 0);
  };

  const agregarConsumo = async () => {
    const mesa = mesas.find(item => item.id === selectedMesaId);
    const total = calcularTotalPedido();

    if (!mesa || pedido.length === 0 || total === 0) {
      toast.error('Agrega al menos un ítem al pedido');
      return;
    }

    setProcesandoMesa(true);
    try {
      await addTableProducts(
        mesa.numero,
        pedido.map(item => ({
          product_id: Number(item.itemId),
          quantity: item.cantidad
        }))
      );
      await recargarMesa(mesa.numero);
      setPedido([]);
      setConsumoDialogOpen(false);
      toast.success(`Consumo agregado: $${total.toLocaleString('es-AR')}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo agregar el pedido');
    } finally {
      setProcesandoMesa(false);
    }
  };

  const mesasOrdenadas = [...mesas].sort((a, b) => a.numero - b.numero);

  return (
    <div className="p-8">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-[#D4AF37] mb-2">Gestión de Mesas</h1>
          <p className="text-[#a0a0a0]">Control de mesas y pedidos</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button className="bg-[#D4AF37] hover:bg-[#B8860B] text-[#0a0a0a]">
              <Plus className="w-4 h-4 mr-2" />
              Nueva Mesa
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-[#1a1a1a] border-[#3a3a3a]">
            <DialogHeader>
              <DialogTitle className="text-[#D4AF37]">Crear Nueva Mesa</DialogTitle>
              <DialogDescription className="text-[#a0a0a0]">
                Ingresa los datos de la nueva mesa
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label className="text-[#f5f5dc]">Número de Mesa</Label>
                <Input
                  type="number"
                  value={nuevaMesa.numero}
                  onChange={(e) => setNuevaMesa({ ...nuevaMesa, numero: e.target.value })}
                  className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-[#f5f5dc]">Nombre Personalizado (opcional)</Label>
                <Input
                  type="text"
                  placeholder="Ej: Mesa Interna, Mesa VIP, etc."
                  value={nuevaMesa.nombre}
                  onChange={(e) => setNuevaMesa({ ...nuevaMesa, nombre: e.target.value })}
                  className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
                />
              </div>
              <Button
                onClick={crearMesa}
                disabled={procesandoMesa}
                className="w-full bg-[#D4AF37] hover:bg-[#B8860B] text-[#0a0a0a]"
              >
                {procesandoMesa ? 'Creando...' : 'Crear Mesa'}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {mesasOrdenadas.map((mesa) => (
          <Card
            key={mesa.id}
            className={`border-2 ${
              mesa.estado === 'ocupada'
                ? 'bg-[#2a2a1a] border-[#D4AF37]'
                : 'bg-[#1a1a1a] border-[#3a3a3a]'
            }`}
          >
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span className="text-[#f5f5dc]">
                  {mesa.nombrePersonalizado || `Mesa ${mesa.numero}`}
                </span>
                <div className="flex gap-2">
                  {isAdmin && (
                    <Button
                      onClick={() => editarMesa(mesa)}
                      size="sm"
                      variant="ghost"
                      className="text-[#D4AF37] hover:bg-[#3a3a3a]"
                    >
                      <Edit className="w-4 h-4" />
                    </Button>
                  )}
                  {mesa.estado === 'libre' && (
                    <Button
                      onClick={() => void eliminarMesa(mesa)}
                      disabled={procesandoMesa}
                      size="sm"
                      variant="ghost"
                      className="text-red-400 hover:bg-red-950/40 hover:text-red-300"
                      title="Eliminar mesa"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  )}
                </div>
              </CardTitle>
              <CardDescription className="text-[#a0a0a0]">
                {mesa.estado === 'ocupada' ? (
                  <span className="text-[#D4AF37]">● Ocupada</span>
                ) : (
                  <span className="text-[#22c55e]">● Disponible</span>
                )}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {mesa.estado === 'ocupada' && (
                <>
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Users className="w-4 h-4 text-[#a0a0a0]" />
                      <span className="text-[#f5f5dc]">{mesa.personas} personas</span>
                    </div>
                    {mesa.personas > 0 && (
                      <Button
                        onClick={() => abrirQuitarPersonas(mesa)}
                        size="sm"
                        variant="ghost"
                        className="text-red-400 hover:bg-[#3a3a3a]"
                      >
                        <Minus className="w-3 h-3 mr-1" />
                        Quitar
                      </Button>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <Clock className="w-4 h-4 text-[#a0a0a0]" />
                    <span className="text-[#f5f5dc]">
                      {mesa.horaInicio
                        ? new Date(mesa.horaInicio).toLocaleTimeString('es-AR', {
                            hour: '2-digit',
                            minute: '2-digit',
                          })
                        : '-'}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <DollarSign className="w-4 h-4 text-[#a0a0a0]" />
                    <span className="text-[#D4AF37] font-semibold">
                      ${mesa.consumo.toLocaleString('es-AR')}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <Button
                      onClick={() => {
                        setSelectedMesaId(mesa.id);
                        setPedido([]);
                        setConsumoDialogOpen(true);
                      }}
                      size="sm"
                      variant="outline"
                      className="border-[#3a3a3a] text-[#f5f5dc] hover:bg-[#3a3a3a]"
                    >
                      <Plus className="w-4 h-4 mr-1" />
                      Pedido
                    </Button>
                    <Button
                      onClick={() => void abrirPreCierre(mesa.id)}
                      size="sm"
                      className="bg-[#D4AF37] hover:bg-[#B8860B] text-[#0a0a0a]"
                    >
                      <CheckCircle2 className="w-4 h-4 mr-1" />
                      Detalle
                    </Button>
                  </div>
                </>
              )}
              {mesa.estado === 'libre' && (
                <Button
                  onClick={() => abrirOcuparMesa(mesa.id)}
                  className="w-full bg-[#22c55e] hover:bg-[#16a34a] text-white"
                >
                  <Users className="w-4 h-4 mr-2" />
                  Ocupar Mesa
                </Button>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Dialog de Edición de Mesa */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="bg-[#1a1a1a] border-[#3a3a3a]">
          <DialogHeader>
            <DialogTitle className="text-[#D4AF37]">Editar Mesa</DialogTitle>
          </DialogHeader>
          {editingMesa && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label className="text-[#f5f5dc]">Número de Mesa</Label>
                <Input
                  type="number"
                  value={editingMesa.numero}
                  disabled
                  className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
                />
                <p className="text-xs text-[#a0a0a0]">
                  El backend no permite modificar el número de una mesa.
                </p>
              </div>
              <div className="space-y-2">
                <Label className="text-[#f5f5dc]">Nombre Personalizado</Label>
                <Input
                  type="text"
                  placeholder="Ej: Mesa Interna, Mesa VIP, etc."
                  value={editingMesa.nombrePersonalizado || ''}
                  onChange={(e) => setEditingMesa({ ...editingMesa, nombrePersonalizado: e.target.value })}
                  className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <Button
                  onClick={() => setEditDialogOpen(false)}
                  variant="outline"
                  className="border-[#3a3a3a] text-[#f5f5dc] hover:bg-[#3a3a3a]"
                >
                  Cancelar
                </Button>
                <Button
                  onClick={guardarEdicionMesa}
                  disabled={procesandoMesa}
                  className="bg-[#D4AF37] hover:bg-[#B8860B] text-[#0a0a0a]"
                >
                  {procesandoMesa ? 'Guardando...' : 'Guardar'}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Dialog de Consumo */}
      <Dialog open={consumoDialogOpen} onOpenChange={(open) => {
        setConsumoDialogOpen(open);
        if (open) {
          void cargarMenu().catch(error => {
            toast.error(error instanceof Error ? error.message : 'No se pudo cargar el menú');
          });
        }
      }}>
        <DialogContent className="bg-[#1a1a1a] border-[#3a3a3a] max-w-3xl max-h-[85vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="text-[#D4AF37]">Agregar Pedido</DialogTitle>
            <DialogDescription className="text-[#a0a0a0]">
              Selecciona los productos y cantidades
            </DialogDescription>
          </DialogHeader>
          
          <div className="overflow-y-auto flex-1 pr-2 space-y-4">
            {/* Cervezas */}
            <div>
              <h3 className="text-[#D4AF37] mb-2 text-sm font-semibold sticky top-0 bg-[#1a1a1a] py-1 z-10">Cervezas</h3>
              <div className="grid grid-cols-2 gap-2">
                {menuItems
                  .filter((item) => item.tipo === 'cerveza')
                  .map((item) => {
                    const cantidadPedido = pedido.find((p) => p.itemId === item.id)?.cantidad || 0;
                    return (
                      <div
                        key={item.id}
                        className="p-2 bg-[#2a2a2a] rounded border border-[#3a3a3a]"
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-[#f5f5dc] text-sm font-medium">{item.nombre}</span>
                          <span className="text-[#D4AF37] text-sm">${(item.precio / 1000).toFixed(1)}k</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <Button
                            onClick={() => decrementarItem(item.id)}
                            size="sm"
                            variant="outline"
                            className="border-[#3a3a3a] text-[#f5f5dc] hover:bg-[#3a3a3a] h-7 w-7 p-0"
                            disabled={cantidadPedido === 0}
                          >
                            <Minus className="w-3 h-3" />
                          </Button>
                          <Input
                            type="number"
                            min="0"
                            max={item.disponible}
                            step="1"
                            value={cantidadPedido || ''}
                            placeholder="0"
                            aria-label={`Cantidad de ${item.nombre}`}
                            onFocus={event => event.currentTarget.select()}
                            onChange={event => actualizarCantidadItem(
                              item.id,
                              event.target.value,
                              item.disponible
                            )}
                            className="h-7 w-16 px-1 text-center text-sm bg-[#1a1a1a] border-[#3a3a3a] text-[#f5f5dc]"
                          />
                          <Button
                            onClick={() => incrementarItem(item.id, item.disponible)}
                            size="sm"
                            className="bg-[#D4AF37] hover:bg-[#B8860B] text-[#0a0a0a] h-7 w-7 p-0"
                            disabled={cantidadPedido >= item.disponible}
                          >
                            <Plus className="w-3 h-3" />
                          </Button>
                        </div>
                        <p className="mt-1 text-xs text-[#a0a0a0]">
                          Disponible: {item.disponible}
                        </p>
                      </div>
                    );
                  })}
              </div>
            </div>

            {/* Comidas */}
            <div>
              <h3 className="text-[#D4AF37] mb-2 text-sm font-semibold sticky top-0 bg-[#1a1a1a] py-1 z-10">Comidas</h3>
              <div className="grid grid-cols-2 gap-2">
                {menuItems
                  .filter((item) => item.tipo === 'comida')
                  .map((item) => {
                    const cantidadPedido = pedido.find((p) => p.itemId === item.id)?.cantidad || 0;
                    return (
                      <div
                        key={item.id}
                        className="p-2 bg-[#2a2a2a] rounded border border-[#3a3a3a]"
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-[#f5f5dc] text-sm font-medium">{item.nombre}</span>
                          <span className="text-[#D4AF37] text-sm">${(item.precio / 1000).toFixed(1)}k</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <Button
                            onClick={() => decrementarItem(item.id)}
                            size="sm"
                            variant="outline"
                            className="border-[#3a3a3a] text-[#f5f5dc] hover:bg-[#3a3a3a] h-7 w-7 p-0"
                            disabled={cantidadPedido === 0}
                          >
                            <Minus className="w-3 h-3" />
                          </Button>
                          <Input
                            type="number"
                            min="0"
                            max={item.disponible}
                            step="1"
                            value={cantidadPedido || ''}
                            placeholder="0"
                            aria-label={`Cantidad de ${item.nombre}`}
                            onFocus={event => event.currentTarget.select()}
                            onChange={event => actualizarCantidadItem(
                              item.id,
                              event.target.value,
                              item.disponible
                            )}
                            className="h-7 w-16 px-1 text-center text-sm bg-[#1a1a1a] border-[#3a3a3a] text-[#f5f5dc]"
                          />
                          <Button
                            onClick={() => incrementarItem(item.id, item.disponible)}
                            size="sm"
                            className="bg-[#D4AF37] hover:bg-[#B8860B] text-[#0a0a0a] h-7 w-7 p-0"
                            disabled={cantidadPedido >= item.disponible}
                          >
                            <Plus className="w-3 h-3" />
                          </Button>
                        </div>
                        <p className="mt-1 text-xs text-[#a0a0a0]">
                          Disponible: {item.disponible}
                        </p>
                      </div>
                    );
                  })}
              </div>
            </div>

            {/* Tragos */}
            <div>
              <h3 className="text-[#D4AF37] mb-2 text-sm font-semibold sticky top-0 bg-[#1a1a1a] py-1 z-10">Tragos</h3>
              <div className="grid grid-cols-2 gap-2">
                {menuItems
                  .filter((item) => item.tipo === 'trago')
                  .map((item) => {
                    const cantidadPedido = pedido.find((p) => p.itemId === item.id)?.cantidad || 0;
                    return (
                      <div
                        key={item.id}
                        className="p-2 bg-[#2a2a2a] rounded border border-[#3a3a3a]"
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-[#f5f5dc] text-sm font-medium">{item.nombre}</span>
                          <span className="text-[#D4AF37] text-sm">${(item.precio / 1000).toFixed(1)}k</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <Button
                            onClick={() => decrementarItem(item.id)}
                            size="sm"
                            variant="outline"
                            className="border-[#3a3a3a] text-[#f5f5dc] hover:bg-[#3a3a3a] h-7 w-7 p-0"
                            disabled={cantidadPedido === 0}
                          >
                            <Minus className="w-3 h-3" />
                          </Button>
                          <Input
                            type="number"
                            min="0"
                            max={item.disponible}
                            step="1"
                            value={cantidadPedido || ''}
                            placeholder="0"
                            aria-label={`Cantidad de ${item.nombre}`}
                            onFocus={event => event.currentTarget.select()}
                            onChange={event => actualizarCantidadItem(
                              item.id,
                              event.target.value,
                              item.disponible
                            )}
                            className="h-7 w-16 px-1 text-center text-sm bg-[#1a1a1a] border-[#3a3a3a] text-[#f5f5dc]"
                          />
                          <Button
                            onClick={() => incrementarItem(item.id, item.disponible)}
                            size="sm"
                            className="bg-[#D4AF37] hover:bg-[#B8860B] text-[#0a0a0a] h-7 w-7 p-0"
                            disabled={cantidadPedido >= item.disponible}
                          >
                            <Plus className="w-3 h-3" />
                          </Button>
                        </div>
                        <p className="mt-1 text-xs text-[#a0a0a0]">
                          Disponible: {item.disponible}
                        </p>
                      </div>
                    );
                  })}
              </div>
            </div>

            {/* Bebidas sin Alcohol */}
            <div>
              <h3 className="text-[#D4AF37] mb-2 text-sm font-semibold sticky top-0 bg-[#1a1a1a] py-1 z-10">Bebidas sin Alcohol</h3>
              <div className="grid grid-cols-2 gap-2">
                {menuItems
                  .filter((item) => item.tipo === 'bebida')
                  .map((item) => {
                    const cantidadPedido = pedido.find((p) => p.itemId === item.id)?.cantidad || 0;
                    return (
                      <div
                        key={item.id}
                        className="p-2 bg-[#2a2a2a] rounded border border-[#3a3a3a]"
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-[#f5f5dc] text-sm font-medium">{item.nombre}</span>
                          <span className="text-[#D4AF37] text-sm">${(item.precio / 1000).toFixed(1)}k</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <Button
                            onClick={() => decrementarItem(item.id)}
                            size="sm"
                            variant="outline"
                            className="border-[#3a3a3a] text-[#f5f5dc] hover:bg-[#3a3a3a] h-7 w-7 p-0"
                            disabled={cantidadPedido === 0}
                          >
                            <Minus className="w-3 h-3" />
                          </Button>
                          <Input
                            type="number"
                            min="0"
                            max={item.disponible}
                            step="1"
                            value={cantidadPedido || ''}
                            placeholder="0"
                            aria-label={`Cantidad de ${item.nombre}`}
                            onFocus={event => event.currentTarget.select()}
                            onChange={event => actualizarCantidadItem(
                              item.id,
                              event.target.value,
                              item.disponible
                            )}
                            className="h-7 w-16 px-1 text-center text-sm bg-[#1a1a1a] border-[#3a3a3a] text-[#f5f5dc]"
                          />
                          <Button
                            onClick={() => incrementarItem(item.id, item.disponible)}
                            size="sm"
                            className="bg-[#D4AF37] hover:bg-[#B8860B] text-[#0a0a0a] h-7 w-7 p-0"
                            disabled={cantidadPedido >= item.disponible}
                          >
                            <Plus className="w-3 h-3" />
                          </Button>
                        </div>
                        <p className="mt-1 text-xs text-[#a0a0a0]">
                          Disponible: {item.disponible}
                        </p>
                      </div>
                    );
                  })}
              </div>
            </div>
          </div>

          {/* Total - Sticky al fondo */}
          <div className="pt-4 border-t border-[#3a3a3a] mt-2 space-y-3">
            {pedido.length > 0 && (
              <div className="p-3 bg-[#2a2a2a] rounded-lg border-2 border-[#D4AF37]">
                <div className="flex items-center justify-between">
                  <span className="text-[#f5f5dc] font-semibold">Total del Pedido:</span>
                  <span className="text-[#D4AF37] text-xl font-bold">
                    ${calcularTotalPedido().toLocaleString('es-AR')}
                  </span>
                </div>
              </div>
            )}

            <Button
              onClick={agregarConsumo}
              disabled={procesandoMesa || pedido.length === 0}
              className="w-full bg-[#D4AF37] hover:bg-[#B8860B] text-[#0a0a0a]"
            >
              {procesandoMesa ? 'Agregando...' : 'Confirmar Pedido'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Pre-Cierre */}
      <PreCierreMesa
        mesa={mesaParaCierre}
        open={preCierreDialogOpen}
        onOpenChange={(open) => {
          setPreCierreDialogOpen(open);
          if (!open && mesaParaCierre) {
            void cargarDatos();
            setMesaParaCierre(null);
          }
        }}
        onRemoveItem={quitarConsumo}
        onConfirmarCierre={confirmarCierre}
      />

      {/* Dialog de Ocupar Mesa */}
      <Dialog open={ocuparDialogOpen} onOpenChange={setOcuparDialogOpen}>
        <DialogContent className="bg-[#1a1a1a] border-[#3a3a3a] max-w-2xl">
          <DialogHeader>
            <DialogTitle className="text-[#D4AF37]">Ocupar Mesa</DialogTitle>
            <DialogDescription className="text-[#a0a0a0]">
              Ingresa el número de personas
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-6">
            <div className="space-y-2">
              <Label className="text-[#f5f5dc]">Número de Personas</Label>
              <Input
                type="number"
                value={personasOcupar}
                onChange={(e) => setPersonasOcupar(e.target.value)}
                className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Button
                onClick={() => setOcuparDialogOpen(false)}
                variant="outline"
                className="border-[#3a3a3a] text-[#f5f5dc] hover:bg-[#3a3a3a]"
              >
                Cancelar
              </Button>
              <Button
                onClick={() => void ocuparMesa()}
                disabled={procesandoMesa}
                className="bg-[#D4AF37] hover:bg-[#B8860B] text-[#0a0a0a]"
              >
                {procesandoMesa ? 'Guardando...' : 'Ocupar'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Dialog para quitar personas */}
      <Dialog open={quitarPersonasDialogOpen} onOpenChange={setQuitarPersonasDialogOpen}>
        <DialogContent className="bg-[#1a1a1a] border-[#3a3a3a] max-w-md">
          <DialogHeader>
            <DialogTitle className="text-[#D4AF37]">Quitar personas</DialogTitle>
            <DialogDescription className="text-[#a0a0a0]">
              {mesaParaQuitarPersonas
                ? `${mesaParaQuitarPersonas.nombrePersonalizado || `Mesa ${mesaParaQuitarPersonas.numero}`} tiene ${mesaParaQuitarPersonas.personas} persona(s)`
                : 'Indicá cuántas personas querés quitar'}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label className="text-[#f5f5dc]">Cantidad a quitar</Label>
              <Input
                type="number"
                min="1"
                max={mesaParaQuitarPersonas?.personas}
                step="1"
                value={personasAQuitar}
                onChange={(e) => setPersonasAQuitar(e.target.value)}
                className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Button
                onClick={() => setQuitarPersonasDialogOpen(false)}
                variant="outline"
                className="border-[#3a3a3a] text-[#f5f5dc] hover:bg-[#3a3a3a]"
              >
                Cancelar
              </Button>
              <Button
                onClick={() => void quitarPersonas()}
                disabled={procesandoMesa}
                className="bg-red-600 hover:bg-red-700 text-white"
              >
                {procesandoMesa ? 'Quitando...' : 'Quitar'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
