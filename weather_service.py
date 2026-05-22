
import time
import asyncio
import sqlite3
from datetime import datetime
from collections import deque

import smbus2
import bme280
import requests
import nest_asyncio
import matplotlib.pyplot as plt

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler
)

# =========================================================
# НАСТРОЙКИ
# =========================================================

TOKEN = "Telegram bot token"
CHAT_ID = "YourChatId"

WEATHER_API_KEY = "WeatherKay"
CITY = "YourCity"

DB_FILE = "sensors.db"

UPDATE_INTERVAL = 300
AUTO_UPDATE_INTERVAL = 600

nest_asyncio.apply()

last_alert = None

# =========================================================
# I2C
# =========================================================

I2C_PORT = 1

bus = smbus2.SMBus(I2C_PORT)

AHT20_ADDR = 0x38
BME280_ADDR = 0x77

calibration_params = bme280.load_calibration_params(
    bus,
    BME280_ADDR
)

# =========================================================
# SQLITE
# =========================================================

conn = sqlite3.connect(
    DB_FILE,
    check_same_thread=False
)

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS sensor_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    temp REAL,
    humidity REAL,
    pressure REAL,
    wind REAL,
    wind_deg REAL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS kp_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    kp REAL
)
""")

conn.commit()

# =========================================================
# СГЛАЖИВАНИЕ
# =========================================================

WINDOW_SIZE = 5

temp_aht_window = deque(maxlen=WINDOW_SIZE)
hum_window = deque(maxlen=WINDOW_SIZE)
temp_bme_window = deque(maxlen=WINDOW_SIZE)
press_window = deque(maxlen=WINDOW_SIZE)

def smooth_array(data, k=5):

    result = []

    for i in range(len(data)):

        start = max(0, i - k)

        arr = data[start:i+1]

        result.append(sum(arr) / len(arr))

    return result

# =========================================================
# SENSOR FUNCTIONS
# =========================================================

def smooth(window, value):

    window.append(value)

    return sum(window) / len(window)


def read_aht20():

    try:

        bus.write_i2c_block_data(
            AHT20_ADDR,
            0xAC,
            [0x33, 0x00]
        )

        time.sleep(0.08)

        data = bus.read_i2c_block_data(
            AHT20_ADDR,
            0x00,
            6
        )

        if data[0] & 0x80:
            return None

        raw_h = (
            (data[1] << 12)
            | (data[2] << 4)
            | (data[3] >> 4)
        )

        humidity = raw_h * 100 / 1048576

        raw_t = (
            ((data[3] & 0x0F) << 16)
            | (data[4] << 8)
            | data[5]
        )

        temperature = raw_t * 200 / 1048576 - 50

        return temperature, humidity

    except Exception as e:

        print("AHT20 error:", e)

        return None


def read_bme280():

    try:

        data = bme280.sample(
            bus,
            BME280_ADDR,
            calibration_params
        )

        return data.temperature, data.pressure

    except Exception as e:

        print("BME280 error:", e)

        return None, None
#=========================================================
# ЧТЕНИЯ WEMOS
#=========================================================

def get_wemos_text():

    conn2 = sqlite3.connect(DB_FILE)

    cur = conn2.cursor()

    cur.execute("""
        SELECT
            timestamp,
            sensor_id,
            temp,
            humidity,
            wifi_rssi
        FROM wemos_data
        ORDER BY id DESC
        LIMIT 1
    """)

    row = cur.fetchone()

    conn2.close()

    if not row:
        return "📡 Wemos данных нет"

    return (
        "📡 WEMOS SENSOR\n\n"
        f"🕒 {row[0]}\n\n"
        f"🆔 Sensor: {row[1]}\n"
        f"🌡 Температура: {row[2]:.1f} °C\n"
        f"💧 Влажность: {row[3]:.1f} %\n"
        f"📶 WiFi RSSI: {row[4]} dBm"
    )

# =========================================================
# MQ135 AIR QUALITY
# =========================================================

def get_air_text():

    conn2 = sqlite3.connect(DB_FILE)

    cur = conn2.cursor()

    cur.execute("""
        SELECT
            timestamp,
            sensor_id,
            air,
            wifi_rssi
        FROM mq135_data
        ORDER BY id DESC
        LIMIT 1
    """)

    row = cur.fetchone()

    conn2.close()

    if not row:
        return "🌫 MQ135 данных нет"

    air = int(row[2])

    if air < 200:

        status = "🟢 Чистый воздух"

    elif air < 350:

        status = "🟡 Нормально"

    elif air < 500:

        status = "🟠 Загрязнение"

    else:

        status = "🔴 Опасно"

    return (
        "🌫 MQ135 AIR SENSOR\n\n"
        f"🕒 {row[0]}\n\n"
        f"🆔 Sensor: {row[1]}\n"
        f"🌫 Air Value: {air}\n"
        f"📊 Status: {status}\n"
        f"📶 WiFi RSSI: {row[3]} dBm"
    )




# =========================================================
# WEATHER
# =========================================================

def get_weather():

    try:

        url = (
            "http://api.openweathermap.org/data/2.5/weather"
            f"?q={CITY}"
            f"&appid={WEATHER_API_KEY}"
            "&units=metric"
        )

        weather = requests.get(
            url,
            timeout=5
        ).json()

        wind = weather.get(
            "wind",
            {}
        ).get("speed", 0)

        wind_deg = weather.get(
            "wind",
            {}
        ).get("deg", 0)

        return wind, wind_deg

    except Exception as e:

        print("Weather error:", e)

        return 0, 0

# =========================================================
# SENSOR LOGGER
# =========================================================

async def log_sensors():

    while True:

        try:

            aht = read_aht20()

            bme_temp, pressure = read_bme280()

            if aht:

                temp_aht, hum = aht

                temp_aht = smooth(
                    temp_aht_window,
                    temp_aht
                )

                hum = smooth(
                    hum_window,
                    hum
                )

                if bme_temp is not None:
                    bme_temp = smooth(
                        temp_bme_window,
                        bme_temp
                    )

                if pressure:
                    pressure = smooth(
                        press_window,
                        pressure
                    )

                wind, wind_deg = get_weather()

                timestamp = datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

                cursor.execute("""
                    INSERT INTO sensor_data (
                        timestamp,
                        temp,
                        humidity,
                        pressure,
                        wind,
                        wind_deg
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    timestamp,
                    temp_aht,
                    hum,
                    pressure,
                    wind,
                    wind_deg
                ))

                conn.commit()

                print(
                    f"{timestamp} | "
                    f"T={bme_temp:.1f}°C | "
                    f"H={hum:.1f}% | "
                    f"P={pressure:.1f}hPa | "
                    f"W={wind:.1f}m/s"
                )

        except Exception as e:

            print("Log error:", e)

        await asyncio.sleep(UPDATE_INTERVAL)

# =========================================================
# KP LOGGER
# =========================================================

async def log_kp():

    while True:

        try:

            url = (
                "https://services.swpc.noaa.gov/"
                "json/planetary_k_index_1m.json"
            )

            data = requests.get(
                url,
                timeout=10
            ).json()

            latest = data[-1]

            kp = float(latest["kp_index"])

            timestamp = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            cursor.execute("""
                INSERT INTO kp_data (
                    timestamp,
                    kp
                )
                VALUES (?, ?)
            """, (
                timestamp,
                kp
            ))

            conn.commit()

            print("KP:", kp)

        except Exception as e:

            print("KP error:", e)

        await asyncio.sleep(1200)

# =========================================================
# AURORA ALERT
# =========================================================

async def check_aurora(context):

    global last_alert

    conn2 = sqlite3.connect(DB_FILE)

    cur = conn2.cursor()

    cur.execute("""
        SELECT kp
        FROM kp_data
        ORDER BY id DESC
        LIMIT 1
    """)

    row = cur.fetchone()

    conn2.close()

    if not row:
        return

    kp = row[0]

    try:

        url = (
            "http://api.openweathermap.org/data/2.5/weather"
            f"?q={CITY}"
            f"&appid={WEATHER_API_KEY}"
        )

        weather = requests.get(
            url,
            timeout=5
        ).json()

        clouds = weather.get(
            "clouds",
            {}
        ).get("all", 100)

    except:

        clouds = 100

    hour = datetime.now().hour

    night = hour >= 21 or hour <= 4

    if not night:
        status = "day"

    elif clouds > 80:
        status = "clouds"

    elif kp < 5:
        status = "low"

    elif kp < 6:
        status = "medium"

    else:
        status = "high"

    if status == last_alert:
        return

    last_alert = status

    if status == "high":

        text = (
            f"✨ СЕВЕРНОЕ СИЯНИЕ!\n"
            f"Kp={kp}\n"
            f"☁️ {clouds}%"
        )

    elif status == "medium":

        text = (
            f"🌌 Возможны сияния\n"
            f"Kp={kp}"
        )

    else:
        return

    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=text
    )

# =========================================================
# DATA
# =========================================================

def read_last_rows(n=1):

    cursor.execute("""
        SELECT
            timestamp,
            temp,
            humidity,
            pressure
        FROM sensor_data
        ORDER BY id DESC
        LIMIT ?
    """, (n,))

    rows = cursor.fetchall()

    return rows[::-1]


def get_latest_data_text():

    rows = read_last_rows(1)

    if not rows:
        return "НЕТ ДАННЫХ"

    r = rows[-1]

    return (
        f"🌡 ТЕМПЕРАТУРА: {r[1]:.1f} °C\n\n"
        f"💧 ВЛАЖНОСТЬ: {r[2]:.1f} %\n\n"
        f"📈 ДАВЛЕНИЕ: {r[3]:.1f} hPa"
    )

# =========================================================
# STATS
# =========================================================

def get_stats():

    cursor.execute("""
        SELECT
            temp,
            humidity,
            pressure
        FROM sensor_data
        ORDER BY id DESC
        LIMIT 100
    """)

    rows = cursor.fetchall()

    if not rows:
        return "НЕТ ДАННЫХ"

    temps = [r[0] for r in rows if r[0] is not None]
    hums = [r[1] for r in rows if r[1] is not None]
    press = [r[2] for r in rows if r[2] is not None]
    return (
        "📊 СТАТИСТИКА\n\n"
        f"🌡 Tmin: {min(temps):.1f}\n"
        f"🌡 Tmax: {max(temps):.1f}\n"
        f"🌡 Avg : {sum(temps)/len(temps):.1f}\n\n"
        f"💧 Hmin: {min(hums):.1f}\n"
        f"💧 Hmax: {max(hums):.1f}\n\n"
        f"📈 Pmin: {min(press):.1f}\n"
        f"📈 Pmax: {max(press):.1f}"
    )

# =========================================================
# GRAPHS
# =========================================================

def generate_graphs():

    cursor.execute("""
        SELECT
            timestamp,
            temp,
            humidity,
            pressure,
            wind
        FROM sensor_data
        ORDER BY id DESC
        LIMIT 50
    """)

    rows = cursor.fetchall()[::-1]

    if not rows:
        return None, None, None, None

    times = [r[0][-8:] for r in rows]

    temps = smooth_array([r[1] for r in rows])
    hums = smooth_array([r[2] for r in rows])
    press = smooth_array([r[3] for r in rows])
    wind = smooth_array([r[4] for r in rows])
    plt.figure()
    plt.plot(times, temps)
    plt.xticks(rotation=45)
    plt.title("Temperature")
    plt.tight_layout()
    plt.savefig("temp.png")
    plt.close()

    plt.figure()
    plt.plot(times, hums)
    plt.xticks(rotation=45)
    plt.title("Humidity")
    plt.tight_layout()
    plt.savefig("hum.png")
    plt.close()

    plt.figure()
    plt.plot(times, press)
    plt.xticks(rotation=45)
    plt.title("Pressure")
    plt.tight_layout()
    plt.savefig("press.png")
    plt.close()

    plt.figure()
    plt.plot(times, wind)
    plt.xticks(rotation=45)
    plt.title("Wind")
    plt.tight_layout()
    plt.savefig("wind.png")
    plt.close()

    return (
        "temp.png",
        "hum.png",
        "press.png",
        "wind.png"
    )

# =========================================================
# GEOMAG
# =========================================================

def get_geomagnetic_forecast():

    try:

        url = (
            "https://services.swpc.noaa.gov/"
            "json/planetary_k_index_1m.json"
        )

        response = requests.get(
            url,
            timeout=10
        )

        data = response.json()

        latest = data[-1]

        kp = float(latest["kp_index"])

        if kp < 3:
            level = "🟢 Спокойно"

        elif kp < 5:
            level = "🟡 Возмущения"

        elif kp < 7:
            level = "🟠 Буря"

        else:
            level = "🔴 Сильная буря"

        return (
            "🧲 ГЕОМАГНИТНЫЙ ПРОГНОЗ\n\n"
            f"Kp: {kp}\n"
            f"{level}"
        )

    except Exception as e:

        print("Geomagnetic error:", e)

        return "Ошибка геомагнитного прогноза"

# =========================================================
# KP GRAPH
# =========================================================

def generate_kp_graph():

    try:

        url = (
            "https://services.swpc.noaa.gov/"
            "json/planetary_k_index_1m.json"
        )

        response = requests.get(
            url,
            timeout=10
        )

        data = response.json()

        sample = data[-50:]

        times = []
        kp_values = []

        for d in sample:

            try:

                kp = float(d["kp_index"])

                t = d["time_tag"][11:16]

                times.append(t)

                kp_values.append(kp)

            except:
                pass

        plt.figure()

        plt.plot(
            times,
            kp_values,
            marker="o"
        )

        plt.axhspan(
            0,
            3,
            alpha=0.2,
            color="green"
        )

        plt.axhspan(
            3,
            5,
            alpha=0.2,
            color="yellow"
        )

        plt.axhspan(
            5,
            9,
            alpha=0.2,
            color="red"
        )

        plt.xticks(rotation=45)

        plt.ylim(0, 9)

        plt.title("Kp Index")

        plt.tight_layout()

        plt.savefig("kp.png")

        plt.close()

        return "kp.png"

    except Exception as e:

        print("KP graph error:", e)

        return None
#=========================================================
#  WEMOS GRAF
#========================================================

def generate_wemos_graphs():

    conn2 = sqlite3.connect(DB_FILE)

    cur = conn2.cursor()

    cur.execute("""
        SELECT
            timestamp,
            temp,
            humidity,
            wifi_rssi
        FROM wemos_data
        WHERE sensor_id = 2
        ORDER BY id DESC
        LIMIT 50
    """)

    rows = cur.fetchall()[::-1]

    conn2.close()

    if not rows:
        return None, None, None

    times = [r[0][-8:] for r in rows]

    temps = smooth_array([r[1] for r in rows])

    hums = smooth_array([r[2] for r in rows])

    rssi = smooth_array([r[3] for r in rows])

    # TEMPERATURE
    plt.figure()

    plt.plot(times, temps)

    plt.xticks(rotation=45)

    plt.title("Wemos Temperature")

    plt.tight_layout()

    plt.savefig("wemos_temp.png")

    plt.close()

    # HUMIDITY
    plt.figure()

    plt.plot(times, hums)

    plt.xticks(rotation=45)

    plt.title("Wemos Humidity")

    plt.tight_layout()

    plt.savefig("wemos_hum.png")

    plt.close()

    # RSSI
    plt.figure()

    plt.plot(times, rssi)

    plt.xticks(rotation=45)

    plt.title("WiFi RSSI")

    plt.tight_layout()

    plt.savefig("wemos_rssi.png")

    plt.close()

    return (
        "wemos_temp.png",
        "wemos_hum.png",
        "wemos_rssi.png"
    )

#=========================================================
#  PAGE HISTORY
#=========================================================

async def show_wemos_history(update, context):

    query = update.callback_query

    await query.answer()

    files = generate_wemos_graphs()

    if not files[0]:

        await query.message.reply_text(
            "Нет данных Wemos"
        )

        return

    await query.message.reply_text(
        "📈 История Wemos"
    )

    await query.message.reply_photo(
        open(files[0], "rb")
    )

    await query.message.reply_photo(
        open(files[1], "rb")
    )

    await query.message.reply_photo(
        open(files[2], "rb")
    )

    keyboard = [[
        InlineKeyboardButton(
            "⬅️ Назад",
            callback_data="back"
        )
    ]]

    await query.message.reply_text(
        "Меню:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
# =========================================================
# MENU
# =========================================================

async def start(update: Update,
                context: ContextTypes.DEFAULT_TYPE):

    keyboard = [

        [
            InlineKeyboardButton(
                "📊 Данные",
                callback_data="show_data"
            )
        ],

        [
            InlineKeyboardButton(
                "📈 Статистика",
                callback_data="stats"
            )
        ],

        [
            InlineKeyboardButton(
                "🌦 Прогноз",
                callback_data="weather"
            )
        ],


        [
            InlineKeyboardButton(
                "🧲 Геомагнитка",
                callback_data="geomag"
            )
        ],

        [
             InlineKeyboardButton(
                 "📡 Wemos",
                callback_data="wemos"
            )
        ],

        [
             InlineKeyboardButton(
                "📈 Wemos History",
                callback_data="wemos_history"
            )
        ],


           [

            InlineKeyboardButton(
                      "🌫 Воздух",
                 callback_data="air"
        )
          ],    




          [ 
             InlineKeyboardButton(
            "⬅️ Назад",
            callback_data="back"
        )
      ]


    ]

    await update.message.reply_text(
        "МЕТЕОСТАНЦИЯ",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================================================
# WEATHER FORECAST
# =========================================================

def get_weather_forecast():

    try:

        url = (
            "http://api.openweathermap.org/data/2.5/forecast"
            f"?q={CITY}"
            f"&appid={WEATHER_API_KEY}"
            "&units=metric"
            "&lang=ru"
        )

        response = requests.get(url)

        data = response.json()

        if data["cod"] != "200":
            return "Ошибка прогноза"

        forecast = {}

        for item in data["list"]:

            date = item["dt_txt"].split(" ")[0]

            forecast.setdefault(
                date,
                []
            ).append(item)

        result = "🌦 ПРОГНОЗ\n\n"

        i = 0

        for date, day_data in forecast.items():

            if i >= 3:
                break

            temps = [
                d["main"]["temp"]
                for d in day_data
            ]

            desc = day_data[0]["weather"][0]["description"]

            result += (
                f"{date}\n"
                f"🌡 {min(temps):.1f}"
                f"...{max(temps):.1f} °C\n"
                f"☁️ {desc}\n\n"
            )

            i += 1

        return result

    except Exception as e:

        print("Forecast error:", e)

        return "Ошибка прогноза"

# =========================================================
# BUTTON PAGES
# =========================================================

async def show_data(update, context):

    query = update.callback_query

    await query.answer()

    keyboard = [[
        InlineKeyboardButton(
            "⬅️ Назад",
            callback_data="back"
        )
    ]]

    await query.edit_message_text(
        get_latest_data_text(),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_stats(update, context):

    query = update.callback_query

    await query.answer()

    text = get_stats()

    await query.message.reply_text(text)

    files = generate_graphs()

    if files[0]:
        await query.message.reply_photo(open(files[0], "rb"))
        await query.message.reply_photo(open(files[1], "rb"))
        await query.message.reply_photo(open(files[2], "rb"))
        await query.message.reply_photo(open(files[3], "rb"))

    keyboard = [[
         InlineKeyboardButton(
                "⬅️ Назад",
                callback_data="back"
         )
    ]]

    await query.message.reply_text(
           "Меню:",
           reply_markup=InlineKeyboardMarkup(keyboard)
     ) 
async def show_weather(update, context):

    query = update.callback_query

    await query.answer()

    keyboard = [[
        InlineKeyboardButton(
            "⬅️ Назад",
            callback_data="back"
        )
    ]]

    await query.edit_message_text(
        get_weather_forecast(),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_geomag(update, context):

    query = update.callback_query

    await query.answer()

    text = get_geomagnetic_forecast()

    await query.message.reply_text(text)

    file = generate_kp_graph()

    if file:
        await query.message.reply_photo(
            open(file, "rb")
        )
    keyboard = [[
        InlineKeyboardButton(
            "⬅️ Назад",
            callback_data="back"
        )
    ]]

    await query.message.reply_text(
        "Меню:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )



# =========================================================
# SHOW AIR
# =========================================================

async def show_air(update, context):

    query = update.callback_query

    await query.answer()

    keyboard = [[
        InlineKeyboardButton(
            "⬅️ Назад",
            callback_data="back"
        )
    ]]

    await query.edit_message_text(
        get_air_text(),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================================================
# BACK
# =========================================================

async def back_to_menu(update, context):

    query = update.callback_query

    await query.answer()

    keyboard = [

        [
            InlineKeyboardButton(
                "📊 Данные",
                callback_data="show_data"
            )
        ],

        [
            InlineKeyboardButton(
                "📈 Статистика",
                callback_data="stats"
            )
        ],

        [
            InlineKeyboardButton(
                "🌦 Прогноз",
                callback_data="weather"
            )
        ],

        [
            InlineKeyboardButton(
                "🧲 Геомагнитка",
                callback_data="geomag"
            )
        ],

        [
             InlineKeyboardButton(
                  "📡 Wemos",
                  callback_data="wemos"
             )
         ],    
        
        [
            InlineKeyboardButton(
                 "📈 Wemos History",
                 callback_data="wemos_history"
            )
        ],

       [

            InlineKeyboardButton(
                      "🌫 Воздух",
                 callback_data="air"
        )
          ]    
    ]

    await query.edit_message_text(
        "МЕТЕОСТАНЦИЯ",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================================================
# BUTTON HANDLER
# =========================================================

async def button_handler(update, context):

    query = update.callback_query

    if query.data == "show_data":
        await show_data(update, context)

    elif query.data == "stats":
        await show_stats(update, context)

    elif query.data == "weather":
        await show_weather(update, context)

    elif query.data == "geomag":
        await show_geomag(update, context)

    elif query.data == "wemos":
        await show_wemos(update, context)

    elif query.data == "wemos_history":
         await show_wemos_history(update, context)

    elif query.data == "air":
         await show_air(update, context) 

    elif query.data == "back":
        await back_to_menu(update, context)
#=========================================================
# CLEAR BASE
#=========================================================
# =========================================================
# SQLITE CLEANUP
# =========================================================

async def cleanup_database():

    while True:

        try:

            conn2 = sqlite3.connect(DB_FILE)

            cur = conn2.cursor()

            # sensor_data
            cur.execute("""
                DELETE FROM sensor_data
                WHERE id NOT IN (
                    SELECT id
                    FROM sensor_data
                    ORDER BY id DESC
                    LIMIT 5000
                )
            """)

            # kp_data
            cur.execute("""
                DELETE FROM kp_data
                WHERE id NOT IN (
                    SELECT id
                    FROM kp_data
                    ORDER BY id DESC
                    LIMIT 5000
                )
            """)

            # wemos_data
            cur.execute("""
                DELETE FROM wemos_data
                WHERE id NOT IN (
                    SELECT id
                    FROM wemos_data
                    ORDER BY id DESC
                    LIMIT 5000
                )
            """)

            conn2.commit()

            conn2.close()

            print("SQLite cleanup complete")

        except Exception as e:

            print("Cleanup error:", e)

        # раз в 6 часов
        await asyncio.sleep(86400)
# =========================================================
# MAIN
# =========================================================

async def main():

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(
        CallbackQueryHandler(button_handler)
    )

    app.job_queue.run_repeating(
        check_aurora,
        interval=600,
        first=10
    )

    asyncio.create_task(log_sensors())

    asyncio.create_task(log_kp())

    asyncio.create_task(cleanup_database())

    await app.run_polling()
#=========================================================
#  WEMOS
#========================================================
async def show_wemos(update, context):

    query = update.callback_query

    await query.answer()

    keyboard = [[
        InlineKeyboardButton(
            "⬅️ Назад",
            callback_data="back"
        )
    ]]

    await query.edit_message_text(
        get_wemos_text(),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    loop = asyncio.get_event_loop()

    loop.run_until_complete(main())
