"""
ETAPA 2 — LIMPIEZA Y TRANSFORMACIÓN
Trata duplicados, nulos, errores de formato y aplica transformaciones.
Guarda el resultado en /data/clean/.
"""

import pandas as pd
import numpy as np
import os
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("data/limpieza.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# LIMPIEZA
# ─────────────────────────────────────────────

def eliminar_duplicados(df: pd.DataFrame) -> pd.DataFrame:
    """
    Elimina filas completamente vacías y duplicados exactos.
    Criterio: si todas las columnas son iguales, es un duplicado real.
    """
    antes = len(df)
    df = df.dropna(how="all")
    df = df.drop_duplicates()
    eliminadas = antes - len(df)
    logger.info(f"Duplicados/filas vacías eliminados: {eliminadas} | Restantes: {len(df)}")
    return df.reset_index(drop=True)


def estandarizar_especie(df: pd.DataFrame) -> pd.DataFrame:
    """
    Unifica variantes de especie (GATO, gata, Cat → gato, etc.).
    Criterio: el dataset tiene las mismas especies escritas de formas distintas;
    se unifican a minúsculas con un diccionario controlado.
    """
    mapa = {
        "gato": "gato", "gata": "gato", "GATO": "gato", "GATA": "gato",
        "cat": "gato", "Cat": "gato",
        "perro": "perro", "Perro": "perro", "PERRO": "perro",
        "perra": "perro", "PERRA": "perro",
        "loro": "loro", "Loro": "loro",
        "pez": "pez"
    }
    antes = df["especie"].value_counts(dropna=False).to_dict()
    df["especie"] = df["especie"].map(mapa).fillna(df["especie"].str.lower())
    despues = df["especie"].value_counts(dropna=False).to_dict()
    logger.info(f"Especie antes: {antes}")
    logger.info(f"Especie después: {despues}")
    return df


def imputar_edad(df: pd.DataFrame) -> pd.DataFrame:
    """
    Edades negativas → NaN (imposibles biológicamente).
    Nulos → mediana de la misma especie (preserva la distribución por tipo de animal).
    """
    nulos_antes = df["edad_años"].isnull().sum()
    df.loc[df["edad_años"] < 0, "edad_años"] = np.nan
    medianas = df.groupby("especie")["edad_años"].median()
    df["edad_años"] = df.apply(
        lambda r: medianas.get(r["especie"], df["edad_años"].median())
        if pd.isna(r["edad_años"]) else r["edad_años"],
        axis=1
    )
    nulos_despues = df["edad_años"].isnull().sum()
    logger.info(f"edad_años — nulos antes: {nulos_antes} | después: {nulos_despues}")
    return df


def corregir_pesos(df: pd.DataFrame) -> pd.DataFrame:
    """
    Pesos > 200 kg son imposibles para mascotas domésticas → se reemplazan
    con la mediana del peso de su especie.
    """
    imposibles = (df["peso_kg"] > 200).sum()
    df.loc[df["peso_kg"] > 200, "peso_kg"] = np.nan
    medianas = df.groupby("especie")["peso_kg"].median()
    df["peso_kg"] = df.apply(
        lambda r: medianas.get(r["especie"], df["peso_kg"].median())
        if pd.isna(r["peso_kg"]) else r["peso_kg"],
        axis=1
    )
    logger.info(f"Pesos imposibles corregidos: {imposibles} | Nulos restantes: {df['peso_kg'].isnull().sum()}")
    return df


def corregir_fechas(df: pd.DataFrame) -> pd.DataFrame:
    """
    El dataset tiene fechas en 3 formatos distintos (%Y-%m-%d, %d/%m/%Y, %Y%m%d).
    Se prueba cada formato hasta que uno funcione.
    """
    formatos = ["%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"]

    def parsear(valor):
        if pd.isna(valor):
            return pd.NaT
        for fmt in formatos:
            try:
                return datetime.strptime(str(valor).strip(), fmt)
            except ValueError:
                continue
        return pd.NaT

    df["fecha_consulta"] = df["fecha_consulta"].apply(parsear)
    nulos = df["fecha_consulta"].isna().sum()
    logger.info(f"Fechas no parseables (quedan como NaT): {nulos}")
    return df


# ─────────────────────────────────────────────
# TRANSFORMACIONES
# ─────────────────────────────────────────────

def crear_rango_peso(df: pd.DataFrame) -> pd.DataFrame:
    """
    TRANSFORMACIÓN 1 — Columna derivada 'rango_peso'.
    Clasifica cada mascota en bajo/normal/alto/obeso según rangos veterinarios
    por especie. Útil para análisis clínico rápido.
    """
    rangos = {
        "perro": (5, 40, 60),
        "gato": (2, 6, 8),
        "loro": (0.1, 0.5, 1),
        "pez":  (0.01, 0.1, 0.5),
    }

    def clasificar(row):
        bajo, normal_max, alto_max = rangos.get(row["especie"], (1, 20, 40))
        if pd.isna(row["peso_kg"]):
            return "desconocido"
        if row["peso_kg"] < bajo:
            return "bajo"
        elif row["peso_kg"] <= normal_max:
            return "normal"
        elif row["peso_kg"] <= alto_max:
            return "alto"
        else:
            return "obeso"

    df["rango_peso"] = df.apply(clasificar, axis=1)
    logger.info(f"rango_peso → {df['rango_peso'].value_counts().to_dict()}")
    return df


def extraer_fecha_componentes(df: pd.DataFrame) -> pd.DataFrame:
    """
    TRANSFORMACIÓN 2 — Extrae mes y año de fecha_consulta.
    Permite agrupar consultas por período sin transformar toda la fecha.
    """
    df["mes_consulta"] = df["fecha_consulta"].dt.month
    df["año_consulta"] = df["fecha_consulta"].dt.year
    rango = f"{df['fecha_consulta'].min()} → {df['fecha_consulta'].max()}"
    logger.info(f"mes_consulta y año_consulta creados. Rango fechas: {rango}")
    return df


def encoding_especie(df: pd.DataFrame) -> pd.DataFrame:
    """
    TRANSFORMACIÓN 3 — One-hot encoding de especie.
    Convierte la variable categórica en columnas binarias (0/1) para uso en
    modelos de ML o análisis estadístico.
    """
    dummies = pd.get_dummies(df["especie"], prefix="especie", dtype=int)
    df = pd.concat([df, dummies], axis=1)
    logger.info(f"Dummies creados: {list(dummies.columns)}")
    return df


def calcular_años_cliente(df: pd.DataFrame) -> pd.DataFrame:
    """
    TRANSFORMACIÓN 4 — 'años_cliente': cuántos años lleva el dueño
    en la clínica (desde su primera consulta registrada).
    """
    primera_visita = (
        df.dropna(subset=["dueño_email", "fecha_consulta"])
        .groupby("dueño_email")["fecha_consulta"]
        .min()
        .rename("primera_visita")
    )
    df = df.merge(primera_visita, on="dueño_email", how="left")
    df["años_cliente"] = (
        (df["fecha_consulta"] - df["primera_visita"]).dt.days / 365.25
    ).round(2).fillna(0)
    df = df.drop(columns=["primera_visita"])
    logger.info(f"años_cliente → min: {df['años_cliente'].min()} | max: {df['años_cliente'].max()}")
    return df


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def run(df: pd.DataFrame = None) -> pd.DataFrame:
    logger.info("════════════════════════════════")
    logger.info("  ETAPA 2 — LIMPIEZA Y TRANSFORMACIÓN")
    logger.info("════════════════════════════════")

    if df is None:
        df = pd.read_csv("data/raw/mascotas_raw.csv", encoding="utf-8-sig")
        logger.info(f"Cargado desde data/raw/mascotas_raw.csv: {df.shape}")

    # Limpieza
    df = eliminar_duplicados(df)
    df = estandarizar_especie(df)
    df = imputar_edad(df)
    df = corregir_pesos(df)
    df = corregir_fechas(df)

    # Transformaciones
    df = crear_rango_peso(df)
    df = extraer_fecha_componentes(df)
    df = encoding_especie(df)
    df = calcular_años_cliente(df)

    # Guardar
    os.makedirs("data/clean", exist_ok=True)
    destino = "data/clean/mascotas_clean.csv"
    df.to_csv(destino, index=False, encoding="utf-8-sig")
    logger.info(f"Dataset limpio guardado en: {destino} ({df.shape[0]} filas × {df.shape[1]} columnas)")
    logger.info("Etapa 2 completada.\n")

    return df


if __name__ == "__main__":
    run()
