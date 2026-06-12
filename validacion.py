"""
ETAPA 3 — VALIDACIÓN ESTRUCTURAL Y SEMÁNTICA
Implementa validaciones con pandera (estructurales) y reglas de negocio
(semánticas). Separa registros válidos de inválidos.
"""

import pandas as pd
import pandera.pandas as pa
from pandera.pandas import Column, DataFrameSchema, Check
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("data/validacion.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# VALIDACIONES ESTRUCTURALES (pandera)
# ─────────────────────────────────────────────

# Se define el esquema esperado del dataset limpio.
# Cada columna tiene: tipo esperado, rango de valores permitido y/o regex.

schema = DataFrameSchema(
    columns={
        # VALIDACIÓN 1 — id_mascota debe ser entero positivo único
        "id_mascota": Column(
            int,
            checks=Check.greater_than(0),
            nullable=False,
            description="ID debe ser entero positivo"
        ),

        # VALIDACIÓN 2 — edad_años debe estar entre 0 y 30 años
        "edad_años": Column(
            float,
            checks=Check.in_range(0, 30),
            nullable=True,
            description="Edad debe estar entre 0 y 30 años"
        ),

        # VALIDACIÓN 3 — peso_kg debe estar entre 0.01 y 200 kg
        "peso_kg": Column(
            float,
            checks=Check.in_range(0.01, 200),
            nullable=True,
            description="Peso debe estar entre 0.01 y 200 kg"
        ),

        # VALIDACIÓN 4 — dueño_email debe tener formato de email válido
        "dueño_email": Column(
            str,
            checks=Check.str_matches(r"^[\w\.\-]+@[\w\.\-]+\.\w{2,}$"),
            nullable=True,
            description="Email debe tener formato válido"
        ),

        # VALIDACIÓN 5 — costo_consulta debe ser positivo
        "costo_consulta": Column(
            float,
            checks=Check.greater_than(0),
            nullable=True,
            description="Costo debe ser mayor que 0"
        ),

        # VALIDACIÓN 6 — especie debe ser una de las categorías válidas
        "especie": Column(
            str,
            checks=Check.isin(["perro", "gato", "loro", "pez"]),
            nullable=True,
            description="Especie debe ser perro, gato, loro o pez"
        ),
    },
    coerce=False,
)


def validar_estructural(df: pd.DataFrame):
    """
    Aplica el esquema pandera fila a fila.
    Retorna (df_validos, df_invalidos) separando los registros según resultado.
    lazy=True permite recolectar todos los errores en una sola pasada.
    """
    logger.info("── Validación Estructural (pandera) ──")

    # Convertir fecha_consulta a string para evitar problemas de tipo en pandera
    df_val = df.copy()
    if "fecha_consulta" in df_val.columns:
        df_val["fecha_consulta"] = df_val["fecha_consulta"].astype(str)

    indices_invalidos = set()

    try:
        schema.validate(df_val, lazy=True)
        logger.info("Todos los registros pasaron la validación estructural.")
    except pa.errors.SchemaErrors as err:
        failure_cases = err.failure_cases
        logger.info(f"Errores estructurales encontrados: {len(failure_cases)}")

        for _, row in failure_cases.iterrows():
            col = row.get("column", "?")
            check = row.get("check", "?")
            idx = row.get("index")
            val = row.get("failure_case")
            if idx is not None and not pd.isna(idx):
                indices_invalidos.add(int(idx))
                logger.info(f"  Fila {int(idx)} | columna '{col}' | check '{check}' | valor: {val}")

    df_invalidos_struct = df[df.index.isin(indices_invalidos)].copy()
    df_validos = df[~df.index.isin(indices_invalidos)].copy()

    logger.info(f"Válidos estructurales: {len(df_validos)} | Inválidos: {len(df_invalidos_struct)}")
    return df_validos, df_invalidos_struct


# ─────────────────────────────────────────────
# VALIDACIONES SEMÁNTICAS (reglas de negocio)
# ─────────────────────────────────────────────

def validar_semantica(df: pd.DataFrame):
    """
    Aplica reglas de negocio que no puede capturar pandera solas
    porque involucran relaciones ENTRE columnas.

    REGLA 1: Un gato no puede pesar más de 20 kg (límite veterinario real).
    REGLA 2: El costo de consulta de urgencia debe ser mayor al de control rutinario
             del mismo dueño (las urgencias tienen sobrecargo obligatorio).
    """
    logger.info("── Validación Semántica (reglas de negocio) ──")

    df = df.copy()
    df["error_semantico"] = ""
    indices_invalidos = set()

    # REGLA 1 — Peso máximo por especie
    limites_peso = {"gato": 20, "loro": 2, "pez": 1}
    for especie, limite in limites_peso.items():
        mask = (df["especie"] == especie) & (df["peso_kg"] > limite)
        if mask.any():
            count = mask.sum()
            logger.info(f"  Regla 1 — {count} '{especie}' con peso > {limite} kg (imposible)")
            df.loc[mask, "error_semantico"] += f"peso_imposible_{especie}; "
            indices_invalidos.update(df[mask].index.tolist())

    # REGLA 2 — Urgencias deben costar más que controles del mismo dueño
    urgencias = df[df["motivo_consulta"].str.lower().str.contains("urgencia", na=False)]
    controles = df[df["motivo_consulta"].str.lower().str.contains("control", na=False)]

    if not urgencias.empty and not controles.empty:
        costo_prom_control = controles["costo_consulta"].mean()
        mask_barata = urgencias["costo_consulta"] < costo_prom_control
        if mask_barata.any():
            count = mask_barata.sum()
            logger.info(f"  Regla 2 — {count} urgencias con costo menor al promedio de controles ({costo_prom_control:.0f})")
            idx_mal = urgencias[mask_barata].index.tolist()
            df.loc[idx_mal, "error_semantico"] += "urgencia_costo_bajo; "
            indices_invalidos.update(idx_mal)

    df_invalidos_sem = df[df.index.isin(indices_invalidos)].copy()
    df_validos = df[~df.index.isin(indices_invalidos)].copy()
    df_validos = df_validos.drop(columns=["error_semantico"])

    logger.info(f"Válidos semánticos: {len(df_validos)} | Inválidos: {len(df_invalidos_sem)}")
    return df_validos, df_invalidos_sem


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def run(df: pd.DataFrame = None) -> pd.DataFrame:
    logger.info("════════════════════════════════")
    logger.info("  ETAPA 3 — VALIDACIÓN")
    logger.info("════════════════════════════════")

    if df is None:
        df = pd.read_csv("data/clean/mascotas_clean.csv", encoding="utf-8-sig")
        logger.info(f"Cargado desde data/clean/mascotas_clean.csv: {df.shape}")

    # Validación estructural
    df_validos, df_inv_struct = validar_estructural(df)

    # Validación semántica (sobre los que pasaron la estructural)
    df_final_validos, df_inv_sem = validar_semantica(df_validos)

    # Unir todos los inválidos
    df_todos_invalidos = pd.concat([df_inv_struct, df_inv_sem], ignore_index=True).drop_duplicates()

    # Guardar
    os.makedirs("data/validated", exist_ok=True)
    os.makedirs("data/errors", exist_ok=True)

    df_final_validos.to_csv("data/validated/mascotas_validated.csv", index=False, encoding="utf-8-sig")
    df_todos_invalidos.to_csv("data/errors/mascotas_errors.csv", index=False, encoding="utf-8-sig")

    logger.info(f"Registros válidos guardados en: data/validated/mascotas_validated.csv ({len(df_final_validos)})")
    logger.info(f"Registros inválidos guardados en: data/errors/mascotas_errors.csv ({len(df_todos_invalidos)})")
    logger.info("Etapa 3 completada.\n")

    return df_final_validos


if __name__ == "__main__":
    run()
