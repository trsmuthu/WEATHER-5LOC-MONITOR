#!/usr/bin/env python3
"""
5-Location Environmental & Hourly Prediction Monitor (IST 7:00 AM - 7:00 PM)
Features:
  - 1-Hour Prediction & Forecast for SUNNY / RAIN / WIND across 5 locations
  - Real-time Rain Probability (%) and Precipitation Volume (mm)
  - Wind Speed & Gust Threshold Warnings (> 20 km/h or gusts > 30 km/h)
  - Daily High & Low Temperatures for each location
  - Automated push notifications to iPhone via ntfy every hour from 7 AM to 7 PM IST
  - Auto-sleep during night hours (8:00 PM to 6:59 AM IST)

Locations:
  1. New Delhi: 28.500028, 77.266119
  2. KRC: 10.873525, 77.658080
  3. Manora Beach: 10.266353, 79.300686
  4. Germala Checkpost: 11.773330, 77.225213
  5. Kings College: 10.648149, 79.066893
"""

import sys
import os
import time
import json
import ssl
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta

# iPhone ntfy channel
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "weather-5loc-muthu")

LOCATIONS = [
    {
        "name": "New Delhi",
        "lat": 28.500028,
        "lon": 77.266119,
    },
    {
        "name": "KRC",
        "lat": 10.873525,
        "lon": 77.658080,
    },
    {
        "name": "Manora Beach",
        "lat": 10.266353,
        "lon": 79.300686,
    },
    {
        "name": "Germala Checkpost",
        "lat": 11.773330,
        "lon": 77.225213,
    },
    {
        "name": "Kings College",
        "lat": 10.648149,
        "lon": 79.066893,
    },
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def degrees_to_cardinal(d):
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    ix = round(d / (360. / len(dirs)))
    return dirs[ix % len(dirs)]


def decode_wmo_weather(code):
    """Maps WMO Weather codes to emojis, descriptions, and rain flags."""
    wmo_map = {
        0: ("☀️", "Clear / Sunny", False),
        1: ("🌤️", "Mainly Clear", False),
        2: ("⛅", "Partly Cloudy", False),
        3: ("☁️", "Overcast", False),
        45: ("🌫️", "Foggy", False),
        48: ("🌫️", "Depositing Rime Fog", False),
        51: ("🌦️", "Light Drizzle", True),
        53: ("🌦️", "Moderate Drizzle", True),
        55: ("🌧️", "Dense Drizzle", True),
        61: ("🌦️", "Slight Rain", True),
        63: ("🌧️", "Moderate Rain", True),
        65: ("🌧️", "Heavy Rain", True),
        71: ("🌨️", "Slight Snow", True),
        73: ("🌨️", "Moderate Snow", True),
        75: ("🌨️", "Heavy Snow", True),
        80: ("🌦️", "Slight Showers", True),
        81: ("🌧️", "Moderate Showers", True),
        82: ("⛈️", "Violent Showers", True),
        95: ("⛈️", "Thunderstorm", True),
        96: ("⛈️", "Thunderstorm with Hail", True),
        99: ("⛈️", "Heavy Thunderstorm", True),
    }
    return wmo_map.get(code, ("🌡️", "Cloudy", False))


def fetch_weather_and_prediction(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}&"
        f"current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m&"
        f"hourly=temperature_2m,precipitation_probability,precipitation,weather_code,wind_speed_10m,wind_gusts_10m&"
        f"daily=temperature_2m_max,temperature_2m_min&"
        f"forecast_hours=6&timezone=Asia/Kolkata"
    )
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15, context=CTX) as resp:
        return json.loads(resp.read().decode("utf-8"))


def send_iphone_push(title, body, is_urgent=False):
    endpoint = f"https://ntfy.sh/{NTFY_TOPIC}"
    payload = body.encode("utf-8")
    
    req = urllib.request.Request(endpoint, data=payload, method="POST")
    # Pure ASCII title to avoid latin-1 header encoding issues
    clean_title = title.encode("ascii", "ignore").decode("ascii")
    req.add_header("Title", clean_title)
    req.add_header("Priority", "urgent" if is_urgent else "default")
    req.add_header("Tags", "rotating_light,umbrella,wind_blowing_face" if is_urgent else "sunny,partly_sunny")
    req.add_header("Click", "https://open-meteo.com/")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"[PUSH SENT] -> iPhone ({NTFY_TOPIC})")
            return True
    except Exception as e:
        print(f"[FAILED TO SEND PUSH] {e}")
        return False


def build_hourly_prediction_report():
    ist = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist)
    timestamp = now_ist.strftime("%d %b, %I:%M %p IST")

    print(f"[{timestamp}] Generating Hourly Prediction (Sunny / Rain / Wind)...")
    
    active_alerts = []
    location_cards = []

    for idx, loc in enumerate(LOCATIONS, 1):
        name = loc["name"]
        lat = loc["lat"]
        lon = loc["lon"]

        try:
            raw = fetch_weather_and_prediction(lat, lon)
            cur = raw.get("current", {})
            daily = raw.get("daily", {})
            hr = raw.get("hourly", {})

            temp = round(cur.get("temperature_2m", 0), 1)
            feels = round(cur.get("apparent_temperature", 0), 1)
            humidity = cur.get("relative_humidity_2m", 0)
            cur_rain = cur.get("precipitation", 0.0)
            wcode = cur.get("weather_code", 0)
            cur_wind = round(cur.get("wind_speed_10m", 0), 1)
            cur_gusts = round(cur.get("wind_gusts_10m", 0), 1)
            wind_dir = degrees_to_cardinal(cur.get("wind_direction_10m", 0))

            # Daily High / Low
            temp_max = round(daily.get("temperature_2m_max", [temp])[0], 1)
            temp_min = round(daily.get("temperature_2m_min", [temp])[0], 1)

            cur_icon, cur_desc, is_raining_now = decode_wmo_weather(wcode)

            # --- HOURLY PREDICTION (Next 1 to 3 Hours) ---
            next_probs = hr.get("precipitation_probability", [0] * 3)[:3]
            next_rain = hr.get("precipitation", [0.0] * 3)[:3]
            next_winds = hr.get("wind_speed_10m", [cur_wind] * 3)[:3]
            next_gusts = hr.get("wind_gusts_10m", [cur_gusts] * 3)[:3]

            max_prob = max(next_probs) if next_probs else 0
            total_pred_rain = sum(next_rain)
            max_pred_wind = max(next_winds) if next_winds else cur_wind
            max_pred_gust = max(next_gusts) if next_gusts else cur_gusts

            # 1. SUNNY / SKY PREDICTION
            if max_prob < 20 and cur_rain == 0:
                sky_prediction = "☀️ Sunny / Clear"
            elif max_prob < 50:
                sky_prediction = "⛅ Partly Cloudy"
            else:
                sky_prediction = "🌧️ Overcast / Rain Clouds"

            # 2. RAIN PREDICTION & ALERT
            has_rain_alert = False
            if is_raining_now or cur_rain > 0:
                rain_prediction = f"🌧️ Active Rain ({cur_rain}mm, {max_prob}% chance)"
                active_alerts.append(f"🌧️ RAIN ACTIVE at {name}: {cur_desc} ({cur_rain}mm)")
                has_rain_alert = True
            elif max_prob >= 50 or total_pred_rain >= 0.5:
                rain_prediction = f"🌧️ Rain Imminent ({max_prob}% chance, ~{round(total_pred_rain,1)}mm)"
                active_alerts.append(f"🌧️ RAIN PREDICTED at {name}: {max_prob}% chance (~{round(total_pred_rain,1)}mm)")
                has_rain_alert = True
            elif max_prob >= 25:
                rain_prediction = f"🌦️ Possible Light Rain ({max_prob}% chance)"
            else:
                rain_prediction = "☀️ Dry (0-20% chance)"

            # 3. WIND PREDICTION & ALERT
            has_wind_alert = False
            if cur_wind >= 20.0 or max_pred_wind >= 20.0 or max_pred_gust >= 30.0:
                wind_prediction = f"💨 High Wind ({round(max_pred_wind,1)} km/h, Gusts {round(max_pred_gust,1)} km/h) ⚠️"
                active_alerts.append(f"💨 WIND ALERT at {name}: {round(max_pred_wind,1)} km/h (Gusts {round(max_pred_gust,1)})")
                has_wind_alert = True
            elif max_pred_wind >= 12.0:
                wind_prediction = f"🍃 Moderate Breeze ({round(max_pred_wind,1)} km/h {wind_dir})"
            else:
                wind_prediction = f"🍃 Gentle / Calm ({round(max_pred_wind,1)} km/h)"

            # Format Badge
            badges = []
            if has_rain_alert:
                badges.append("RAIN")
            if has_wind_alert:
                badges.append("WIND")
            badge_str = " ⚠️ [" + " & ".join(badges) + "]" if badges else ""

            card = (
                f"📍 {idx}. {name}{badge_str}\n"
                f"   {cur_icon} {cur_desc} · 🌡️ {temp}°C (Low: {temp_min}° / High: {temp_max}°)\n"
                f"   🔮 1-3H PREDICTION:\n"
                f"      • Sky: {sky_prediction}\n"
                f"      • Rain: {rain_prediction}\n"
                f"      • Wind: {wind_prediction}\n"
            )
            location_cards.append(card)

        except Exception as e:
            print(f"Error fetching {name}: {e}")
            location_cards.append(f"📍 {idx}. {name}: Data temporarily unavailable\n")

    # Header with Alerts
    header = f"🔮 1-HR PREDICTION: SUNNY / RAIN / WIND\n⏰ Time: {timestamp}\n\n"
    if active_alerts:
        header += "🚨 ACTIVE & UPCOMING WARNINGS:\n" + "\n".join(active_alerts) + "\n\n"
    else:
        header += "✅ ALL 5 LOCATIONS CALM & CLEAR (No severe rain or wind).\n\n"

    full_report = header + "".join(location_cards)
    is_urgent = len(active_alerts) > 0
    return full_report, is_urgent


def main():
    if "--test" in sys.argv:
        print("Sending test notification to iPhone...")
        send_iphone_push(
            "Hourly Prediction Connected!",
            "1-Hour Prediction Alerts for Sunny, Rain, and Wind are active!",
            is_urgent=False
        )
        return

    # Check active daytime window (7:00 AM to 7:00 PM IST)
    ist = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist)
    is_manual = "--force" in sys.argv or "--manual" in sys.argv or os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch"

    # Auto-sleep during night hours (8:00 PM to 6:59 AM IST) unless manually triggered
    if not is_manual and not (7 <= now_ist.hour <= 19):
        print(f"[{now_ist.strftime('%d %b, %I:%M %p IST')}] Night time (outside 7 AM - 7 PM IST). Staying silent so you can sleep.")
        return

    report, is_urgent = build_hourly_prediction_report()
    print("========================================")
    print(" 5-LOCATION HOURLY PREDICTION")
    print("========================================")
    print(report)

    title = "WEATHER ALERT: Rain / Wind" if is_urgent else "HOURLY PREDICTION: Sunny / Calm"
    send_iphone_push(title, report, is_urgent=is_urgent)


if __name__ == "__main__":
    main()
