"""
ETAPA 1 — INGESTA
Carga el dataset desde su fuente (CSV), muestra estadísticas iniciales
y guarda una copia sin modificar en /data/raw/.
"""

import pandas as pd
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("data/ingesta.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def cargar_dataset(ruta: str) -> pd.DataFrame:
    """Carga el CSV desde la ruta indicada."""
    logger.info(f"Leyendo dataset desde: {ruta}")
    df = pd.read_csv(ruta, encoding="utf-8-sig")
    logger.info(f"Dataset cargado: {df.shape[0]} filas × {df.shape[1]} columnas")
    logger.info(f"Columnas: {df.columns.tolist()}")
    return df


def mostrar_estadisticas(df: pd.DataFrame):
    """Muestra estadísticas básicas del raw dataset."""
    logger.info("── ESTADÍSTICAS DEL RAW DATASET ──")

    # Tipos de datos
    logger.info("Tipos de datos (dtypes):")
    for col, dtype in df.dtypes.items():
        logger.info(f"  {col}: {dtype}")

    # Conteo de nulos
    nulos = df.isnull().sum()
    nulos_existentes = nulos[nulos > 0]
    if nulos_existentes.empty:
        logger.info("Sin valores nulos.")
    else:
        logger.info("Valores nulos por columna:")
        for col, n in nulos_existentes.items():
            pct = round(n / len(df) * 100, 1)
            logger.info(f"  {col}: {n} nulos ({pct}%)")

    # Duplicados
    dupl = df.duplicated().sum()
    logger.info(f"Duplicados exactos: {dupl}")

    # Shape
    logger.info(f"Shape: {df.shape[0]} filas × {df.shape[1]} columnas")

    # Primeras filas
    logger.info("Primeras 3 filas:")
    logger.info(f"\n{df.head(3).to_string()}")


def guardar_raw(df: pd.DataFrame, destino: str):
    """Guarda el dataset sin modificar en /data/raw/."""
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    df.to_csv(destino, index=False, encoding="utf-8-sig")
    logger.info(f"Copia raw guardada en: {destino}")


def run() -> pd.DataFrame:
    logger.info("════════════════════════════════")
    logger.info("  ETAPA 1 — INGESTA")
    logger.info("════════════════════════════════")

    df = cargar_dataset("mascotas.csv")
    mostrar_estadisticas(df)
    guardar_raw(df, "data/raw/mascotas_raw.csv")

    logger.info("Etapa 1 completada.\n")
    return df


if __name__ == "__main__":
    run()
