import { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Edit,
  History,
  Minus,
  Plus,
  Trash2,
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

type EditableProduct = Omit<
  Product,
  'price' | 'minimum_qty' | 'capacity_qty'
> & {
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
  if (direction === 'subtract') {
    return `Máximo a descontar: ${product.qty}`;
  }
  if (product.capacity_qty === null) {
    return 'Este producto no tiene una capacidad máxima configurada.';
  }
  return `Máximo a agregar: ${Math.max(
    product.capacity_qty - product.qty,
    0,
  )}`;
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
    name: '',
    type: 'comida' as ProductType,
    price: '',
    qty: '',
    unit: 'unidades',
    minimum_qty: '0',
    capacity_qty: ''
  });
  const [adjustment, setAdjustment] = useState({
    quantity: '',
    direction: 'add' as 'add' | 'subtract',
    movementType: 'reposicion' as ManualMovementType,
    note: ''
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
    void loadProducts();
  }, []);

  const lowStockCount = useMemo(
    () => products.filter(product => product.qty <= product.minimum_qty).length,
    [products]
  );
  const adjustmentMaximum = getStockAdjustmentMaximum(
    adjustProduct,
    adjustment.direction,
  );
  const adjustmentHint = getStockAdjustmentHint(
    adjustProduct,
    adjustment.direction,
  );

  const loadHistory = async () => {
    try {
      setMovements(await fetchStockMovements());
      setHistoryOpen(true);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo cargar el historial');
    }
  };

  const submitNewProduct = async () => {
    const price = Number(newProduct.price);
    const qty = Number(newProduct.qty);
    const minimum = Number(newProduct.minimum_qty);
    const capacity = newProduct.capacity_qty
      ? Number(newProduct.capacity_qty)
      : null;
    if (
      !newProduct.name.trim()
      || !Number.isInteger(price) || price <= 0
      || !Number.isInteger(qty) || qty < 0
      || !Number.isInteger(minimum) || minimum < 0
    ) {
      toast.error('Revisá nombre, precio, cantidad y mínimo');
      return;
    }
    setSaving(true);
    try {
      await createProduct({
        name: newProduct.name.trim(),
        type: newProduct.type,
        price,
        qty,
        unit: newProduct.unit.trim(),
        minimum_qty: minimum,
        capacity_qty: capacity
      });
      setNewOpen(false);
      setNewProduct({
        name: '',
        type: 'comida',
        price: '',
        qty: '',
        unit: 'unidades',
        minimum_qty: '0',
        capacity_qty: ''
      });
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
    const capacity = editProduct.capacity_qty === ''
      ? null
      : Number(editProduct.capacity_qty);
    if (
      !editProduct.name.trim()
      || !Number.isInteger(price)
      || price <= 0
      || !editProduct.unit.trim()
      || !Number.isInteger(minimum)
      || minimum < 0
      || (
        capacity !== null
        && (
          !Number.isInteger(capacity)
          || capacity <= 0
        )
      )
    ) {
      toast.error('Revisá nombre, tipo, precio, unidad, mínimo y capacidad');
      return;
    }
    setSaving(true);
    try {
      await updateProduct(editProduct.id, {
        name: editProduct.name.trim(),
        type: editProduct.type,
        price,
        unit: editProduct.unit.trim(),
        minimum_qty: minimum,
        capacity_qty: capacity
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
      await adjustStock(
        adjustProduct.id,
        delta,
        adjustment.movementType,
        adjustment.note
      );
      setAdjustProduct(null);
      setAdjustment({
        quantity: '',
        direction: 'add',
        movementType: 'reposicion',
        note: ''
      });
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
    setAdjustment({
      ...adjustment,
      quantity: limitStockAdjustment(
        value,
        adjustment.direction,
        adjustProduct,
      ),
    });
  };

  const changeAdjustmentDirection = (
    direction: 'add' | 'subtract',
  ) => {
    setAdjustment({
      ...adjustment,
      quantity: '',
      direction,
      movementType: direction === 'add' ? 'reposicion' : 'merma',
    });
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

  const renderProducts = (type: ProductType) => {
    const filtered = products.filter(product => product.type === type);
    if (loading) return <p className="text-[#a0a0a0]">Cargando...</p>;
    if (!filtered.length) {
      return <p className="text-[#a0a0a0]">No hay productos en esta categoría.</p>;
    }
    return (
      <div className="grid md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
        {filtered.map(product => {
          const low = product.qty <= product.minimum_qty;
          const capacity = product.capacity_qty ?? Math.max(product.qty, 1);
          const level = Math.min(100, Math.round((product.qty / capacity) * 100));
          return (
            <Card
              key={product.id}
              className={`bg-[#1a1a1a] border-2 ${low ? 'border-red-500' : 'border-[#3a3a3a]'}`}
            >
              <CardHeader>
                <CardTitle className="text-[#f5f5dc] flex justify-between gap-2">
                  <span>{product.name}</span>
                  {isAdmin && (
                    <div className="flex">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setEditProduct({
                          ...product,
                          price: String(product.price),
                          minimum_qty: String(product.minimum_qty),
                          capacity_qty: product.capacity_qty === null
                            ? ''
                            : String(product.capacity_qty)
                        })}
                      >
                        <Edit className="w-4 h-4 text-[#D4AF37]" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => void removeProduct(product)}
                      >
                        <Trash2 className="w-4 h-4 text-red-500" />
                      </Button>
                    </div>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {low && (
                  <p className="text-red-400 flex gap-2 text-sm">
                    <AlertTriangle className="w-4 h-4" /> Stock bajo
                  </p>
                )}
                <div className="flex justify-between text-sm">
                  <span className="text-[#a0a0a0]">Disponible</span>
                  <span className="text-[#D4AF37] font-semibold">
                    {product.qty} {product.unit}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-[#a0a0a0]">Mínimo</span>
                  <span className="text-[#f5f5dc]">{product.minimum_qty}</span>
                </div>
                {product.type === 'cerveza' && (
                  <div>
                    <div className="flex justify-between text-xs text-[#a0a0a0]">
                      <span>Nivel</span><span>{level}%</span>
                    </div>
                    <div className="h-2 bg-[#3a3a3a] rounded mt-1">
                      <div
                        className="h-2 bg-[#D4AF37] rounded"
                        style={{ width: `${level}%` }}
                      />
                    </div>
                  </div>
                )}
                {isAdmin && (
                  <Button
                    className="w-full bg-[#D4AF37] text-[#0a0a0a]"
                    onClick={() => setAdjustProduct(product)}
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
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-[#D4AF37] mb-2">Control de Stock</h1>
          <p className="text-[#a0a0a0]">
            {lowStockCount} producto(s) requieren atención
          </p>
        </div>
        {isAdmin && (
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => void loadHistory()}>
              <History className="w-4 h-4 mr-2" /> Historial
            </Button>
            <Button
              onClick={() => setNewOpen(true)}
              className="bg-[#D4AF37] text-[#0a0a0a]"
            >
              <Plus className="w-4 h-4 mr-2" /> Nuevo producto
            </Button>
          </div>
        )}
      </div>

      <Tabs defaultValue="cerveza">
        <TabsList className="bg-[#1a1a1a]">
          {PRODUCT_TYPES.map(type => (
            <TabsTrigger key={type} value={type} className="capitalize">
              {type}
            </TabsTrigger>
          ))}
        </TabsList>
        {PRODUCT_TYPES.map(type => (
          <TabsContent key={type} value={type} className="mt-5">
            {renderProducts(type)}
          </TabsContent>
        ))}
      </Tabs>

      <Dialog open={newOpen} onOpenChange={setNewOpen}>
        <DialogContent className="bg-[#1a1a1a] border-[#3a3a3a]">
          <DialogHeader>
            <DialogTitle className="text-[#D4AF37]">Nuevo producto</DialogTitle>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-4">
            {[
              ['Nombre', 'name'],
              ['Precio', 'price'],
              ['Cantidad', 'qty'],
              ['Unidad', 'unit'],
              ['Mínimo', 'minimum_qty'],
              ['Capacidad', 'capacity_qty'],
            ].map(([label, key]) => (
              <div className="space-y-2" key={key}>
                <Label className="text-[#f5f5dc]">{label}</Label>
                <Input
                  type={['price', 'qty', 'minimum_qty', 'capacity_qty'].includes(key) ? 'number' : 'text'}
                  value={newProduct[key as keyof typeof newProduct]}
                  onChange={event => setNewProduct({
                    ...newProduct,
                    [key]: event.target.value
                  })}
                  className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
                />
              </div>
            ))}
            <div className="space-y-2 col-span-2">
              <Label className="text-[#f5f5dc]">Tipo</Label>
              <select
                value={newProduct.type}
                onChange={event => setNewProduct({
                  ...newProduct,
                  type: event.target.value as ProductType
                })}
                className="w-full h-9 bg-[#0a0a0a] border border-[#3a3a3a] text-[#f5f5dc] rounded px-3"
              >
                {PRODUCT_TYPES.map(type => <option key={type}>{type}</option>)}
              </select>
            </div>
            <Button
              onClick={() => void submitNewProduct()}
              disabled={saving}
              className="col-span-2 bg-[#D4AF37] text-[#0a0a0a]"
            >
              Crear
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={!!editProduct} onOpenChange={open => !open && setEditProduct(null)}>
        <DialogContent className="bg-[#1a1a1a] border-[#3a3a3a]">
          <DialogHeader><DialogTitle className="text-[#D4AF37]">Editar producto</DialogTitle></DialogHeader>
          {editProduct && (
            <div className="space-y-3">
              <Input value={editProduct.name} onChange={event => setEditProduct({ ...editProduct, name: event.target.value })} />
              <select
                value={editProduct.type}
                onChange={event => setEditProduct({
                  ...editProduct,
                  type: event.target.value as ProductType
                })}
                className="w-full h-9 bg-[#0a0a0a] border border-[#3a3a3a] text-[#f5f5dc] rounded px-3"
              >
                {PRODUCT_TYPES.map(type => <option key={type}>{type}</option>)}
              </select>
              <Input type="number" value={editProduct.price} onChange={event => setEditProduct({ ...editProduct, price: event.target.value })} />
              <Input value={editProduct.unit} onChange={event => setEditProduct({ ...editProduct, unit: event.target.value })} />
              <Input type="number" value={editProduct.minimum_qty} onChange={event => setEditProduct({ ...editProduct, minimum_qty: event.target.value })} />
              <Input
                type="number"
                placeholder="Capacidad opcional"
                value={editProduct.capacity_qty}
                onChange={event => setEditProduct({
                  ...editProduct,
                  capacity_qty: event.target.value
                })}
              />
              <Button onClick={() => void saveProduct()} disabled={saving} className="w-full bg-[#D4AF37] text-[#0a0a0a]">Guardar</Button>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={!!adjustProduct} onOpenChange={open => !open && setAdjustProduct(null)}>
        <DialogContent className="bg-[#1a1a1a] border-[#3a3a3a]">
          <DialogHeader>
            <DialogTitle className="text-[#D4AF37]">Ajustar {adjustProduct?.name}</DialogTitle>
            <DialogDescription className="text-[#a0a0a0]">
              Cada operación quedará registrada en el historial.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Input
              type="number"
              min="0"
              max={adjustmentMaximum}
              value={adjustment.quantity}
              onChange={event => updateAdjustmentQuantity(event.target.value)}
            />
            <p className="text-xs text-[#a0a0a0]">
              {adjustmentHint}
            </p>
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
          <Input placeholder="Nota" value={adjustment.note} onChange={event => setAdjustment({ ...adjustment, note: event.target.value })} />
          <Button onClick={() => void applyAdjustment()} disabled={saving} className="bg-[#D4AF37] text-[#0a0a0a]">Confirmar ajuste</Button>
        </DialogContent>
      </Dialog>

      <Dialog open={historyOpen} onOpenChange={setHistoryOpen}>
        <DialogContent className="bg-[#1a1a1a] border-[#3a3a3a] max-w-3xl max-h-[80vh] overflow-auto">
          <DialogHeader><DialogTitle className="text-[#D4AF37]">Movimientos de stock</DialogTitle></DialogHeader>
          <div className="space-y-2">
            {movements.map(movement => (
              <div key={movement.id} className="p-3 bg-[#2a2a2a] rounded flex justify-between">
                <div>
                  <p className="text-[#f5f5dc]">{movement.product_name}</p>
                  <p className="text-xs text-[#a0a0a0]">{movement.movement_type} · {new Date(movement.created_at).toLocaleString('es-AR')}</p>
                </div>
                <span className={movement.quantity_delta > 0 ? 'text-green-500' : 'text-red-400'}>
                  {movement.quantity_delta > 0 ? '+' : ''}{movement.quantity_delta}
                </span>
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
