import csv
import os
from datetime import datetime

DATA_DIR = "data"
TRANSACTIONS_FILE = os.path.join(DATA_DIR, "transactions.csv")
LIMITS_FILE = os.path.join(DATA_DIR, "limits.csv")

def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def load_transactions():
    ensure_data_dir()
    if not os.path.exists(TRANSACTIONS_FILE):
        return []
    
    transactions = []
    with open(TRANSACTIONS_FILE, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            transactions.append({
                "id": int(row["id"]),
                "date": datetime.strptime(row["date"], "%Y-%m-%d"),
                "type": row["type"],
                "category": row["category"],
                "amount": float(row["amount"]),
            })
    return transactions

def append_transaction_to_file(t):
    """Эффективная дозапись одной транзакции с правильным порядком колонок"""
    ensure_data_dir()
    
    # Меняем порядок на тот, который реально используется в твоем CSV
    fields = ["id", "date", "type", "category", "amount"]
    
    file_exists = os.path.exists(TRANSACTIONS_FILE)
    
    with open(TRANSACTIONS_FILE, mode="a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if not file_exists or os.path.getsize(TRANSACTIONS_FILE) == 0:
            writer.writeheader()
            
        # Записываем данные в правильные колонки
        writer.writerow({
            "id": t["id"],
            "date": t["date"].strftime("%Y-%m-%d"),
            "type": t["type"],
            "category": t["category"],
            "amount": f"{t['amount']:.2f}"
        })

def load_limits():
    ensure_data_dir()
    if not os.path.exists(LIMITS_FILE):
        return {}
    
    limits = {}
    with open(LIMITS_FILE, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if row:
                limits[row[0]] = float(row[1])
    return limits

def save_limits(limits):
    ensure_data_dir()
    with open(LIMITS_FILE, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["category", "limit"])
        for cat, lim in limits.items():
            writer.writerow([cat, lim])