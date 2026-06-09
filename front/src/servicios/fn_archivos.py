from pathlib import Path
import logging
import pandas as pd
import time
from zipfile import BadZipFile

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
INPUT_DIR = DATA_DIR / "input"
CSV_DELIMITERS = [";", ","]
CSV_ENCODINGS = ["utf-8-sig", "latin-1"]


def obtener_csv_mas_reciente() -> Path | None:
    csv_files = list(DATA_DIR.glob("*.csv")) + list(INPUT_DIR.glob("*.csv"))
    if not csv_files:
        return None
    return max(csv_files, key=lambda f: f.stat().st_mtime)


def leer_csv_con_fallback(archivo_csv: Path) -> pd.DataFrame:
    errores: list[str] = []

    try:
        for encoding in CSV_ENCODINGS:
            for delimitador in CSV_DELIMITERS:
                try:
                    return pd.read_csv(
                        archivo_csv,
                        sep=delimitador,
                        engine="python",
                        encoding=encoding,
                        header=None,
                    )
                except (UnicodeDecodeError, pd.errors.ParserError) as e:
                    errores.append(
                        f"sep='{delimitador}', encoding='{encoding}': {type(e).__name__}"
                    )
    except pd.errors.EmptyDataError as e:
        raise ValueError(f"El CSV esta vacio: {archivo_csv}") from e
    except PermissionError as e:
        raise ValueError(f"Sin permisos para leer el archivo CSV: {archivo_csv}") from e
    except FileNotFoundError as e:
        raise ValueError(f"No se encontro el archivo CSV: {archivo_csv}") from e
    except OSError as e:
        raise ValueError(f"Error de entrada/salida leyendo CSV: {archivo_csv}") from e

    raise ValueError(
        "No se pudo leer el CSV con los delimitadores soportados. "
        f"Intentos: {', '.join(errores)}"
    )


def convertir_csv_a_xlsx() -> Path | None:
    archivo_csv = obtener_csv_mas_reciente()
    if archivo_csv is None:
        return None

    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    archivo_xlsx = INPUT_DIR / f"{archivo_csv.stem}.xlsx"

    if (
        archivo_xlsx.exists()
        and archivo_xlsx.stat().st_mtime >= archivo_csv.stat().st_mtime
    ):
        logging.info(f"Se reutiliza XLSX existente: {archivo_xlsx.name}")
        return archivo_xlsx

    df_csv = leer_csv_con_fallback(archivo_csv)
    df_csv.to_excel(archivo_xlsx, index=False, header=False)
    logging.info(f"CSV convertido a XLSX: {archivo_csv.name} -> {archivo_xlsx.name}")
    return archivo_xlsx


def eliminar_xlsx_de_input() -> int:
    xlsx_files = list(INPUT_DIR.glob("*.xlsx"))
    eliminados = 0

    for archivo in xlsx_files:
        try:
            archivo.unlink()
            eliminados += 1
        except OSError as e:
            logging.warning(f"No se pudo eliminar {archivo.name}: {e}")

    logging.info(f"Archivos XLSX eliminados de input: {eliminados}")
    return eliminados


def leer_excel_con_reintentos(
    archivo_excel: Path,
    intentos: int = 6,
    espera_segundos: float = 2.0,
) -> pd.DataFrame:

    last_error = None

    for intento in range(1, intentos + 1):
        try:
            if not archivo_excel.exists():
                raise FileNotFoundError(
                    f"El archivo no existe o no está disponible: {archivo_excel}"
                )

            # Lectura mínima para detectar bloqueo de permisos antes del parseo.
            with archivo_excel.open("rb") as f:
                _ = f.read(1)

            for skip in (1, 2):
                df_ssf = pd.read_excel(
                    archivo_excel,
                    sheet_name=0,
                    usecols="A:J",
                    skiprows=skip,
                )

                if encabezados_validos(df_ssf.columns):
                    logging.info("Excel leído con skiprows=%s", skip)
                    return df_ssf

                logging.warning(
                    "Encabezados no válidos con skiprows=%s. Se probará otro valor.",
                    skip,
                )

            raise ValueError(
                "No se encontraron encabezados válidos con skiprows=1 ni skiprows=2."
            )
        except (PermissionError, OSError, BadZipFile, ValueError) as exc:
            last_error = exc
            logging.warning(
                "No se pudo leer el Excel (intento %s/%s): %s",
                intento,
                intentos,
                exc,
            )
            if intento < intentos:
                time.sleep(espera_segundos)

    raise RuntimeError(
        "No fue posible leer el archivo Excel. Puede estar bloqueado, en Vista protegida o aún en descarga. "
        "Cierra Excel, desbloquea el archivo y vuelve a intentar."
    ) from last_error


def encabezados_validos(columnas: pd.Index) -> bool:
    columnas_limpias = [str(col).strip() for col in columnas]
    if not columnas_limpias:
        return False

    return any(
        col and col.lower() != "nan" and not col.lower().startswith("unnamed:")
        for col in columnas_limpias
    )
