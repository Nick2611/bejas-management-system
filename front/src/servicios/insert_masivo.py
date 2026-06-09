import pandas as pd
from datetime import date
from psycopg2.extras import execute_values
from dotenv import load_dotenv

hoy = date.today()
load_dotenv()


def limpiar_id(valor):  # Para la regla 2
    """Convierte el valor a string limpio:
    - NaN/None = ''
    - Elimina espacios
    - Elimina '.0' si aparece al final
    """
    if pd.isna(valor):
        return ""
    s = str(valor).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def insert_tiendas_db_masivo(df_prueba, conn):
    cursor = conn.cursor()

    # Obtiene todos los valores de la columna "Cod Tienda" los limpia con la función "limpiar_id" y los guarda en una lista
    cod_tiendas_u = [limpiar_id(c) for c in df_prueba["Cod Tienda"].unique()]

    # comprueba si la lista está vacía. Si está vacia la función termina.
    if not cod_tiendas_u:
        print("No hay tiendas")
        return

    # Mapeo de external_id a customer_location_id (SELECT todos los id de tabla customerlocation)
    """Se crea un diccionario vacío (id_map) para guardar el mapeo de external_id a customer_location_id
    Se genera una cadena de placeholders (%s, %s, %s...) para usar en la consulta SQL. El número de %s es igual a la cantidad de tiendas.
    Se ejecuta una unica consulta SELECT para buscar los id de la tabla customerlocation que coincidan con los external_id de la lista de tiendas. 
    El IN ({placeholders}) es para buscar varios valores en una sola operación."""
    id_map = {}
    placeholders = ", ".join(["%s"] * len(cod_tiendas_u))
    cursor.execute(
        f"SELECT external_id, id FROM public.customerlocation WHERE external_id IN ({placeholders})",
        cod_tiendas_u,
    )
    for (
        external_id,
        customer_id,
    ) in (
        cursor.fetchall()
    ):  # Se recorren los resultados de la consulta para llenar el diccionario id_map
        id_map[external_id] = customer_id

    # Eliminar en lote (una sola consulta DELETE masiva para todos los customer_location_id)
    """Se crea una lista con los id que se obtuvieron en id_map. 
    Si la lista no está vacía, se crea un string de placeholders para el DELETE y hacer una única operación DELETE de todos los registros de IDs en la lista. 
    cursor.rowcount devuelve el número de filas afectadas."""
    customer_ids_to_delete = list(id_map.values())
    if customer_ids_to_delete:
        delete_placeholders = ", ".join(["%s"] * len(customer_ids_to_delete))
        cursor.execute(
            f"DELETE FROM public.customerlocationstructure WHERE customer_location_id IN ({delete_placeholders})",
            customer_ids_to_delete,
        )
        print(f"{cursor.rowcount} registros eliminados.")

    # Limpiar los datos para INSERT masivo
    data_to_insert = []
    for _, fila in df_prueba.iterrows():
        cod_tienda = limpiar_id(fila["Cod Tienda"])
        cod_sector = limpiar_id(fila["Cod Sector"])
        desc_sector = str(fila["Desc Sector"]).strip()
        cod_zona = limpiar_id(fila["Cod Zona"])
        desc_zona = str(fila["Desc Zona"]).strip()

        if (
            cod_tienda in id_map
        ):  # se crea una tupla con todos los valores a insertar y se añade a la lista data_to_insert
            customer_location_id = id_map[cod_tienda]
            structure_level = "Zona" if desc_sector.upper() == "_TIENDA" else "Sector"

            if desc_sector.upper() == "_TIENDA":
                # Regla funcional: para filas EXPRESS se deben persistir ambos registros.
                # 1) Zona (cod_zona/desc_zona)
                # 2) Sector con _TIENDA (cod_sector/_TIENDA)
                # Si se inserta solo Zona, falta el Sector _TIENDA en customerlocationstructure.
                # tupla para insertar structure_level = Zona
                data_to_insert.append(
                    (
                        customer_location_id,
                        "Zona",
                        cod_zona,
                        desc_zona,
                        hoy,
                        hoy,
                        "9f0a1b2c-3d4e-4f6a-7b8c-9d0e1f2a3b4c",
                    )
                )

                # tupla para insertar structure_level = Sector con _TIENDA
                data_to_insert.append(
                    (
                        customer_location_id,
                        "Sector",
                        cod_sector,
                        desc_sector,
                        hoy,
                        hoy,
                        "9f0a1b2c-3d4e-4f6a-7b8c-9d0e1f2a3b4c",
                    )
                )
            else:
                # tupla para insertar structure_level =Sector
                data_to_insert.append(
                    (
                        customer_location_id,
                        structure_level,
                        cod_sector,
                        desc_sector,
                        hoy,
                        hoy,
                        "9f0a1b2c-3d4e-4f6a-7b8c-9d0e1f2a3b4c",
                    )
                )
        else:
            print(f"No se encontró customer_location_id con Cod Tienda: {cod_tienda}")

    # Insertar en lote (una sola llamada a `executemany`) (insert masivo)
    if data_to_insert:
        try:
            insert_query = """
            INSERT INTO public.customerlocationstructure
            (id, customer_location_id, structure_level, structure_code, structure_name, created_at, updated_at, deleted_at, created_by, updated_by)
            VALUES %s
            """
            execute_values(
                cursor,
                insert_query,
                data_to_insert,
                template="(gen_random_uuid(), %s, %s, %s, %s, %s, %s, NULL, %s, NULL)",
            )
            print(f"{len(data_to_insert)} registros insertados masivamente.")
        except Exception as e:
            conn.rollback()  # Deshago si algo falla
            print(f"Error durante el INSERT masivo: {e}")
            raise
    else:
        print("No hay datos para insertar.")

    conn.commit()
    cursor.close()
    # conn.close()
