import sqlite3
import os


def get_db_connection():
    db_path = os.path.join(os.path.dirname(__file__), "assets.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Crear la tabla de activos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_name TEXT NOT NULL,
            location TEXT,
            amount REAL NOT NULL,
            currency TEXT NOT NULL,
            month TEXT,
            clase TEXT,
            fecha_ingreso TEXT
        )
    ''')
    # Crear la tabla de tipo de cambio global
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exchange_rate (
            month TEXT PRIMARY KEY,
            rate REAL NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Base de datos inicializada correctamente.")
    