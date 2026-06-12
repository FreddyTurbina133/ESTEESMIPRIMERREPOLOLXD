# Pipeline de Datos — Clínica Veterinaria 🐾

**Asignatura:** Gestion de datos para la Ia — DuocUC  
**Alumno:** Diego Sanchez | Natalia Quiroz 
**Dataset:** Registros de consultas veterinarias (`mascotas.csv`)  
**Base de datos:** SQLite (`data/clinica_veterinaria.db`)

---

## Dominio elegido

Se trabajó con registros de una clínica veterinaria ficticia. El dataset contiene información de mascotas (especie, edad, peso, raza), sus dueños (nombre, email) y las consultas realizadas (fecha, motivo, costo).

**Preguntas que buscamos responder:**
- ¿Qué especie tiene el mayor costo promedio de consulta?
- ¿Cuántos registros tienen errores de datos (pesos imposibles, emails inválidos)?
- ¿Qué meses concentran más consultas?

---

## Estructura del proyecto

```
pipeline_mascotas/
├── mascotas.csv              ← dataset original (fuente)
├── ingesta.py                ← Etapa 1: carga y estadísticas
├── limpieza.py               ← Etapa 2: limpieza y transformación
├── validacion.py             ← Etapa 3: validación estructural y semántica
├── carga.py                  ← Etapa 4: carga a SQLite con transacciones
├── main.py                   ← orquestador (corre todo)
├── README.md
└── data/
    ├── raw/
    │   └── mascotas_raw.csv           ← copia sin modificar del dataset
    ├── clean/
    │   └── mascotas_clean.csv         ← dataset limpio y transformado
    ├── validated/
    │   └── mascotas_validated.csv     ← registros válidos
    ├── errors/
    │   ├── mascotas_errors.csv        ← registros inválidos (validación)
    │   └── rechazados_bd.csv          ← rechazados por la BD
    ├── ingesta.log
    ├── limpieza.log
    ├── validacion.log
    ├── carga.log
    └── pipeline_completo.log
```

---

## Cómo ejecutar

### Requisitos
```bash
pip install pandas numpy pandera
```

### Ejecutar el pipeline completo
```bash
python main.py
```

### Ejecutar etapas individualmente
```bash
python ingesta.py
python limpieza.py
python validacion.py
python carga.py
```

> **Nota:** `mascotas.csv` debe estar en la misma carpeta que los scripts.

---

## Descripción del dataset

| Campo | Tipo | Descripción |
|---|---|---|
| id_mascota | int | Identificador único |
| nombre | str | Nombre de la mascota |
| especie | str | perro / gato / loro / pez |
| raza | str | Raza de la mascota |
| edad_años | float | Edad en años |
| peso_kg | float | Peso en kilogramos |
| fecha_consulta | str | Fecha (3 formatos distintos en el raw) |
| dueño_nombre | str | Nombre del dueño |
| dueño_email | str | Email del dueño (clave para relaciones) |
| motivo_consulta | str | Motivo de la visita |
| costo_consulta | float | Costo en pesos chilenos |

**Fuente:** Dataset sintético generado con errores intencionales para el curso.  
**Registros:** 50 filas × 11 columnas (raw) → 50 filas × 19 columnas (clean)

---

## Errores encontrados en el raw dataset

| Error | Descripción | Solución |
|---|---|---|
| Duplicados exactos | Firulais aparece dos veces (id=1 e id=2) | `drop_duplicates()` |
| Variantes de especie | "gato", "GATO", "Cat", "gata" = lo mismo | Diccionario de mapeo |
| Edades negativas | Fido tiene edad = -1 | Reemplazar por NaN → imputar mediana |
| Nulos en edad_años | 10 filas sin edad | Imputar mediana por especie |
| Pesos imposibles | Rex: 350 kg, Garfield: 9999 kg | Reemplazar por mediana de especie |
| Formatos de fecha mezclados | %Y-%m-%d, %d/%m/%Y, %Y%m%d | Parser multi-formato |
| Nulos varios | nombre, especie, dueño_nombre, etc. | Mantener NaN (dato no disponible) |

---

## Etapas del pipeline

### Etapa 1 — Ingesta (`ingesta.py`)
- Carga `mascotas.csv` con `pd.read_csv()`
- Muestra shape, dtypes, conteo de nulos y primeras filas
- Guarda copia sin modificar en `data/raw/mascotas_raw.csv`

### Etapa 2 — Limpieza y Transformación (`limpieza.py`)

**Limpieza:**
- Eliminación de duplicados exactos y filas vacías
- Estandarización de especie (13 variantes → 4 categorías)
- Imputación de edad con mediana por especie
- Corrección de pesos imposibles (> 200 kg) con mediana por especie
- Parseo de fechas multi-formato

**Transformaciones:**
1. `rango_peso` — clasifica el peso en bajo/normal/alto/obeso según rangos veterinarios por especie
2. `mes_consulta` y `año_consulta` — extrae componentes de fecha para análisis temporal
3. `especie_*` — one-hot encoding de especie (columnas binarias para ML)
4. `años_cliente` — calcula hace cuántos años el dueño es cliente de la clínica

### Etapa 3 — Validación (`validacion.py`)

**Validaciones estructurales (pandera):**
1. `id_mascota` — entero positivo, no nulo
2. `edad_años` — rango [0, 30]
3. `peso_kg` — rango [0.01, 200]
4. `dueño_email` — regex de email válido
5. `costo_consulta` — mayor que 0
6. `especie` — valor dentro del set {perro, gato, loro, pez}

**Validaciones semánticas (reglas de negocio):**
1. Un gato no puede pesar más de 20 kg (límite veterinario)
2. Las consultas de urgencia deben costar más que el promedio de controles rutinarios

Los registros inválidos se guardan en `data/errors/mascotas_errors.csv` con descripción del error.

### Etapa 4 — Carga a BD (`carga.py`)
- Base de datos: **SQLite** (`data/clinica_veterinaria.db`)
- 2 tablas: `dueños` (PK: dueño_email) y `mascotas` (PK: id_mascota, FK: dueño_email)
- Inserción fila a fila con `BEGIN / COMMIT / ROLLBACK` por cada registro
- Registros rechazados por la BD se guardan en `data/errors/rechazados_bd.csv`
- Verificación con 3 consultas SQL: COUNT, GROUP BY especie, JOIN con top 5 costos

---

## Decisiones técnicas

| Decisión | Justificación |
|---|---|
| Imputar edad con mediana por especie | La mediana es robusta a outliers; usar la de la misma especie respeta la distribución biológica real |
| Reemplazar pesos > 200 kg por mediana | 350 kg y 9999 kg son errores de tipeo evidentes; la mediana preserva el dato en lugar de eliminarlo |
| SQLite como BD | No requiere instalación de servidor; cumple completamente con los requisitos del encargo |
| `pandera` con `lazy=True` | Permite detectar TODOS los errores en una sola pasada sin detener la validación al primer fallo |
| FK entre dueños y mascotas | Modela correctamente la relación real: un dueño puede tener varias mascotas |
