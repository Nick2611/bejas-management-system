import shutil
from pathlib import Path
import os


def guardar_en_proceso(nombre_archivo: str) -> str:
    origen = Path(nombre_archivo)
    destino = Path("EnProceso") / origen.name
    os.makedirs(destino.parent, exist_ok=True)  # asegurar que exista la carpeta
    shutil.copy(origen, destino)  # o .move si querés quitarlo del origen
    return str(destino)


def finalizar_archivo(ruta_archivo: str):
    origen = Path(ruta_archivo)
    destino = Path("Historicos") / origen.name
    os.makedirs(destino.parent, exist_ok=True)
    shutil.move(origen, destino)
