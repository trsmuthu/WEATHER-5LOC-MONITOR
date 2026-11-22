#!/usr/bin/env python3
"""5-Location Weather & Environmental Real-Time Monitor

Locations:
  1. New Delhi: 28.500028, 77.266119
  2. KRC: 10.873525, 77.658080
  3. Manora Beach: 10.266353, 79.300686
  4. Germala Checkpost: 11.773330, 77.225213
  5. Kings College: 10.648149, 79.066893

Delivers unified 5-location report to iPhone via ntfy every 3 hours.
"""

import json
import os
import ssl
import sys
import time
import urllib.parse
import urllib.request

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
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    ),
    "Accept": "application/json",
}

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def degrees_to_cardinal(d):
  dirs = [
      "N",
      "NNE",
      "NE",
      "ENE",
      "E",
      "ESE",
      "SE",
      "SSE",
      "S",
      "SSW",
      "SW",
      "WSW",
      "W",
      "WNW",
      "NW",
      "NNW",
  ]
  ix = round(d / (360.0 / len(dirs)))
  return dirs[ix % len(dirs)]


def decode_wmo_weather(code):
  """Maps WMO Weather codes to emojis & short descriptions."""
  wmo_map = {
      0: ("☀️", "Clear"),
      1: ("🌤️", "Mainly Clear"),
      2: ("⛅", "Partly Cloudy"),
      3: ("☁️", "Overcast"),
      45: ("🌫️", "Fog"),
      48: ("🌫️", "Rime Fog"),
      51: ("🌦️", "Light Drizzle"),
      53: ("🌦️", "Moderate Drizzle"),
      55: ("🌧️", "Dense Drizzle"),
      61: ("🌦️", "Slight Rain"),
      63: ("🌧️", "Moderate Rain"),
      65: ("🌧️", "Heavy Rain"),
      71: ("🌨️", "Slight Snow"),
      73: ("🌨️", "Moderate Snow"),
      75: ("🌨️", "Heavy Snow"),
      80: ("🌦️", "Slight Showers"),
      81: ("🌧️", "Moderate Showers"),
      82: ("⛈️", "Violent Showers"),
      95: ("⛈️", "Thunderstorm"),
      96: ("⛈️", "Thunderstorm with Hail"),
      99: ("⛈️", "Heavy Thunderstorm"),
  }
  return wmo_map.get(code, ("🌡️", "Cloudy"))


def fetch_weather(lat, lon):
  url = (
      f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,wind_direction_10m&timezone=Asia/Kolkata"
  )
  req = urllib.request.Request(url, headers=HEADERS)
  with urllib.request.urlopen(req, timeout=15, context=CTX) as resp:
    data = json.loads(resp.read().decode("utf-8"))
    return data.get("current", {})


def send_iphone_push(title, body):
  endpoint = f"https://ntfy.sh/{NTFY_TOPIC}"
  payload = body.encode("utf-8")

  req = urllib.request.Request(endpoint, data=payload, method="POST")
  req.add_header("Title", title)
  req.add_header("Priority", "default")
  req.add_header("Tags", "cloud,thermometer,round_pushpin")
  req.add_header("Click", "https://open-meteo.com/")

  try:
    with urllib.request.urlopen(req, timeout=15) as resp:
      print(f"[PUSH SENT] -> iPhone ({NTFY_TOPIC})")
      return True
  except Exception as e:
    print(f"[FAILED TO SEND PUSH] {e}")
    return False


def build_5loc_report():
  print(
      f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Fetching environmental data for"
      " 5 locations..."
  )

  timestamp = time.strftime("%d %b, %I:%M %p IST")
  report_lines = [f"Updated: {timestamp}\n"]

  alerts = []

  for idx, loc in enumerate(LOCATIONS, 1):
    name = loc["name"]
    lat = loc["lat"]
    lon = loc["lon"]

    try:
      cur = fetch_weather(lat, lon)
      temp = round(cur.get("temperature_2m", 0), 1)
      feels = round(cur.get("apparent_temperature", 0), 1)
      humidity = cur.get("relative_humidity_2m", 0)
      precip = cur.get("precipitation", 0.0)
      wcode = cur.get("weather_code", 0)
      wind_spd = round(cur.get("wind_speed_10m", 0), 1)
      wind_dir = degrees_to_cardinal(cur.get("wind_direction_10m", 0))

      icon, desc = decode_wmo_weather(wcode)

      report_lines.append(f"📍 {idx}. {name}")
      report_lines.append(f"   {icon} {desc} · 🌡️ {temp}°C (Feels {feels}°)")
      report_lines.append(
          f"   💧 {humidity}% · 💨 {wind_spd} km/h {wind_dir} · 🌧️ {precip}mm\n"
      )

      if precip > 0.5:
        alerts.append(f"🌧️ Rain at {name} ({precip}mm)")
      if wind_spd >= 25:
        alerts.append(f"💨 High Wind at {name} ({wind_spd} km/h)")

    except Exception as e:
      print(f"Error fetching {name}: {e}")
      report_lines.append(f"📍 {idx}. {name}: Data temporarily unavailable\n")

  if alerts:
    report_lines.append("⚠️ Alerts: " + " · ".join(alerts))

  full_report = "\n".join(report_lines)
  return full_report


def main():
  if "--test" in sys.argv:
    print("Sending test notification to iPhone...")
    send_iphone_push(
        "5-Location Weather Connected!",
        "Your 5-Location Weather & Environmental Monitor is now linked to your"
        " iPhone!",
    )
    return

  report = build_5loc_report()
  print("========================================")
  print(" 5-LOCATION WEATHER & ENVIRONMENT")
  print("========================================")
  print(report)

  send_iphone_push("5-Location Weather & Environment", report)


if __name__ == "__main__":
  main()
