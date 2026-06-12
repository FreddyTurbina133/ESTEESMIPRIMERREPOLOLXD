"""
ETAPA 4 — CARGA A BASE DE DATOS
Conecta a SQLite, crea el esquema de tablas con PK y FK,
carga los datos validados usando transacciones ACID (COMMIT/ROLLBACK),
separa rechazados y verifica la carga con consultas SQL.
"""

import pandas as pd
import sqlite3
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("data/carga.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DB_PATH = "data/clinica_veterinaria.db"


def conectar() -> sqlite3.Connection:
    """Crea (o abre) la base de datos SQLite."""
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")  # Habilitar FK en SQLite
    logger.info(f"Conectado a SQLite: {DB_PATH}")
    return conn


def crear_esquema(conn: sqlite3.Connection):
    """
    Crea las tablas con tipos correctos, PK y FK.
    Se usan 2 tablas relacionadas:
      - dueños (PK: dueño_email)
      - mascotas (PK: id_mascota, FK: dueño_email → dueños)
    """
    logger.info("── Creando esquema de tablas ──")
    cursor = conn.cursor()

    cursor.executescript("""
        DROP TABLE IF EXISTS mascotas;
        DROP TABLE IF EXISTS dueños;

        CREATE TABLE dueños (
            dueño_email   TEXT PRIMARY KEY,
            dueño_nombre  TEXT
        );

        CREATE TABLE mascotas (
            id_mascota      INTEGER PRIMARY KEY,
            nombre          TEXT,
            especie         TEXT,
            raza            TEXT,
            edad_años       REAL,
            peso_kg         REAL,
            fecha_consulta  TEXT,
            dueño_email     TEXT,
            motivo_consulta TEXT,
            costo_consulta  REAL,
            rango_peso      TEXT,
            mes_consulta    REAL,
            año_consulta    REAL,
            años_cliente    REAL,
            FOREIGN KEY (dueño_email) REFERENCES dueños(dueño_email)
        );
    """)
    conn.commit()
    logger.info("Tablas 'dueños' y 'mascotas' creadas con PK y FK.")


def cargar_con_transaccion(conn: sqlite3.Connection, df: pd.DataFrame):
    """
    Carga los datos usando transacciones ACID:
    - BEGIN → inserta fila a fila
    - COMMIT si todo OK
    - ROLLBACK si hay error → registra en data/errors/rechazados_bd.csv
    """
    logger.info("── Cargando datos con transacciones ACID ──")

    # Primero cargar dueños (tabla padre, sin duplicados)
    dueños_df = df[["dueño_email", "dueño_nombre"]].dropna(subset=["dueño_email"]).drop_duplicates(subset=["dueño_email"])
    rechazados = []

    cursor = conn.cursor()

    # Insertar dueños
    logger.info(f"Insertando {len(dueños_df)} dueños únicos...")
    for _, row in dueños_df.iterrows():
        try:
            conn.execute("BEGIN")
            cursor.execute(
                "INSERT OR IGNORE INTO dueños (dueño_email, dueño_nombre) VALUES (?, ?)",
                (row["dueño_email"], row.get("dueño_nombre"))
            )
            conn.execute("COMMIT")
        except Exception as e:
            conn.execute("ROLLBACK")
            logger.warning(f"ROLLBACK dueño {row['dueño_email']}: {e}")

    # Insertar mascotas
    cols_mascota = [
        "id_mascota", "nombre", "especie", "raza", "edad_años", "peso_kg",
        "fecha_consulta", "dueño_email", "motivo_consulta", "costo_consulta",
        "rango_peso", "mes_consulta", "año_consulta", "años_cliente"
    ]
    # Solo columnas que existen en el dataframe
    cols_disponibles = [c for c in cols_mascota if c in df.columns]
    df_mascota = df[cols_disponibles].copy()

    # Convertir fecha a string para SQLite
    if "fecha_consulta" in df_mascota.columns:
        df_mascota["fecha_consulta"] = df_mascota["fecha_consulta"].astype(str)

    insertados = 0
    logger.info(f"Insertando {len(df_mascota)} mascotas...")

    for _, row in df_mascota.iterrows():
        try:
            conn.execute("BEGIN")
            placeholders = ", ".join(["?"] * len(cols_disponibles))
            sql = f"INSERT INTO mascotas ({', '.join(cols_disponibles)}) VALUES ({placeholders})"
            cursor.execute(sql, tuple(row[c] if pd.notna(row[c]) else None for c in cols_disponibles))
            conn.execute("COMMIT")
            insertados += 1
        except Exception as e:
            conn.execute("ROLLBACK")
            fila_dict = row.to_dict()
            fila_dict["error_bd"] = str(e)
            rechazados.append(fila_dict)
            logger.warning(f"ROLLBACK mascota id={row.get('id_mascota', '?')}: {e}")

    logger.info(f"Insertadas correctamente: {insertados} | Rechazadas por BD: {len(rechazados)}")

    # Guardar rechazados
    if rechazados:
        df_rechazados = pd.DataFrame(rechazados)
        df_rechazados.to_csv("data/errors/rechazados_bd.csv", index=False, encoding="utf-8-sig")
        logger.info("Rechazados por BD guardados en: data/errors/rechazados_bd.csv")

    return insertados


def verificar_carga(conn: sqlite3.Connection):
    """
    Verifica la carga con 3 consultas SQL representativas.
    """
    logger.info("── Verificación SQL ──")
    cursor = conn.cursor()

    # Consulta 1: COUNT total
    cursor.execute("SELECT COUNT(*) FROM mascotas")
    total = cursor.fetchone()[0]
    logger.info(f"  SELECT COUNT(*) FROM mascotas → {total} registros")

    # Consulta 2: GROUP BY especie
    cursor.execute("""
        SELECT especie, COUNT(*) as cantidad, ROUND(AVG(costo_consulta), 0) as costo_promedio
        FROM mascotas
        GROUP BY especie
        ORDER BY cantidad DESC
    """)
    rows = cursor.fetchall()
    logger.info("  Por especie (cantidad, costo promedio):")
    for r in rows:
        logger.info(f"    {r[0]}: {r[1]} mascotas | costo prom: ${r[2]:,.0f}" if r[2] else f"    {r[0]}: {r[1]} mascotas")

    # Consulta 3: Top 5 consultas más caras
    cursor.execute("""
        SELECT m.nombre, m.especie, m.motivo_consulta, m.costo_consulta, d.dueño_nombre
        FROM mascotas m
        LEFT JOIN dueños d ON m.dueño_email = d.dueño_email
        ORDER BY m.costo_consulta DESC
        LIMIT 5
    """)
    rows = cursor.fetchall()
    logger.info("  Top 5 consultas más caras:")
    for r in rows:
        logger.info(f"    {r[0]} ({r[1]}) — {r[2]} — ${r[3]:,.0f} — dueño: {r[4]}")


def run(df: pd.DataFrame = None):
    logger.info("════════════════════════════════")
    logger.info("  ETAPA 4 — CARGA A BASE DE DATOS (SQLite)")
    logger.info("════════════════════════════════")

    if df is None:
        df = pd.read_csv("data/validated/mascotas_validated.csv", encoding="utf-8-sig")
        logger.info(f"Cargado desde data/validated/mascotas_validated.csv: {df.shape}")

    conn = conectar()
    crear_esquema(conn)
    cargar_con_transaccion(conn, df)
    verificar_carga(conn)
    conn.close()

    logger.info(f"Base de datos guardada en: {DB_PATH}")
    logger.info("Etapa 4 completada.\n")


if __name__ == "__main__":
    run()
