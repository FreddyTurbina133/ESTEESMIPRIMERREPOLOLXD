import pandas as pd
import numpy as np
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("pipeline.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def cargar_datos():
    logger.info("Cargando el archivo mascotas.csv")
    df = pd.read_csv("mascotas.csv")
    logger.info(f"Se cargaron {df.shape[0]} filas y {df.shape[1]} columnas")
    return df


def detectar_problemas(df):
    logger.info("Buscando duplicados...")
    duplicados = df.duplicated().sum()
    logger.info(f"Duplicados encontrados: {duplicados}")

    logger.info("Contando nulos por columna...")
    nulos = df.isnull().sum()
    for col, n in nulos[nulos > 0].items():
        logger.info(f"  {col}: {n} nulos")

    logger.info("Revisando outliers en peso_kg...")
    raros = df[df["peso_kg"] > 200]
    for _, row in raros.iterrows():
        logger.info(f"  {row['nombre']} tiene {row['peso_kg']}kg, parece un error")


def limpiar_datos(df):
    # eliminar filas vacias
    df = df.dropna(how="all")
    df = df.drop_duplicates()
    logger.info(f"Filas despues de eliminar duplicados y vacias: {len(df)}")

    # estandarizar especie
    mapa_especie = {
        "gato": "gato", "gata": "gato", "GATO": "gato", "GATA": "gato",
        "cat": "gato", "Cat": "gato",
        "perro": "perro", "Perro": "perro", "PERRO": "perro",
        "perra": "perro", "PERRA": "perro",
        "loro": "loro", "Loro": "loro",
        "pez": "pez"
    }
    df["especie"] = df["especie"].map(mapa_especie).fillna(df["especie"].str.lower())
    logger.info(f"Especies despues de estandarizar: {df['especie'].unique()}")

    # corregir edades negativas e imputar nulos
    df.loc[df["edad_años"] < 0, "edad_años"] = np.nan
    medianas_edad = df.groupby("especie")["edad_años"].median()
    df["edad_años"] = df.apply(
        lambda row: medianas_edad.get(row["especie"], df["edad_años"].median())
        if pd.isna(row["edad_años"]) else row["edad_años"],
        axis=1
    )
    logger.info(f"Nulos en edad_años despues de imputar: {df['edad_años'].isnull().sum()}")

    # corregir pesos imposibles
    df.loc[df["peso_kg"] > 200, "peso_kg"] = np.nan
    medianas_peso = df.groupby("especie")["peso_kg"].median()
    df["peso_kg"] = df.apply(
        lambda row: medianas_peso.get(row["especie"], df["peso_kg"].median())
        if pd.isna(row["peso_kg"]) else row["peso_kg"],
        axis=1
    )
    logger.info(f"Nulos en peso_kg despues de imputar: {df['peso_kg'].isnull().sum()}")

    # corregir fechas
    formatos = ["%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"]
    def parsear_fecha(valor):
        if pd.isna(valor):
            return pd.NaT
        for fmt in formatos:
            try:
                return datetime.strptime(str(valor).strip(), fmt)
            except ValueError:
                continue
        return pd.NaT

    df["fecha_consulta"] = df["fecha_consulta"].apply(parsear_fecha)
    logger.info(f"Fechas que no se pudieron parsear: {df['fecha_consulta'].isna().sum()}")

    return df.reset_index(drop=True)


def transformar_datos(df):
    # crear columna rango_peso
    rangos = {
        "perro": (5, 40, 60),
        "gato": (2, 6, 8),
    }
    def clasificar_peso(row):
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

    df["rango_peso"] = df.apply(clasificar_peso, axis=1)
    logger.info(f"Columna rango_peso creada")

    # extraer mes y año
    df["mes_consulta"] = df["fecha_consulta"].dt.month
    df["año_consulta"] = df["fecha_consulta"].dt.year
    logger.info("Columnas mes y año extraidas de fecha_consulta")

    # codificar especie
    dummies = pd.get_dummies(df["especie"], prefix="especie", dtype=int)
    df = pd.concat([df, dummies], axis=1)
    logger.info(f"Dummies de especie creados: {list(dummies.columns)}")

    # calcular años como cliente
    primera_visita = (
        df.dropna(subset=["dueño_email", "fecha_consulta"])
        .groupby("dueño_email")["fecha_consulta"]
        .min()
        .rename("primera_visita")
    )
    df = df.merge(primera_visita, on="dueño_email", how="left")
    df["años_cliente"] = ((df["fecha_consulta"] - df["primera_visita"]).dt.days / 365.25).round(2).fillna(0)
    df = df.drop(columns=["primera_visita"])
    logger.info("Columna años_cliente creada")

    return df


def main():
    logger.info("Iniciando pipeline")

    df = cargar_datos()
    detectar_problemas(df)
    df = limpiar_datos(df)
    df = transformar_datos(df)

    df.to_csv("mascotas_clean.csv", index=False, encoding="utf-8-sig")
    logger.info("Archivo mascotas_clean.csv guardado")
    logger.info("Pipeline terminado")


if __name__ == "__main__":
    main()
