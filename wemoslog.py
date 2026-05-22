from flask import Flask, request
import sqlite3
from datetime import datetime

app = Flask(__name__)

DB_NAME = "sensors.db"


@app.route("/sensor")
def sensor():

    temp = request.args.get("temp")
    hum = request.args.get("hum")
    sensor_id = request.args.get("id")
    rssi = request.args.get("rssi")

    if temp is None or hum is None:
        return "missing data", 400

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO wemos_data
    (timestamp, sensor_id, temp, humidity, wifi_rssi)
    VALUES (?, ?, ?, ?, ?)
    """, (timestamp, sensor_id, temp, hum, rssi))

    conn.commit()
    conn.close()

    print(f"{timestamp} | Sensor={sensor_id} | T={temp} | H={hum}")

    return "OK"

@app.route("/mq135")
def mq135():

    sensor_id = request.args.get("id")
    air = request.args.get("air")
    rssi = request.args.get("rssi")

    if air is None:
        return "missing air", 400

    timestamp = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO mq135_data
    (timestamp, sensor_id, air, wifi_rssi)
    VALUES (?, ?, ?, ?)
    """, (
        timestamp,
        sensor_id,
        air,
        rssi
    ))

    conn.commit()
    conn.close()

    print(
        f"{timestamp} | "
        f"MQ135={air}"
    )

    return "OK"


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=8001
    )
