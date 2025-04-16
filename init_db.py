import sqlite3

conn = sqlite3.connect("assets.db")
conn.row_factory = sqlite3.Row

# Tabla assets (ya la tienes)
conn.execute("""
    CREATE TABLE IF NOT EXISTS assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_name TEXT NOT NULL,
        location TEXT,
        amount REAL,
        currency TEXT,
        month TEXT,
        clase TEXT,
        observaciones TEXT,
        fecha_ingreso TEXT,
        portfolio_id TEXT DEFAULT 'default',
        estado TEXT DEFAULT 'activo'
    );
""")

# Crear tabla portfolios si no existe
conn.execute("""
    CREATE TABLE IF NOT EXISTS portfolios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL
    );
""")

# Crear tabla classes si no existe
conn.execute("""
    CREATE TABLE IF NOT EXISTS classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL
    );
""")

# Crear tabla subclasses si no existe
conn.execute("""
    CREATE TABLE IF NOT EXISTS subclasses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        class_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        FOREIGN KEY (class_id) REFERENCES classes(id)
    );
""")

# Crear tabla statuses si no existe
conn.execute("""
    CREATE TABLE IF NOT EXISTS statuses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL
    );
""")

conn.commit()
conn.close()
print("Tablas creadas o verificadas exitosamente.")