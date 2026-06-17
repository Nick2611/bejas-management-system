import { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Beer,
  Edit,
  Flame,
  History,
  Minus,
  Plus,
  Trash2,
  TrendingDown,
  TrendingUp,
  UtensilsCrossed,
  Wine,
} from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../context/AuthContext';
import {
  createProduct,
  deleteProduct,
  fetchProducts,
  updateProduct,
  type Product,
  type ProductType,
} from '../services/productsApi';
import {
  adjustStock,
  fetchStockMovements,
  type ManualMovementType,
  type StockMovement,
} from '../services/stockApi';
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';

const PRODUCT_TYPES: ProductType[] = ['cerveza', 'comida', 'trago', 'bebida'];

const TYPE_META: Record<ProductType, { plural: string; icon: React.ElementType }> = {
  cerveza: { plural: 'Cervezas',  icon: Beer },
  comida:  { plural: 'Comidas',   icon: UtensilsCrossed },
  trago:   { plural: 'Tragos',    icon: Wine },
  bebida:  { plural: 'Bebidas',   icon: Flame },
};

const STOCK_PREDETERMINADO: Array<{
  name: string; type: ProductType; price: number;
  qty: number; unit: string; minimum_qty: number; capacity_qty: number | null;
}> = [
  // Barriles
  { name: 'Belgian Bitter',       type: 'cerveza', price: 3000, qty: 30, unit: 'litros',   minimum_qty: 10, capacity_qty: 30 },
  { name: 'Pale Ale',             type: 'cerveza', price: 3000, qty: 30, unit: 'litros',   minimum_qty: 10, capacity_qty: 30 },
  { name: 'APA',                  type: 'cerveza', price: 3000, qty: 30, unit: 'litros',   minimum_qty: 10, capacity_qty: 30 },
  { name: 'Honey',                type: 'cerveza', price: 3000, qty: 30, unit: 'litros',   minimum_qty: 10, capacity_qty: 30 },
  { name: 'IPA',                  type: 'cerveza', price: 3000, qty: 30, unit: 'litros',   minimum_qty: 10, capacity_qty: 30 },
  { name: 'Scottish',             type: 'cerveza', price: 3000, qty: 30, unit: 'litros',   minimum_qty: 10, capacity_qty: 30 },
  { name: 'Dubbel',               type: 'cerveza', price: 3000, qty: 30, unit: 'litros',   minimum_qty: 10, capacity_qty: 30 },
  { name: 'Porter',               type: 'cerveza', price: 3000, qty: 30, unit: 'litros',   minimum_qty: 10, capacity_qty: 30 },
  // Comidas
  { name: 'Papas Fritas Clásicas', type: 'comida', price: 2000, qty: 50, unit: 'porciones', minimum_qty: 10, capacity_qty: null },
  { name: 'Papas Fritas Rústicas', type: 'comida', price: 2000, qty: 50, unit: 'porciones', minimum_qty: 10, capacity_qty: null },
  { name: 'Tequeños 6 UNID',       type: 'comida', price: 2500, qty: 30, unit: 'porciones', minimum_qty: 5,  capacity_qty: null },
  { name: 'Tequeños 12 UNID',      type: 'comida', price: 3500, qty: 20, unit: 'porciones', minimum_qty: 5,  capacity_qty: null },
  { name: 'Pasteles 4 UNID',       type: 'comida', price: 2500, qty: 25, unit: 'porciones', minimum_qty: 5,  capacity_qty: null },
  { name: 'Nachos con Cheddar',    type: 'comida', price: 2000, qty: 40, unit: 'porciones', minimum_qty: 10, capacity_qty: null },
  // Tragos
  { name: 'Gin (botellas)',          type: 'trago', price: 2500, qty: 5, unit: 'litros', minimum_qty: 2, capacity_qty: null },
  { name: 'Fernet Branca (botellas)',type: 'trago', price: 2500, qty: 6, unit: 'litros', minimum_qty: 2, capacity_qty: null },
  { name: 'Vermut (botellas)',       type: 'trago', price: 2500, qty: 4, unit: 'litros', minimum_qty: 2, capacity_qty: null },
  { name: 'Ron (botellas)',          type: 'trago', price: 2500, qty: 5, unit: 'litros', minimum_qty: 2, capacity_qty: null },
  { name: 'Vodka (botellas)',        type: 'trago', price: 2500, qty: 5, unit: 'litros', minimum_qty: 2, capacity_qty: null },
  { name: 'Campari (botellas)',      type: 'trago', price: 2500, qty: 4, unit: 'litros', minimum_qty: 1, capacity_qty: null },
  { name: 'Aperol (botellas)',       type: 'trago', price: 2500, qty: 3, unit: 'litros', minimum_qty: 1, capacity_qty: null },
  // Bebidas
  { name: 'Coca-Cola 354ml',    type: 'bebida', price: 800,  qty: 48, unit: 'unidades', minimum_qty: 12, capacity_qty: null },
  { name: 'Sprite 354ml',       type: 'bebida', price: 800,  qty: 36, unit: 'unidades', minimum_qty: 12, capacity_qty: null },
  { name: 'Fanta Naranja 354ml',type: 'bebida', price: 800,  qty: 24, unit: 'unidades', minimum_qty: 12, capacity_qty: null },
  { name: 'Agua Mineral',       type: 'bebida', price: 500,  qty: 48, unit: 'unidades', minimum_qty: 12, capacity_qty: null },
];

type EditableProduct = Omit<Product, 'price' | 'minimum_qty' | 'capacity_qty'> & {
  price: string;
  minimum_qty: string;
  capacity_qty: string;
};

export function limitStockAdjustment(
  value: string,
  direction: 'add' | 'subtract',
  product: Pick<Product, 'qty' | 'capacity_qty'>,
): string {
  if (value === '') return '';
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return '';
  const maximum = direction === 'subtract'
    ? product.qty
    : product.capacity_qty === null
      ? null
      : Math.max(product.capacity_qty - product.qty, 0);
  const normalized = Math.max(0, Math.floor(parsed));
  return String(maximum === null ? normalized : Math.min(normalized, maximum));
}

export function getStockAdjustmentMaximum(
  product: Pick<Product, 'qty' | 'capacity_qty'> | null,
  direction: 'add' | 'subtract',
): number | undefined {
  if (!product) return undefined;
  if (direction === 'subtract') return product.qty;
  if (product.capacity_qty === null) return undefined;
  return Math.max(product.capacity_qty - product.qty, 0);
}

export function getStockAdjustmentHint(
  product: Pick<Product, 'qty' | 'capacity_qty'> | null,
  direction: 'add' | 'subtract',
): string {
  if (!product) return '';
  if (direction === 'subtract') return `Máximo a descontar: ${product.qty}`;
  if (product.capacity_qty === null) return 'Este producto no tiene una capacidad máxima configurada.';
  return `Máximo a agregar: ${Math.max(product.capacity_qty - product.qty, 0)}`;
}

function getBarrelBorderColor(level: number): string {
  if (level > 60) return 'border-green-500';
  if (level > 30) return 'border-orange-500';
  return 'border-red-500';
}

function getBarrelBarColor(level: number): string {
  if (level > 60) return 'bg-green-500';
  if (level > 30) return 'bg-orange-500';
  return 'bg-red-500';
}

function getBarrelTextColor(level: number): string {
  if (level > 60) return 'text-green-400';
  if (level > 30) return 'text-orange-400';
  return 'text-red-400';
}

function formatRestock(dateStr: string | null): string {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  return d.toLocaleString('es-AR', {
    day: 'numeric', month: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

export function Stock() {
  const { isAdmin } = useAuth();
  const [products, setProducts] = useState<Product[]>([]);
  const [movements, setMovements] = useState<StockMovement[]>([]);
  const [loading, setLoading] = useState(true);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [newOpen, setNewOpen] = useState(false);
  const [editProduct, setEditProduct] = useState<EditableProduct | null>(null);
  const [adjustProduct, setAdjustProduct] = useState<Product | null>(null);
  const [saving, setSaving] = useState(false);
  const [newProduct, setNewProduct] = useState({
    name: '', type: 'comida' as ProductType, price: '',
    qty: '', unit: 'unidades', minimum_qty: '0', capacity_qty: '',
  });
  const [adjustment, setAdjustment] = useState({
    quantity: '',
    direction: 'add' as 'add' | 'subtract',
    movementType: 'reposicion' as ManualMovementType,
    note: '',
  });

  const loadProducts = async () => {
    setLoading(true);
    try {
      setProducts(await fetchProducts());
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo cargar el stock');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      try {
        const fetched = await fetchProducts();
        const existingNames = new Set(fetched.map(p => p.name.toLowerCase()));
        const toCreate = STOCK_PREDETERMINADO.filter(p => !existingNames.has(p.name.toLowerCase()));
        if (toCreate.length > 0) {
          for (const item of toCreate) {
            await createProduct(item);
          }
          setProducts(await fetchProducts());
        } else {
          setProducts(fetched);
        }
      } catch (error) {
        toast.error(error instanceof Error ? error.message : 'No se pudo cargar el stock');
      } finally {
        setLoading(false);
      }
    };
    void init();
  }, []);

  const lowStockCount = useMemo(
    () => products.filter(p => p.qty <= p.minimum_qty).length,
    [products],
  );

  const adjustmentMaximum = getStockAdjustmentMaximum(adjustProduct, adjustment.direction);
  const adjustmentHint = getStockAdjustmentHint(adjustProduct, adjustment.direction);

  const loadHistory = async () => {
    try {
      setMovements(await fetchStockMovements());
      setHistoryOpen(true);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo cargar el historial');
    }
  };

  const recargarBarril = async (product: Product) => {
    if (!product.capacity_qty || product.qty >= product.capacity_qty) {
      toast.info('El barril ya está lleno');
      return;
    }
    const delta = product.capacity_qty - product.qty;
    setSaving(true);
    try {
      await adjustStock(product.id, delta, 'reposicion', 'Recarga completa');
      await loadProducts();
      toast.success(`${product.name} recargado a ${product.capacity_qty}L`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo recargar');
    } finally {
      setSaving(false);
    }
  };

  const operarBarril = (product: Product) => {
    setAdjustProduct(product);
    setAdjustment({ quantity: '', direction: 'subtract', movementType: 'merma', note: '' });
  };

  const submitNewProduct = async () => {
    const price = Number(newProduct.price);
    const qty = Number(newProduct.qty);
    const minimum = Number(newProduct.minimum_qty);
    const capacity = newProduct.capacity_qty ? Number(newProduct.capacity_qty) : null;
    if (!newProduct.name.trim() || !Number.isInteger(price) || price <= 0
      || !Number.isInteger(qty) || qty < 0 || !Number.isInteger(minimum) || minimum < 0) {
      toast.error('Revisá nombre, precio, cantidad y mínimo');
      return;
    }
    setSaving(true);
    try {
      await createProduct({
        name: newProduct.name.trim(), type: newProduct.type,
        price, qty, unit: newProduct.unit.trim(), minimum_qty: minimum, capacity_qty: capacity,
      });
      setNewOpen(false);
      setNewProduct({ name: '', type: 'comida', price: '', qty: '', unit: 'unidades', minimum_qty: '0', capacity_qty: '' });
      await loadProducts();
      toast.success('Producto creado');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo crear el producto');
    } finally {
      setSaving(false);
    }
  };

  const saveProduct = async () => {
    if (!editProduct) return;
    const price = Number(editProduct.price);
    const minimum = Number(editProduct.minimum_qty);
    const capacity = editProduct.capacity_qty === '' ? null : Number(editProduct.capacity_qty);
    if (!editProduct.name.trim() || !Number.isInteger(price) || price <= 0
      || !editProduct.unit.trim() || !Number.isInteger(minimum) || minimum < 0
      || (capacity !== null && (!Number.isInteger(capacity) || capacity <= 0))) {
      toast.error('Revisá nombre, tipo, precio, unidad, mínimo y capacidad');
      return;
    }
    setSaving(true);
    try {
      await updateProduct(editProduct.id, {
        name: editProduct.name.trim(), type: editProduct.type, price,
        unit: editProduct.unit.trim(), minimum_qty: minimum, capacity_qty: capacity,
      });
      setEditProduct(null);
      await loadProducts();
      toast.success('Producto actualizado');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo actualizar');
    } finally {
      setSaving(false);
    }
  };

  const applyAdjustment = async () => {
    if (!adjustProduct) return;
    const amount = Number(adjustment.quantity);
    if (!Number.isInteger(amount) || amount <= 0) {
      toast.error('La cantidad debe ser un entero mayor a cero');
      return;
    }
    const delta = adjustment.direction === 'add' ? amount : -amount;
    setSaving(true);
    try {
      await adjustStock(adjustProduct.id, delta, adjustment.movementType, adjustment.note);
      setAdjustProduct(null);
      setAdjustment({ quantity: '', direction: 'add', movementType: 'reposicion', note: '' });
      await loadProducts();
      toast.success('Stock actualizado');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo ajustar el stock');
    } finally {
      setSaving(false);
    }
  };

  const updateAdjustmentQuantity = (value: string) => {
    if (!adjustProduct) return;
    setAdjustment({ ...adjustment, quantity: limitStockAdjustment(value, adjustment.direction, adjustProduct) });
  };

  const changeAdjustmentDirection = (direction: 'add' | 'subtract') => {
    setAdjustment({ ...adjustment, quantity: '', direction, movementType: direction === 'add' ? 'reposicion' : 'merma' });
  };

  const removeProduct = async (product: Product) => {
    try {
      await deleteProduct(product.id);
      await loadProducts();
      toast.success('Producto eliminado');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo eliminar');
    }
  };

  const beers = useMemo(
    () => products.filter(p => p.type === 'cerveza').sort((a, b) => a.id - b.id),
    [products],
  );

  const renderBarrels = () => {
    if (loading) return <p className="text-[#a0a0a0]">Cargando...</p>;
    if (!beers.length) return <p className="text-[#a0a0a0]">No hay barriles configurados.</p>;

    return (
      <div className="grid md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
        {beers.map((product, idx) => {
          const capacity = product.capacity_qty ?? Math.max(product.qty, 1);
          const level = Math.min(100, Math.round((product.qty / capacity) * 100));
          const low = product.qty <= product.minimum_qty;
          const isFull = product.capacity_qty !== null && product.qty >= product.capacity_qty;

          return (
            <Card
              key={product.id}
              className={`bg-[#1a1a1a] border-2 ${getBarrelBorderColor(level)}`}
            >
              <CardHeader>
                <CardTitle className="text-[#f5f5dc] flex justify-between gap-2">
                  <div>
                    <span className="block">{product.name}</span>
                    <span className="text-sm font-normal text-[#D4AF37]">Barril #{idx + 1}</span>
                  </div>
                  {isAdmin && (
                    <div className="flex shrink-0">
                      <Button
                        size="sm" variant="ghost"
                        onClick={() => setEditProduct({
                          ...product,
                          price: String(product.price),
                          minimum_qty: String(product.minimum_qty),
                          capacity_qty: product.capacity_qty === null ? '' : String(product.capacity_qty),
                        })}
                      >
                        <Edit className="w-4 h-4 text-[#D4AF37]" />
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => void removeProduct(product)}>
                        <Trash2 className="w-4 h-4 text-red-500" />
                      </Button>
                    </div>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {low && (
                  <div className="flex items-center gap-2 p-2 rounded border border-red-500/40 bg-red-950/30">
                    <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
                    <span className="text-red-400 text-sm font-medium">¡Stock Bajo!</span>
                  </div>
                )}

                {/* Level bar */}
                <div>
                  <div className="flex justify-between text-xs text-[#a0a0a0] mb-1">
                    <span>Nivel</span>
                    <span className={`font-semibold ${getBarrelTextColor(level)}`}>{level}%</span>
                  </div>
                  <div className="h-2 bg-[#3a3a3a] rounded-full">
                    <div
                      className={`h-2 rounded-full transition-all duration-500 ${getBarrelBarColor(level)}`}
                      style={{ width: `${level}%` }}
                    />
                  </div>
                </div>

                {/* Stats */}
                <div className="flex justify-between text-sm">
                  <span className="text-[#a0a0a0]">Capacidad:</span>
                  <span className="text-[#f5f5dc] font-medium">
                    {product.capacity_qty !== null ? `${product.capacity_qty}L` : '—'}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-[#a0a0a0]">Actuales:</span>
                  <span className={`font-semibold ${getBarrelTextColor(level)}`}>{product.qty}.0L</span>
                </div>
                <div className="flex justify-between text-xs text-[#a0a0a0]">
                  <span>Recargado:</span>
                  <span>{formatRestock(product.last_restocked_at)}</span>
                </div>

                {/* Actions */}
                <div className="grid grid-cols-2 gap-2 pt-1">
                  <Button
                    size="sm"
                    variant="outline"
                    className="border-[#3a3a3a] text-[#f5f5dc] hover:bg-[#2a2a2a] flex items-center gap-1"
                    onClick={() => operarBarril(product)}
                  >
                    <TrendingDown className="w-3.5 h-3.5" /> Operar
                  </Button>
                  <Button
                    size="sm"
                    className="bg-[#D4AF37] hover:bg-[#B8860B] text-[#0a0a0a] flex items-center gap-1"
                    onClick={() => void recargarBarril(product)}
                    disabled={saving || isFull}
                  >
                    <TrendingUp className="w-3.5 h-3.5" /> Recargar
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    );
  };

  const renderProducts = (type: ProductType) => {
    const filtered = products.filter(p => p.type === type).sort((a, b) => a.id - b.id);
    const Icon = TYPE_META[type].icon;

    if (loading) return <p className="text-[#a0a0a0]">Cargando...</p>;
    if (!filtered.length) return <p className="text-[#a0a0a0]">No hay productos en esta categoría.</p>;

    return (
      <div className="grid md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
        {filtered.map(product => {
          const low = product.qty <= product.minimum_qty;
          return (
            <Card
              key={product.id}
              className={`bg-[#1a1a1a] border-2 ${low ? 'border-red-500' : 'border-[#3a3a3a]'}`}
            >
              <CardHeader>
                <CardTitle className="text-[#f5f5dc] flex justify-between gap-2">
                  <span className="flex-1">{product.name}</span>
                  <div className="flex items-center shrink-0">
                    {isAdmin && (
                      <>
                        <Button
                          size="sm" variant="ghost"
                          onClick={() => setEditProduct({
                            ...product,
                            price: String(product.price),
                            minimum_qty: String(product.minimum_qty),
                            capacity_qty: product.capacity_qty === null ? '' : String(product.capacity_qty),
                          })}
                        >
                          <Edit className="w-4 h-4 text-[#D4AF37]" />
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => void removeProduct(product)}>
                          <Trash2 className="w-4 h-4 text-red-500" />
                        </Button>
                      </>
                    )}
                    <Icon className="w-4 h-4 text-[#D4AF37] ml-1" />
                  </div>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {low && (
                  <p className="text-red-400 flex gap-2 text-sm">
                    <AlertTriangle className="w-4 h-4" /> Stock bajo
                  </p>
                )}
                <div className="flex justify-between text-sm">
                  <span className="text-[#a0a0a0]">Cantidad Actual:</span>
                  <span className="text-[#D4AF37] font-semibold">{product.qty} {product.unit}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-[#a0a0a0]">Mínimo:</span>
                  <span className="text-[#f5f5dc]">{product.minimum_qty} {product.unit}</span>
                </div>
                {isAdmin && (
                  <Button
                    className="w-full bg-[#D4AF37] text-[#0a0a0a]"
                    onClick={() => {
                      setAdjustProduct(product);
                      setAdjustment({ quantity: '', direction: 'add', movementType: 'reposicion', note: '' });
                    }}
                  >
                    Ajustar stock
                  </Button>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    );
  };

  return (
    <div className="p-8 space-y-6">
      <div className="flex justify-between items-start flex-wrap gap-4">
        <div>
          <h1 className="text-[#D4AF37] mb-2">Control de Stock</h1>
          <p className="text-[#a0a0a0]">
            {lowStockCount} producto(s) requieren atención
          </p>
        </div>
        {isAdmin && (
          <div className="flex gap-2 flex-wrap">
            <Button variant="outline" onClick={() => void loadHistory()}
              className="border-[#3a3a3a] text-[#f5f5dc] hover:bg-[#2a2a2a]"
            >
              <History className="w-4 h-4 mr-2" /> Historial
            </Button>
            <Button onClick={() => setNewOpen(true)} className="bg-[#D4AF37] text-[#0a0a0a]">
              <Plus className="w-4 h-4 mr-2" /> Nuevo producto
            </Button>
          </div>
        )}
      </div>

      <Tabs defaultValue="cerveza">
        <TabsList className="bg-[#1a1a1a]">
          {PRODUCT_TYPES.map(type => {
            const Icon = TYPE_META[type].icon;
            return (
              <TabsTrigger key={type} value={type} className="flex items-center gap-1.5">
                <Icon className="w-3.5 h-3.5" />
                {TYPE_META[type].plural}
              </TabsTrigger>
            );
          })}
        </TabsList>
        <TabsContent value="cerveza" className="mt-5">{renderBarrels()}</TabsContent>
        {(['comida', 'trago', 'bebida'] as ProductType[]).map(type => (
          <TabsContent key={type} value={type} className="mt-5">{renderProducts(type)}</TabsContent>
        ))}
      </Tabs>

      {/* Dialog: nuevo producto */}
      <Dialog open={newOpen} onOpenChange={setNewOpen}>
        <DialogContent className="bg-[#1a1a1a] border-[#3a3a3a]">
          <DialogHeader>
            <DialogTitle className="text-[#D4AF37]">Nuevo producto</DialogTitle>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-4">
            {([['Nombre', 'name'], ['Precio', 'price'], ['Cantidad', 'qty'], ['Unidad', 'unit'], ['Mínimo', 'minimum_qty'], ['Capacidad', 'capacity_qty']] as [string, string][]).map(([label, key]) => (
              <div className="space-y-2" key={key}>
                <Label className="text-[#f5f5dc]">{label}</Label>
                <Input
                  type={['price', 'qty', 'minimum_qty', 'capacity_qty'].includes(key) ? 'number' : 'text'}
                  value={newProduct[key as keyof typeof newProduct]}
                  onChange={e => setNewProduct({ ...newProduct, [key]: e.target.value })}
                  className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
                />
              </div>
            ))}
            <div className="space-y-2 col-span-2">
              <Label className="text-[#f5f5dc]">Tipo</Label>
              <select
                value={newProduct.type}
                onChange={e => setNewProduct({ ...newProduct, type: e.target.value as ProductType })}
                className="w-full h-9 bg-[#0a0a0a] border border-[#3a3a3a] text-[#f5f5dc] rounded px-3"
              >
                {PRODUCT_TYPES.map(t => <option key={t} value={t}>{TYPE_META[t].plural}</option>)}
              </select>
            </div>
            <Button onClick={() => void submitNewProduct()} disabled={saving} className="col-span-2 bg-[#D4AF37] text-[#0a0a0a]">
              {saving ? 'Creando...' : 'Crear'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Dialog: editar */}
      <Dialog open={!!editProduct} onOpenChange={open => !open && setEditProduct(null)}>
        <DialogContent className="bg-[#1a1a1a] border-[#3a3a3a]">
          <DialogHeader><DialogTitle className="text-[#D4AF37]">Editar producto</DialogTitle></DialogHeader>
          {editProduct && (
            <div className="space-y-3">
              <Input value={editProduct.name} onChange={e => setEditProduct({ ...editProduct, name: e.target.value })} className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]" />
              <select
                value={editProduct.type}
                onChange={e => setEditProduct({ ...editProduct, type: e.target.value as ProductType })}
                className="w-full h-9 bg-[#0a0a0a] border border-[#3a3a3a] text-[#f5f5dc] rounded px-3"
              >
                {PRODUCT_TYPES.map(t => <option key={t} value={t}>{TYPE_META[t].plural}</option>)}
              </select>
              <Input type="number" placeholder="Precio" value={editProduct.price} onChange={e => setEditProduct({ ...editProduct, price: e.target.value })} className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]" />
              <Input placeholder="Unidad" value={editProduct.unit} onChange={e => setEditProduct({ ...editProduct, unit: e.target.value })} className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]" />
              <Input type="number" placeholder="Mínimo" value={editProduct.minimum_qty} onChange={e => setEditProduct({ ...editProduct, minimum_qty: e.target.value })} className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]" />
              <Input type="number" placeholder="Capacidad (litros, opcional)" value={editProduct.capacity_qty} onChange={e => setEditProduct({ ...editProduct, capacity_qty: e.target.value })} className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]" />
              <Button onClick={() => void saveProduct()} disabled={saving} className="w-full bg-[#D4AF37] text-[#0a0a0a]">
                {saving ? 'Guardando...' : 'Guardar'}
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Dialog: ajustar */}
      <Dialog open={!!adjustProduct} onOpenChange={open => !open && setAdjustProduct(null)}>
        <DialogContent className="bg-[#1a1a1a] border-[#3a3a3a]">
          <DialogHeader>
            <DialogTitle className="text-[#D4AF37]">Ajustar — {adjustProduct?.name}</DialogTitle>
            <DialogDescription className="text-[#a0a0a0]">
              Cada operación quedará registrada en el historial.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Input
              type="number" min="0" max={adjustmentMaximum}
              value={adjustment.quantity}
              onChange={e => updateAdjustmentQuantity(e.target.value)}
              className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
            />
            <p className="text-xs text-[#a0a0a0]">{adjustmentHint}</p>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <Button
              variant="outline"
              className={adjustment.direction === 'add'
                ? 'bg-[#D4AF37] border-[#D4AF37] text-[#0a0a0a] hover:bg-[#B8860B]'
                : 'bg-transparent border-[#D4AF37] text-[#f5f5dc] hover:bg-[#2a2a2a]'}
              onClick={() => changeAdjustmentDirection('add')}
            >
              <Plus className="w-4 h-4" /> Agregar
            </Button>
            <Button
              variant="outline"
              className={adjustment.direction === 'subtract'
                ? 'bg-red-600 border-red-600 text-white hover:bg-red-700'
                : 'bg-transparent border-red-500 text-[#f5f5dc] hover:bg-red-950/40'}
              onClick={() => changeAdjustmentDirection('subtract')}
            >
              <Minus className="w-4 h-4" /> Descontar
            </Button>
          </div>
          <Input
            placeholder="Nota"
            value={adjustment.note}
            onChange={e => setAdjustment({ ...adjustment, note: e.target.value })}
            className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
          />
          <Button onClick={() => void applyAdjustment()} disabled={saving} className="bg-[#D4AF37] text-[#0a0a0a]">
            {saving ? 'Aplicando...' : 'Confirmar ajuste'}
          </Button>
        </DialogContent>
      </Dialog>

      {/* Dialog: historial */}
      <Dialog open={historyOpen} onOpenChange={setHistoryOpen}>
        <DialogContent className="bg-[#1a1a1a] border-[#3a3a3a] max-w-3xl max-h-[80vh] overflow-auto">
          <DialogHeader><DialogTitle className="text-[#D4AF37]">Movimientos de stock</DialogTitle></DialogHeader>
          <div className="space-y-2">
            {movements.map(m => (
              <div key={m.id} className="p-3 bg-[#2a2a2a] rounded flex justify-between">
                <div>
                  <p className="text-[#f5f5dc]">{m.product_name}</p>
                  <p className="text-xs text-[#a0a0a0]">{m.movement_type} · {new Date(m.created_at).toLocaleString('es-AR')}</p>
                </div>
                <span className={m.quantity_delta > 0 ? 'text-green-500' : 'text-red-400'}>
                  {m.quantity_delta > 0 ? '+' : ''}{m.quantity_delta}
                </span>
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
