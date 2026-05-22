# 🌦 Meteo Dashboard
screenshots/dashboard-main.png
Modern IoT weather dashboard powered by FastAPI, Chart.js and ESP/Wemos sensors.

![dashboard](https://raw.githubusercontent.com/korot62/meteo-dashboard-bot/main/screenshots/dashboard-main.png)

---

# ✨ Features

- 🌡 Temperature monitoring
- 💧 Humidity monitoring
- 📈 Pressure history
- 💨 Wind speed & direction
- 🌌 Aurora forecast
- 🧲 Kp index visualization
- 🌫 MQ135 air quality sensor
- 📶 WiFi RSSI monitoring
- 📊 Real-time charts
- ⚡ FastAPI backend
- 📱 Mobile-friendly UI

---

# 🖥 Dashboard Preview

## Main Dashboard

![preview1](https://raw.githubusercontent.com/korot62/meteo-dashboard-bot/main/screenshots/Screenshot 2026-05-22 at 17-02-07 Meteo Dashboard.png)

## Air Quality

![preview2](https://raw.githubusercontent.com/korot62/meteo-dashboard-bot/main/screenshots/dashboard-air_quality.png)

---

# 🧰 Hardware

## Sensors

- BME280
- MQ135
- Wemos D1 Mini / ESP8266
- Optional wind sensor

## Server

- BananaPi M64
- HummingBoard i.MX6
- Linux server

---

# ⚙ Backend Stack

- Python
- FastAPI
- SQLite
- Requests
- Uvicorn

---

# 🎨 Frontend Stack

- HTML5
- CSS3
- JavaScript
- Chart.js

---

# 📦 Installation

## Clone repository

```bash
git clone https://github.com/korot62/meteo-dashboard-bot.git
cd meteo-dashboard
```

---

## Install dependencies

```bash
pip install fastapi uvicorn requests
```

---

## Run server

```bash
uvicorn api_server:app --host 0.0.0.0 --port 8000
```

---

# 🌍 Open dashboard

```text
http://SERVER_IP:8000
```

Example:

```text
http://192.168.1.50:8000
```

---

# 📂 Project Structure

```text
meteo-dashboard/
│
├── api_server.py
├── dashboard.html
├── sensors.db
├── static/
├── screenshots/
└── README.md
```

---

# 📡 API Endpoints

## Full sensor data

```text
/full
```

## Aurora status

```text
/aurora
```

---

# 🌫 Air Quality Levels

| PPM | Status |
|-----|--------|
| 0-400 | 🟢 Good |
| 400-800 | 🟡 Moderate |
| 800-1500 | 🟠 Poor |
| 1500+ | 🔴 Hazardous |

---

# 🚀 Future Plans

- WebSocket real-time updates
- PWA support
- Docker deployment
- MQTT support
- Home Assistant integration
- Telegram alerts
- Apple-style AQI UI
- Historical analytics

---

# 📸 Screenshots

Put screenshots here:

```text
screenshots/
```

Example files:

```text
dashboard-main.png
dashboard-air.png
dashboard-mobile.png
dashboard-graphs.png
```

---

# 🔒 License

MIT License

---

# 👨‍💻 Author

Made with ❤️ by korot62
