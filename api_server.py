from fastapi import FastAPI
import sqlite3
from fastapi.responses import FileResponse
import requests
from datetime import datetime

app = FastAPI()

WEATHER_API_KEY = "WEATHER_API_KEYb"
CITY = "YourCiti"
DB_FILE = "sensors.db"


# ---------------- DB ----------------
def get_db():
    return sqlite3.connect(DB_FILE)


# ---------------- ROOT ----------------
@app.get("/")
def root():
    return {"status": "ok"}


# ---------------- DASHBOARD ----------------
@app.get("/dashboard")
def dashboard():
    return FileResponse("dashboard.html")


# ---------------- WEMOS ----------------
def get_wemos():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT timestamp, temp, humidity, wifi_rssi
        FROM wemos_data
        WHERE sensor_id = 2
        ORDER BY id DESC
        LIMIT 24
    """)

    rows = cursor.fetchall()[::-1]
    conn.close()

    return [
        {
            "time": r[0],
            "temp": r[1],
            "humidity": r[2],
            "rssi": r[3]
        }
        for r in rows
    ]


# ---------------- MQ135 ----------------
def get_mq135():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT timestamp, air, wifi_rssi
        FROM mq135_data
        WHERE sensor_id = 2
        ORDER BY id DESC
        LIMIT 24
    """)

    rows = cursor.fetchall()[::-1]
    conn.close()

    return [
        {
            "time": r[0],
            "ppm": r[1],
            "rssi": r[2]
        }
        for r in rows
    ]


# ---------------- AURORA ----------------
@app.get("/aurora")
def aurora():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT kp FROM kp_data ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    kp = row[0] if row else 0
    conn.close()

    # WEATHER
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={WEATHER_API_KEY}&units=metric"
        weather = requests.get(url, timeout=5).json()
        clouds = weather["clouds"]["all"]
    except:
        clouds = 0

    hour = datetime.now().hour
    night = hour >= 21 or hour <= 4

    if not night:
        status = "☀️ День — не видно"
    elif clouds > 80:
        status = "☁️ Облачно — не видно"
    elif kp < 3:
        status = "❌ Слабая активность"
    elif kp < 5:
        status = "⚠️ Малый шанс"
    elif kp < 6:
        status = "🌌 Возможны"
    else:
        status = "✨ Высокая вероятность"

    return {
        "kp": kp,
        "clouds": clouds,
        "night": night,
        "status": status
    }


# ---------------- DATA ----------------
@app.get("/data")
def get_latest_data():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT timestamp, temp, humidity, pressure
        FROM sensor_data
        ORDER BY id DESC LIMIT 1
    """)

    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"error": "no data"}

    return {
        "time": row[0],
        "temp": row[1],
        "humidity": row[2],
        "pressure": row[3]
    }


# ---------------- FULL ----------------
@app.get("/full")
def get_full():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT timestamp, temp, humidity, pressure, wind, wind_deg
        FROM sensor_data
        ORDER BY id DESC LIMIT 100
    """)
    rows = cursor.fetchall()[::-1]

    cursor.execute("""
        SELECT timestamp, kp
        FROM kp_data
        ORDER BY id DESC LIMIT 100
    """)
    kp = cursor.fetchall()[::-1]

    conn.close()

    return {
        "sensors": [
            {
                "time": r[0],
                "temp": r[1],
                "hum": r[2],
                "press": r[3],
                "wind": r[4],
                "deg": r[5]
            }
            for r in rows
        ],
        "kp": [
            {"time": r[0], "kp": r[1]}
            for r in kp
        ],
        "wemos": get_wemos(),
        "mq135": get_mq135()
    }


# ---------------- KP ----------------
@app.get("/kp")
def get_kp():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT timestamp, kp
        FROM kp_data
        ORDER BY id DESC LIMIT 1
    """)

    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"error": "no data"}

    return {
        "time": row[0],
        "kp": row[1]
    }


# ---------------- HISTORY ----------------
@app.get("/history")
def get_history():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT timestamp, temp
        FROM sensor_data
        ORDER BY id DESC LIMIT 50
    """)

    rows = cursor.fetchall()
    conn.close()

    return [
        {"time": r[0], "temp": r[1]}
        for r in rows
    ]
