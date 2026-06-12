"""
MAIN — ORQUESTADOR DEL PIPELINE
Ejecuta las 4 etapas en orden:
  1. Ingesta     → data/raw/
  2. Limpieza    → data/clean/
  3. Validación  → data/validated/ y data/errors/
  4. Carga BD    → data/clinica_veterinaria.db

Uso: python main.py
"""

import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("data/pipeline_completo.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

import ingesta
import limpieza
import validacion
import carga


def main():
    inicio = time.time()

    logger.info("╔══════════════════════════════════════════╗")
    logger.info("║   PIPELINE COMPLETO — Clínica Veterinaria ║")
    logger.info("╚══════════════════════════════════════════╝")

    # Etapa 1
    df_raw = ingesta.run()

    # Etapa 2
    df_clean = limpieza.run(df_raw)

    # Etapa 3
    df_valido = validacion.run(df_clean)

    # Etapa 4
    carga.run(df_valido)

    elapsed = round(time.time() - inicio, 2)
    logger.info(f"Pipeline completado en {elapsed} segundos.")
    logger.info("╔══════════════════════════════════════════╗")
    logger.info("║   FIN DEL PIPELINE — ÉXITO               ║")
    logger.info("╚══════════════════════════════════════════╝")


if __name__ == "__main__":
    main()
