import pandas as pd

# Ajusta la ruta si es necesario
df = pd.read_csv('import_assets.csv')

print("Columnas del CSV:")
print(df.columns.tolist(), "\n")

print("Primeras 5 filas del CSV:")
print(df.head(), "\n")

# Detectar filas sin asset_name
mask = df['asset_name'].isnull() | (df['asset_name'].astype(str).str.strip() == "")
print(f"Filas con asset_name faltante: {mask.sum()}\n")

if mask.any():
    print("Ejemplos de filas con asset_name faltante:")
    print(df[mask].head())