import asyncio
import sqlite3
import requests
from datetime import datetime

DB_FILE = "sensors.db"

# --- база ---
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS kp_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    kp REAL
)
""")
conn.commit()


# --- получение Kp ---
def fetch_kp():
    try:
        url = "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json"
        r = requests.get(url, timeout=10)

        if r.status_code != 200:
            print("HTTP error:", r.status_code)
            return None

        data = r.json()

        if not data:
            print("No KP data")
            return None

        latest = data[-1]

        kp = float(latest["kp_index"])
        ts = latest["time_tag"]

        return ts, kp

    except Exception as e:
        print("KP fetch error:", e)
        return None


# --- запись ---
def save_kp(ts, kp):
    cursor.execute(
        "INSERT INTO kp_data (timestamp, kp) VALUES (?, ?)",
        (ts, kp)
    )
    conn.commit()


# --- основной цикл ---
async def kp_loop():
    while True:
        result = fetch_kp()

        if result:
            ts, kp = result
            save_kp(ts, kp)
            print(f"Kp logged: {kp}")

        await asyncio.sleep(600)  # каждые 10 минут


# --- запуск ---
if __name__ == "__main__":
    asyncio.run(kp_loop())
