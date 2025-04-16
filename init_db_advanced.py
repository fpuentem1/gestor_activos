#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect("assets.db")
cursor = conn.cursor()

# Crear tabla de Classes (Tipos de Activo)
cursor.execute("""
CREATE TABLE IF NOT EXISTS classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
""")

# Crear tabla de Subclasses (Subtipos) que se vinculan a una Clase
cursor.execute("""
CREATE TABLE IF NOT EXISTS subclasses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER,
    name TEXT NOT NULL,
    UNIQUE (class_id, name),
    FOREIGN KEY(class_id) REFERENCES classes(id)
);
""")

# Si deseas insertar algunos valores de ejemplo
cursor.execute("INSERT OR IGNORE INTO classes (name) VALUES ('Financiero')")
cursor.execute("INSERT OR IGNORE INTO subclasses (class_id, name) VALUES ((SELECT id FROM classes WHERE name='Financiero'), 'Bonos')")
cursor.execute("INSERT OR IGNORE INTO subclasses (class_id, name) VALUES ((SELECT id FROM classes WHERE name='Financiero'), 'Acciones')")
cursor.execute("INSERT OR IGNORE INTO subclasses (class_id, name) VALUES ((SELECT id FROM classes WHERE name='Financiero'), 'Contrato Private Equity')")

conn.commit()
conn.close()
print("Tablas de Classes y Subclasses creadas exitosamente.")