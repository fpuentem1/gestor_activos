import pandas as pd
import sqlite3

# Rutas (ajusta si tus archivos están en otra carpeta)
CSV_PATH = 'import_assets.csv'
DB_PATH = 'assets.db'


def main():
    # Leer el CSV
    df = pd.read_csv(CSV_PATH)

    # Conectar a la base de datos
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Iterar filas e insertar en la tabla assets
    for _, row in df.iterrows():
        cursor.execute(
            """
            INSERT INTO assets (
                asset_name, location, amount, currency, month,
                clase, observaciones, fecha_ingreso,
                portfolio_id, estado, class_id, subclass_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row['asset_name'],
                row['location'],
                row['amount'],
                row['currency'],
                row['month'],
                row.get('clase', ''),
                row.get('observaciones', ''),
                row.get('fecha_ingreso', ''),
                row.get('portfolio_id', 'default'),
                row.get('estado', 'activo'),
                row.get('class_id', None),
                row.get('subclass_id', None)
            )
        )

    # Confirmar cambios y cerrar
    conn.commit()
    conn.close()
    print("Importación completada exitosamente.")


if __name__ == '__main__':
    main()