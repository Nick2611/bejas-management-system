import { Productos } from './Productos';
import { UserManagement } from './UserManagement';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';


export function Configuracion() {
  return (
    <Tabs defaultValue="productos" className="p-4">
      <TabsList className="bg-[#1a1a1a] border border-[#3a3a3a]">
        <TabsTrigger value="productos">Productos</TabsTrigger>
        <TabsTrigger value="usuarios">Usuarios</TabsTrigger>
      </TabsList>
      <TabsContent value="productos"><Productos /></TabsContent>
      <TabsContent value="usuarios"><UserManagement /></TabsContent>
    </Tabs>
  );
}
