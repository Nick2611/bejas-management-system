import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from './ui/dialog';
import { Beer, UtensilsCrossed, Edit, DollarSign, Plus, Trash2, Wine, Droplets } from 'lucide-react';
import { toast } from 'sonner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import {
  createProduct,
  deleteProduct,
  fetchProducts,
  updateProduct,
  type CreateProductRequest,
  type ProductType
} from '../services/productsApi';

type ConfigurableProductType = Exclude<ProductType, 'cerveza'>;
type NumericFieldValue = number | '';

const parseNumericField = (value: string): NumericFieldValue =>
  value === '' ? '' : Number(value);

interface Producto {
  id: string;
  nombre: string;
  precio: number;
  tipo: 'cerveza' | 'comida' | 'trago' | 'bebida';
  cantidad: number;
  unidad: string;
}

type EditingProducto = Omit<Producto, 'precio'> & {
  precio: NumericFieldValue;
};

interface CreateProductForm {
  name: string;
  price: NumericFieldValue;
  type: ProductType;
  qty: NumericFieldValue;
  unit: string;
}

export function Productos() {
  const [productos, setProductos] = useState<Producto[]>([]);
  const [editingProducto, setEditingProducto] =
    useState<EditingProducto | null>(null);
  const [nuevoProducto, setNuevoProducto] = useState<CreateProductForm>({
    name: '',
    price: '',
    type: 'comida',
    qty: '',
    unit: 'unidades'
  });
  const [creandoProducto, setCreandoProducto] = useState(false);
  const [actualizandoProducto, setActualizandoProducto] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [nuevoProductoDialogType, setNuevoProductoDialogType] = useState<ConfigurableProductType | null>(null);

  useEffect(() => {
    void cargarProductos();
  }, []);

  const cargarProductos = async () => {
    try {
      const productosDb = await fetchProducts();
      setProductos(productosDb.map(producto => ({
        id: String(producto.id),
        nombre: producto.name,
        precio: producto.price,
        tipo: producto.type,
        cantidad: producto.qty,
        unidad: producto.unit
      })));
    } catch (error) {
      setProductos([]);
      toast.error(error instanceof Error ? error.message : 'No se pudieron cargar los productos');
    }
  };

  const editarProducto = (producto: Producto) => {
    setEditingProducto({ ...producto });
    setEditDialogOpen(true);
  };

  const guardarCambios = async () => {
    if (!editingProducto) return;
    const price = Number(editingProducto.precio);

    if (!editingProducto.nombre.trim()) {
      toast.error('El nombre no puede estar vacío');
      return;
    }

    if (!Number.isInteger(price) || price <= 0) {
      toast.error('El precio debe ser mayor a 0');
      return;
    }

    if (!editingProducto.unidad.trim()) {
      toast.error('La unidad no puede estar vacía');
      return;
    }

    setActualizandoProducto(true);

    try {
      await updateProduct(Number(editingProducto.id), {
        name: editingProducto.nombre.trim(),
        type: editingProducto.tipo,
        price,
        unit: editingProducto.unidad.trim()
      });
      await cargarProductos();
      setEditDialogOpen(false);
      toast.success('Producto actualizado');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo actualizar el producto');
    } finally {
      setActualizandoProducto(false);
    }
  };

  const crearProducto = async () => {
    const price = Number(nuevoProducto.price);
    const qty = Number(nuevoProducto.qty);

    if (!nuevoProducto.name.trim()) {
      toast.error('El nombre no puede estar vacío');
      return;
    }

    if (!Number.isInteger(price) || price <= 0) {
      toast.error('El precio debe ser un número entero mayor a 0');
      return;
    }

    if (!Number.isInteger(qty) || qty <= 0) {
      toast.error('La cantidad debe ser un número entero mayor a 0');
      return;
    }

    if (!nuevoProducto.unit.trim()) {
      toast.error('La unidad no puede estar vacía');
      return;
    }

    const payload: CreateProductRequest = {
      name: nuevoProducto.name.trim(),
      type: nuevoProducto.type,
      price,
      qty,
      unit: nuevoProducto.unit.trim()
    };

    setCreandoProducto(true);

    try {
      await createProduct(payload);
      await cargarProductos();

      setNuevoProductoDialogType(null);
      setNuevoProducto({
        name: '',
        price: '',
        type: 'comida',
        qty: '',
        unit: 'unidades'
      });
      toast.success('Producto creado exitosamente');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo conectar con el backend');
    } finally {
      setCreandoProducto(false);
    }
  };

  const eliminarProducto = async (id: string) => {
    const producto = productos.find(p => p.id === id);

    if (!producto) return;
    try {
      await deleteProduct(Number(id));
      await cargarProductos();
      toast.success('Producto eliminado');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo eliminar el producto');
    }
  };

  const cervezas = productos.filter(p => p.tipo === 'cerveza');
  const comidas = productos.filter(p => p.tipo === 'comida');
  const tragos = productos.filter(p => p.tipo === 'trago');
  const bebidas = productos.filter(p => p.tipo === 'bebida');

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-[#D4AF37] mb-2">Configuración de Productos</h1>
        <p className="text-[#a0a0a0]">Gestiona los nombres y precios del menú</p>
      </div>

      <Tabs defaultValue="cervezas" className="space-y-6">
        <TabsList className="bg-[#1a1a1a] border border-[#3a3a3a]">
          <TabsTrigger 
            value="cervezas"
            className="data-[state=active]:bg-[#D4AF37] data-[state=active]:text-[#0a0a0a]"
          >
            <Beer className="w-4 h-4 mr-2" />
            Cervezas
          </TabsTrigger>
          <TabsTrigger 
            value="comidas"
            className="data-[state=active]:bg-[#D4AF37] data-[state=active]:text-[#0a0a0a]"
          >
            <UtensilsCrossed className="w-4 h-4 mr-2" />
            Comidas
          </TabsTrigger>
          <TabsTrigger 
            value="tragos"
            className="data-[state=active]:bg-[#D4AF37] data-[state=active]:text-[#0a0a0a]"
          >
            <Wine className="w-4 h-4 mr-2" />
            Tragos
          </TabsTrigger>
          <TabsTrigger 
            value="bebidas"
            className="data-[state=active]:bg-[#D4AF37] data-[state=active]:text-[#0a0a0a]"
          >
            <Droplets className="w-4 h-4 mr-2" />
            Bebidas
          </TabsTrigger>
        </TabsList>

        {/* Tab de Cervezas */}
        <TabsContent value="cervezas">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {cervezas.map((producto) => (
              <Card key={producto.id} className="bg-[#1a1a1a] border-2 border-[#3a3a3a]">
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    <span className="text-[#f5f5dc]">{producto.nombre}</span>
                    <Beer className="w-5 h-5 text-[#D4AF37]" />
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-center py-4">
                    <DollarSign className="w-6 h-6 text-[#D4AF37]" />
                    <span className="text-3xl text-[#D4AF37]">
                      {producto.precio.toLocaleString('es-AR')}
                    </span>
                  </div>
                  <Button
                    onClick={() => editarProducto(producto)}
                    className="w-full bg-[#D4AF37] hover:bg-[#B8860B] text-[#0a0a0a]"
                  >
                    <Edit className="w-4 h-4 mr-2" />
                    Editar
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Tab de Comidas */}
        <TabsContent value="comidas">
          <div className="mb-4 flex justify-end">
            <Dialog
              open={nuevoProductoDialogType === 'comida'}
              onOpenChange={(open) => {
                setNuevoProductoDialogType(open ? 'comida' : null);
                if (open) {
                  setNuevoProducto(current => ({
                    ...current,
                    type: 'comida',
                    unit: 'unidades'
                  }));
                }
              }}
            >
              <DialogTrigger asChild>
                <Button className="bg-[#D4AF37] hover:bg-[#B8860B] text-[#0a0a0a]">
                  <Plus className="w-4 h-4 mr-2" />
                  Nueva Comida
                </Button>
              </DialogTrigger>
              <DialogContent className="bg-[#1a1a1a] border-[#3a3a3a]">
                <DialogHeader>
                  <DialogTitle className="text-[#D4AF37]">Crear Nueva Comida</DialogTitle>
                  <DialogDescription className="text-[#a0a0a0]">
                    Agrega una nueva comida al menú
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label className="text-[#f5f5dc]">Nombre</Label>
                    <Input
                      type="text"
                      value={nuevoProducto.name}
                      onChange={(e) => setNuevoProducto({ ...nuevoProducto, name: e.target.value, type: 'comida' })}
                      className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
                      placeholder="Ej: Empanadas"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-[#f5f5dc]">Precio ($)</Label>
                    <Input
                      type="number"
                      min="1"
                      step="1"
                      value={nuevoProducto.price}
                      onChange={(e) => setNuevoProducto({
                        ...nuevoProducto,
                        price: parseNumericField(e.target.value)
                      })}
                      className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-[#f5f5dc]">Cantidad inicial</Label>
                    <Input
                      type="number"
                      min="1"
                      step="1"
                      value={nuevoProducto.qty}
                      onChange={(e) => setNuevoProducto({
                        ...nuevoProducto,
                        qty: parseNumericField(e.target.value)
                      })}
                      className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-[#f5f5dc]">Unidad</Label>
                    <Input
                      type="text"
                      value={nuevoProducto.unit}
                      onChange={(e) => setNuevoProducto({ ...nuevoProducto, unit: e.target.value })}
                      className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
                      placeholder="Ej: unidades"
                    />
                  </div>
                  <Button
                    onClick={crearProducto}
                    disabled={creandoProducto}
                    className="w-full bg-[#D4AF37] hover:bg-[#B8860B] text-[#0a0a0a]"
                  >
                    {creandoProducto ? 'Creando...' : 'Crear Comida'}
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {comidas.map((producto) => (
              <Card key={producto.id} className="bg-[#1a1a1a] border-2 border-[#3a3a3a]">
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    <span className="text-[#f5f5dc]">{producto.nombre}</span>
                    <div className="flex gap-2">
                      <Button
                        onClick={() => void eliminarProducto(producto.id)}
                        size="sm"
                        variant="ghost"
                        className="text-red-500 hover:bg-[#3a3a3a]"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                      <UtensilsCrossed className="w-5 h-5 text-[#D4AF37]" />
                    </div>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-center py-4">
                    <DollarSign className="w-6 h-6 text-[#D4AF37]" />
                    <span className="text-3xl text-[#D4AF37]">
                      {producto.precio.toLocaleString('es-AR')}
                    </span>
                  </div>
                  <Button
                    onClick={() => editarProducto(producto)}
                    className="w-full bg-[#D4AF37] hover:bg-[#B8860B] text-[#0a0a0a]"
                  >
                    <Edit className="w-4 h-4 mr-2" />
                    Editar
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Tab de Tragos */}
        <TabsContent value="tragos">
          <div className="mb-4 flex justify-end">
            <Dialog
              open={nuevoProductoDialogType === 'trago'}
              onOpenChange={(open) => {
                setNuevoProductoDialogType(open ? 'trago' : null);
                if (open) {
                  setNuevoProducto(current => ({
                    ...current,
                    type: 'trago',
                    unit: 'botellas'
                  }));
                }
              }}
            >
              <DialogTrigger asChild>
                <Button className="bg-[#D4AF37] hover:bg-[#B8860B] text-[#0a0a0a]">
                  <Plus className="w-4 h-4 mr-2" />
                  Nuevo Trago
                </Button>
              </DialogTrigger>
              <DialogContent className="bg-[#1a1a1a] border-[#3a3a3a]">
                <DialogHeader>
                  <DialogTitle className="text-[#D4AF37]">Crear Nuevo Trago</DialogTitle>
                  <DialogDescription className="text-[#a0a0a0]">
                    Agrega un nuevo trago al menú
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label className="text-[#f5f5dc]">Nombre</Label>
                    <Input
                      type="text"
                      value={nuevoProducto.name}
                      onChange={(e) => setNuevoProducto({ ...nuevoProducto, name: e.target.value, type: 'trago' })}
                      className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
                      placeholder="Ej: Mojito"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-[#f5f5dc]">Precio ($)</Label>
                    <Input
                      type="number"
                      min="1"
                      step="1"
                      value={nuevoProducto.price}
                      onChange={(e) => setNuevoProducto({
                        ...nuevoProducto,
                        price: parseNumericField(e.target.value)
                      })}
                      className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-[#f5f5dc]">Cantidad inicial</Label>
                    <Input
                      type="number"
                      min="1"
                      step="1"
                      value={nuevoProducto.qty}
                      onChange={(e) => setNuevoProducto({
                        ...nuevoProducto,
                        qty: parseNumericField(e.target.value)
                      })}
                      className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-[#f5f5dc]">Unidad</Label>
                    <Input
                      type="text"
                      value={nuevoProducto.unit}
                      onChange={(e) => setNuevoProducto({ ...nuevoProducto, unit: e.target.value })}
                      className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
                      placeholder="Ej: botellas"
                    />
                  </div>
                  <Button
                    onClick={crearProducto}
                    disabled={creandoProducto}
                    className="w-full bg-[#D4AF37] hover:bg-[#B8860B] text-[#0a0a0a]"
                  >
                    {creandoProducto ? 'Creando...' : 'Crear Trago'}
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {tragos.map((producto) => (
              <Card key={producto.id} className="bg-[#1a1a1a] border-2 border-[#3a3a3a]">
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    <span className="text-[#f5f5dc]">{producto.nombre}</span>
                    <div className="flex gap-2">
                      <Button
                        onClick={() => void eliminarProducto(producto.id)}
                        size="sm"
                        variant="ghost"
                        className="text-red-500 hover:bg-[#3a3a3a]"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                      <Wine className="w-5 h-5 text-[#D4AF37]" />
                    </div>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-center py-4">
                    <DollarSign className="w-6 h-6 text-[#D4AF37]" />
                    <span className="text-3xl text-[#D4AF37]">
                      {producto.precio.toLocaleString('es-AR')}
                    </span>
                  </div>
                  <Button
                    onClick={() => editarProducto(producto)}
                    className="w-full bg-[#D4AF37] hover:bg-[#B8860B] text-[#0a0a0a]"
                  >
                    <Edit className="w-4 h-4 mr-2" />
                    Editar
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Tab de Bebidas */}
        <TabsContent value="bebidas">
          <div className="mb-4 flex justify-end">
            <Dialog
              open={nuevoProductoDialogType === 'bebida'}
              onOpenChange={(open) => {
                setNuevoProductoDialogType(open ? 'bebida' : null);
                if (open) {
                  setNuevoProducto(current => ({
                    ...current,
                    type: 'bebida',
                    unit: 'unidades'
                  }));
                }
              }}
            >
              <DialogTrigger asChild>
                <Button className="bg-[#D4AF37] hover:bg-[#B8860B] text-[#0a0a0a]">
                  <Plus className="w-4 h-4 mr-2" />
                  Nueva Bebida
                </Button>
              </DialogTrigger>
              <DialogContent className="bg-[#1a1a1a] border-[#3a3a3a]">
                <DialogHeader>
                  <DialogTitle className="text-[#D4AF37]">Crear Nueva Bebida</DialogTitle>
                  <DialogDescription className="text-[#a0a0a0]">
                    Agrega una nueva bebida al menú
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label className="text-[#f5f5dc]">Nombre</Label>
                    <Input
                      type="text"
                      value={nuevoProducto.name}
                      onChange={(e) => setNuevoProducto({ ...nuevoProducto, name: e.target.value, type: 'bebida' })}
                      className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
                      placeholder="Ej: Agua con Gas"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-[#f5f5dc]">Precio ($)</Label>
                    <Input
                      type="number"
                      min="1"
                      step="1"
                      value={nuevoProducto.price}
                      onChange={(e) => setNuevoProducto({
                        ...nuevoProducto,
                        price: parseNumericField(e.target.value)
                      })}
                      className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-[#f5f5dc]">Cantidad inicial</Label>
                    <Input
                      type="number"
                      min="1"
                      step="1"
                      value={nuevoProducto.qty}
                      onChange={(e) => setNuevoProducto({
                        ...nuevoProducto,
                        qty: parseNumericField(e.target.value)
                      })}
                      className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-[#f5f5dc]">Unidad</Label>
                    <Input
                      type="text"
                      value={nuevoProducto.unit}
                      onChange={(e) => setNuevoProducto({ ...nuevoProducto, unit: e.target.value })}
                      className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
                      placeholder="Ej: unidades"
                    />
                  </div>
                  <Button
                    onClick={crearProducto}
                    disabled={creandoProducto}
                    className="w-full bg-[#D4AF37] hover:bg-[#B8860B] text-[#0a0a0a]"
                  >
                    {creandoProducto ? 'Creando...' : 'Crear Bebida'}
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {bebidas.map((producto) => (
              <Card key={producto.id} className="bg-[#1a1a1a] border-2 border-[#3a3a3a]">
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    <span className="text-[#f5f5dc]">{producto.nombre}</span>
                    <div className="flex gap-2">
                      <Button
                        onClick={() => void eliminarProducto(producto.id)}
                        size="sm"
                        variant="ghost"
                        className="text-red-500 hover:bg-[#3a3a3a]"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                      <Droplets className="w-5 h-5 text-[#D4AF37]" />
                    </div>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-center py-4">
                    <DollarSign className="w-6 h-6 text-[#D4AF37]" />
                    <span className="text-3xl text-[#D4AF37]">
                      {producto.precio.toLocaleString('es-AR')}
                    </span>
                  </div>
                  <Button
                    onClick={() => editarProducto(producto)}
                    className="w-full bg-[#D4AF37] hover:bg-[#B8860B] text-[#0a0a0a]"
                  >
                    <Edit className="w-4 h-4 mr-2" />
                    Editar
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>
      </Tabs>

      {/* Diálogo de Edición */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="bg-[#1a1a1a] border-[#3a3a3a]">
          <DialogHeader>
            <DialogTitle className="text-[#D4AF37]\">Editar Producto</DialogTitle>
            <DialogDescription className="text-[#a0a0a0]">
              Modifica los datos comerciales. El stock se ajusta desde Stock.
            </DialogDescription>
          </DialogHeader>
          {editingProducto && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label className="text-[#f5f5dc]">Nombre</Label>
                <Input
                  type="text"
                  value={editingProducto.nombre}
                  onChange={(e) => setEditingProducto({ ...editingProducto, nombre: e.target.value })}
                  className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-[#f5f5dc]">Precio ($)</Label>
                <Input
                  type="number"
                  value={editingProducto.precio}
                  onChange={(e) => setEditingProducto({
                    ...editingProducto,
                    precio: parseNumericField(e.target.value)
                  })}
                  className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-[#f5f5dc]">Tipo</Label>
                <Select
                  value={editingProducto.tipo}
                  onValueChange={(value) => setEditingProducto({
                    ...editingProducto,
                    tipo: value as ProductType
                  })}
                >
                  <SelectTrigger className="bg-[#0a0a0a] border-[#3a3a3a] text-[#f5f5dc]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="cerveza">Cerveza</SelectItem>
                    <SelectItem value="comida">Comida</SelectItem>
                    <SelectItem value="trago">Trago</SelectItem>
                    <SelectItem value="bebida">Bebida</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-[#f5f5dc]">Unidad</Label>
                <Input
                  type="text"
                  value={editingProducto.unidad}
                  onChange={(e) => setEditingProducto({
                    ...editingProducto,
                    unidad: e.target.value
                  })}
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
                  onClick={guardarCambios}
                  disabled={actualizandoProducto}
                  className="bg-[#D4AF37] hover:bg-[#B8860B] text-[#0a0a0a]"
                >
                  {actualizandoProducto ? 'Guardando...' : 'Guardar Cambios'}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
