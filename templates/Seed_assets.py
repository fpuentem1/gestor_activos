# seed_assets.py
import csv
import sqlite3
from datetime import datetime
from dateutil.relativedelta import relativedelta

DB = "assets.db"

def get_months(start, end):
    """Devuelve lista de meses AAAA‑MM desde start hasta end inclusive."""
    curr = datetime.strptime(start + "-01", "%Y-%m")
    last = datetime.strptime(end + "-01", "%Y-%m")
    months = []
    while curr <= last:
        months.append(curr.strftime("%Y-%m"))
        curr += relativedelta(months=1)
    return months

def seed(csv_path, start_month, end_month, portfolio_id="default"):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    months = get_months(start_month, end_month)

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for m in months:
                cur.execute("""
                    INSERT INTO assets
                    (asset_name, location, amount, currency, month,
                     clase, observaciones, fecha_ingreso, portfolio_id)
                    VALUES (?,?,?,?,?,?,?,?,?)
                """, (
                    row["asset_name"],
                    row.get("location",""),
                    float(row["amount"]),
                    row.get("currency","USD"),
                    m,
                    row.get("clase",""),
                    row.get("observaciones",""),
                    datetime.now().strftime("%Y-%m"),
                    portfolio_id
                ))
    conn.commit()
    conn.close()
    print(f"Semilla completada: {csv_path} → {len(months)} meses cada asset.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 4:
        print("Uso: python seed_assets.py datos.csv 2025-01 2025-04")
    else:
        _, archivo, inicio, fin = sys.argv
        seed(archivo, inicio, fin)