import re
import pandas as pd

# 1) Leer esquema real de la base de datos
schema = {}
with open('schema.txt', 'r') as f:
    next(f)  # saltar encabezado
    for line in f:
        parts = line.strip().split()
        if len(parts) >= 2:
            tabla, columna = parts[0], parts[1]
            schema.setdefault(tabla, set()).add(columna)

# 2) Leer todas las referencias SQL
rows = []
with open('all_sql_references.txt', 'r') as f:
    for raw in f:
        raw = raw.rstrip()
        try:
            file, lineno, code = raw.split(':', 2)
            lineno = int(lineno)
        except ValueError:
            continue
        code_strip = code.strip()

        # Detectar SELECT
        m = re.search(r'\bSELECT\s+(.*?)\s+FROM\s+["`]?(\w+)["`]?', code_strip, re.IGNORECASE)
        if m:
            fields = [fld.strip() for fld in m.group(1).split(',')]
            table = m.group(2)
            used_cols = []
            missing = []
            for fld in fields:
                # Extraer nombre de columna (sin alias ni prefijo)
                col = fld.split()[-1].split('.')[-1]
                used_cols.append(col)
                if col not in schema.get(table, set()):
                    missing.append(col)
            rows.append({
                'file': file,
                'line': lineno,
                'type': 'SELECT',
                'table': table,
                'used_cols': used_cols,
                'missing_cols': missing
            })
            continue

        # Detectar INSERT
        m = re.search(r'\bINSERT\s+INTO\s+["`]?(\w+)["`]?\s*\((.*?)\)', code_strip, re.IGNORECASE)
        if m:
            table = m.group(1)
            cols = [c.strip() for c in m.group(2).split(',')]
            missing = [col for col in cols if col not in schema.get(table, set())]
            rows.append({
                'file': file,
                'line': lineno,
                'type': 'INSERT',
                'table': table,
                'used_cols': cols,
                'missing_cols': missing
            })
            continue

        # Detectar UPDATE
        m = re.search(r'\bUPDATE\s+["`]?(\w+)["`]?\s+SET\s+(.*?)\s+WHERE', code_strip, re.IGNORECASE)
        if m:
            table = m.group(1)
            assigns = [p.strip() for p in m.group(2).split(',')]
            cols = [asg.split('=')[0].strip() for asg in assigns]
            missing = [col for col in cols if col not in schema.get(table, set())]
            rows.append({
                'file': file,
                'line': lineno,
                'type': 'UPDATE',
                'table': table,
                'used_cols': cols,
                'missing_cols': missing
            })
            continue

# 3) Construir DataFrame de inconsistencias y filtrar
df = pd.DataFrame(rows)
df['inconsistent'] = df['missing_cols'].apply(lambda x: len(x) > 0)
inconsistencies = df[df['inconsistent']].reset_index(drop=True)

# 4) Mostrar tabla interactiva al usuario
if inconsistencies.empty:
    print("✅ No se encontraron inconsistencias entre SQL y esquema de la BD.")
else:
    # Mostramos sólo las columnas clave
    print("⚠️  Inconsistencias encontradas:\n")
    print(inconsistencies[[
        'file','line','type','table','missing_cols'
    ]].to_string(index=False))