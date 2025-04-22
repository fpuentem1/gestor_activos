import sqlite3

conn = sqlite3.connect("assets.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Habilitar integridad referencial en SQLite
cursor.execute("PRAGMA foreign_keys = ON;")

# 1) Tablas maestras: portfolios, classes, subclasses, statuses
cursor.execute("""
CREATE TABLE IF NOT EXISTS portfolios (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT    NOT NULL UNIQUE
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS classes (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT    NOT NULL UNIQUE
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS subclasses (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER NOT NULL,
    name     TEXT    NOT NULL,
    UNIQUE(class_id, name),
    FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE CASCADE
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS statuses (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT    NOT NULL UNIQUE
);
""")

# 2) Tabla de assets (datos estáticos)
cursor.execute("DROP TABLE IF EXISTS assets;")
cursor.execute("""
CREATE TABLE assets (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT    NOT NULL,
    location       TEXT,
    date_acquired  TEXT,            -- fecha_ingreso
    class_id       INTEGER NOT NULL,
    subclass_id    INTEGER NOT NULL,
    portfolio_id   INTEGER NOT NULL,
    observations   TEXT,            -- observaciones
    FOREIGN KEY(class_id)     REFERENCES classes(id),
    FOREIGN KEY(subclass_id)  REFERENCES subclasses(id),
    FOREIGN KEY(portfolio_id) REFERENCES portfolios(id)
);
""")

# 3) Tabla de valores por periodo (dinámica)
cursor.execute("DROP TABLE IF EXISTS asset_values;")
cursor.execute("""
CREATE TABLE asset_values (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id   INTEGER NOT NULL,
    month      TEXT    NOT NULL,   -- p.ej. '2025-04'
    amount     REAL,
    currency   TEXT,
    status_id  INTEGER,             -- vincula a statuses(id)
    UNIQUE(asset_id, month),
    FOREIGN KEY(asset_id)  REFERENCES assets(id)  ON DELETE CASCADE,
    FOREIGN KEY(status_id) REFERENCES statuses(id)
);
""")

# 4) Tabla de tasas de cambio (si la usas para convertir montos)
cursor.execute("""
CREATE TABLE IF NOT EXISTS exchange_rate (
    month TEXT PRIMARY KEY,
    rate  REAL
);
""")

conn.commit()
conn.close()
print("Esquema re-creado: assets + asset_values + catálogos.")