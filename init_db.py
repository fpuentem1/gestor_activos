import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "assets.db")

conn = sqlite3.connect(db_path)
c = conn.cursor()

# Crea la tabla assets si no existe.
c.execute("""
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
    portfolio_id TEXT DEFAULT 'default'
)
""")

# Crea la tabla exchange_rate si no existe.
c.execute("""
CREATE TABLE IF NOT EXISTS exchange_rate (
    month TEXT PRIMARY KEY,
    rate REAL
)
""")

# Crea la tabla portfolios si no existe.
c.execute("""
CREATE TABLE IF NOT EXISTS portfolios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
)
""")

conn.commit()
conn.close()

print("Tablas creadas exitosamente.")