from pathlib import Path
import os
import logging
from contextlib import contextmanager

import pandas as pd
import psycopg2
from dotenv import load_dotenv

from servicios import reglas, insert_masivo
from servicios.MK_BOXFunctions import returnClient, download_items_of_folder, removefile

from servicios.fn_archivos import (
    convertir_csv_a_xlsx,
    INPUT_DIR,
    eliminar_xlsx_de_input,
    leer_excel_con_reintentos,
)
# ==========================================
# CONFIGURACIÓN
# ==========================================

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


# ==========================================
# UTILIDADES
# ==========================================
def load_environment() -> dict:
    env_path = Path(__file__).resolve().parent / "utils" / ".env"
    load_dotenv(dotenv_path=env_path)

    required_vars = [
        "DB_USER",
        "DB_PASS",
        "DB_HOST",
        "DB_NAME",
        "DB_PORT",
        "CUSTOMER_ID",
        "BOXCLIENTID",
        "BOXCLIENTSECRET",
        "BOXENTERPRISEID",
        "BOXIDMAINFOLDER",
    ]
    config = {}

    for var in required_vars:
        value = os.getenv(var)
        if not value:
            raise ValueError(f"Variable de entorno requerida no encontrada: {var}")
        config[var] = value

    return config


@contextmanager
def get_connection(config: dict):
    conn = psycopg2.connect(
        host=config["DB_HOST"],
        dbname=config["DB_NAME"],
        user=config["DB_USER"],
        password=config["DB_PASS"],
        port=config["DB_PORT"],
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
        logging.info("Conexión cerrada.")


def obtener_archivo_excel() -> Path:
    convertir_csv_a_xlsx()
    archivos = list(INPUT_DIR.glob("*.xlsx"))
    print("INPUT_DIR: ", INPUT_DIR)
    print("archivos encontrados: ", archivos)
    if not archivos:
        raise FileNotFoundError("No se encontró ningún archivo Excel en data/input")

    # Retorna el archivo Excel más reciente
    return max(archivos, key=lambda f: f.stat().st_mtime)


# ==========================================
# CAPA DE DATOS
# ==========================================


def obtener_customer_locations(conn, customer_id: str) -> pd.DataFrame:
    query = """
        SELECT *
        FROM customerlocation
        WHERE customer_id = %s
          AND customer_location_status = 'Activa'
          AND deleted_at IS NULL
        ORDER BY external_id
    """

    return pd.read_sql(query, conn, params=[customer_id])


# ==========================================
# PROCESAMIENTO
# ==========================================


def aplicar_reglas(df_ssf: pd.DataFrame, df_customer: pd.DataFrame) -> pd.DataFrame:
    reglas_pipeline = [
        reglas.regla_codigo_tienda,
        lambda df: reglas.regla_es_tienda(df, df_customer),
        lambda df: reglas.regla_obtener_id_tienda(df, df_customer),
        lambda df: reglas.regla_nombre_tienda(df, df_customer),
        lambda df: reglas.regla_formato_tienda(df, df_customer),
        reglas.regla_sector_padre,
        reglas.regla_codigo_sector_padre,
        reglas.regla_sector,
        reglas.regla_codigo_sector,
        reglas.regla_descripcion_sector,
        reglas.regla_codigo_zona,
        reglas.regla_descripcion_zona,
    ]

    for regla in reglas_pipeline:
        df_ssf = regla(df_ssf)

    return df_ssf


def validar_tiendas(df: pd.DataFrame) -> pd.DataFrame:
    df_validado = df[
        (df["Es Tienda"]) & (df["Cod Sector"].notna()) & (df["Desc Sector"].notna())
    ]

    logging.info(f"Filas validadas: {len(df_validado)}")
    return df_validado


# ==========================================
# CASO DE USO PRINCIPAL
# ==========================================


def procesar_customer(customer_id: str, conn):
    logging.info(f"Procesando customer_id: {customer_id}")

    # Obtener datos BD
    df_customer = obtener_customer_locations(conn, customer_id)

    # Leer Excel
    archivo_excel = obtener_archivo_excel()
    df_ssf = leer_excel_con_reintentos(archivo_excel)
    df_ssf.columns = df_ssf.columns.str.strip()

    # Aplicar reglas
    df_procesado = aplicar_reglas(df_ssf, df_customer)

    # 4Validar
    df_validado = validar_tiendas(df_procesado)

    # Insert masivo
    insert_masivo.insert_tiendas_db_masivo(df_validado, conn)

    logging.info(f"Customer {customer_id} procesado correctamente.")


# ==========================================
# MAIN
# ==========================================


def main():
    config = load_environment()
    customer_id = config["CUSTOMER_ID"]
    id_main_folder = config["BOXIDMAINFOLDER"]

    client = returnClient()
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    items_downloaded = download_items_of_folder(client, id_main_folder, str(INPUT_DIR))

    if not items_downloaded:
        logging.error("No se encontraron archivos para descargar en Box.")
        exit(-1)

    try:
        with get_connection(config) as conn:
            procesar_customer(customer_id, conn)

        print("Proceso finalizado exitosamente.")

        for item in items_downloaded:
            print("item_to_remove: ", item)
            removefile(client, item)

        eliminar_xlsx_de_input()

        logging.info(
            "Archivos procesados y eliminados de Box correctamente. Proceso completo."
        )
    except Exception as e:
        logging.error(f"Error durante el procesamiento: {e}")
        exit(-1)


if __name__ == "__main__":
    main()
