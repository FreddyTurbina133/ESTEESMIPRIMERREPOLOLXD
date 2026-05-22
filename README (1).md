# Actividad 2.2 - Pipeline de Datos

**Alumno:** Diego Sanchez

## Archivos
- `mascotas.csv` - dataset original
- `pipeline.py` - script principal
- `mascotas_clean.csv` - dataset limpio
- `pipeline.log` - log del proceso

## Como ejecutar
```bash
pip install pandas numpy
python pipeline.py
```

## Errores encontrados
- Firulais aparece duplicado (id=1 e id=2)
- Fila completamente vacía (id=6)
- edad_años tiene 10 nulos
- especie tiene variantes como gato, GATO, Cat, gata, etc.
- Garfield tiene peso 9999kg y Rex 350kg, claramente son errores
- fecha_consulta tiene 3 formatos distintos mezclados
- Fido tiene edad -1

## Lo que hice
Para los nulos de edad usé la mediana por especie. Los pesos imposibles los reemplacé también con la mediana. Las fechas las parseé probando los 3 formatos uno por uno. Las variantes de especie las unifiqué con un diccionario.
