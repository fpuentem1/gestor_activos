import sqlite3

db_path = "assets.db"  # Define el nombre de tu base de datos

def get_db_connection():
    conn = sqlite3.connect(db_path, timeout=20)  # Usa db_path aquí y agrega timeout opcionalmente
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")  # Habilitar integridad referencial en cada nueva conexión
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
    