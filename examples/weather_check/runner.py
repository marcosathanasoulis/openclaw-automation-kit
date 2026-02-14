from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any, Dict

WEATHER_CODE_TO_TEXT = {
    0: "Clear",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Dense drizzle",
    56: "Freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Rain",
    65: "Heavy rain",
    66: "Freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow",
    73: "Snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Rain showers",
    81: "Rain showers",
    82: "Violent rain showers",
    85: "Snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Severe thunderstorm with hail",
}


def _fetch_json(url: str) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "OpenClawAutomationKit/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


def _geocode_location(location: str) -> Dict[str, Any]:
    candidates = [location.strip()]
    if "," in location:
        candidates.append(location.split(",")[0].strip())

    for candidate in candidates:
        if not candidate:
            continue
        query = urllib.parse.urlencode({"name": candidate, "count": 1, "language": "en", "format": "json"})
        url = f"https://geocoding-api.open-meteo.com/v1/search?{query}"
        payload = _fetch_json(url)
        results = payload.get("results") or []
        if results:
            return results[0]
    raise ValueError(f"No geocoding result for '{location}'")


def _fetch_current_weather(latitude: float, longitude: float, temperature_unit: str) -> Dict[str, Any]:
    query = urllib.parse.urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,weather_code,wind_speed_10m",
            "temperature_unit": temperature_unit,
        }
    )
    url = f"https://api.open-meteo.com/v1/forecast?{query}"
    payload = _fetch_json(url)
    current = payload.get("current") or {}
    if not current:
        raise ValueError("Weather API returned no current data")
    return current


def run(context: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
    del context
    location = str(inputs["location"]).strip()
    temperature_unit = str(inputs.get("temperature_unit", "fahrenheit")).strip().lower()
    if temperature_unit not in {"fahrenheit", "celsius"}:
        temperature_unit = "fahrenheit"

    try:
        geo = _geocode_location(location)
        latitude = float(geo["latitude"])
        longitude = float(geo["longitude"])
        resolved_location = geo.get("name") or location

        current = _fetch_current_weather(latitude, longitude, temperature_unit)
        temperature = float(current.get("temperature_2m"))
        weather_code = int(current.get("weather_code", -1))
        condition = WEATHER_CODE_TO_TEXT.get(weather_code, f"Code {weather_code}")
        wind_speed_kmh = float(current.get("wind_speed_10m", 0.0))
        unit_symbol = "F" if temperature_unit == "fahrenheit" else "C"

        return {
            "location": location,
            "resolved_location": resolved_location,
            "latitude": latitude,
            "longitude": longitude,
            "temperature": temperature,
            "temperature_unit": temperature_unit,
            "condition": condition,
            "wind_speed_kmh": wind_speed_kmh,
            "summary": (
                f"Current weather for {resolved_location}: {temperature:.1f}°{unit_symbol}, "
                f"{condition}, wind {wind_speed_kmh:.1f} km/h."
            ),
            "errors": [],
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "location": location,
            "resolved_location": location,
            "latitude": 0.0,
            "longitude": 0.0,
            "temperature": 0.0,
            "temperature_unit": temperature_unit,
            "condition": "Unavailable",
            "wind_speed_kmh": 0.0,
            "summary": f"Failed to fetch weather for {location}",
            "errors": [str(exc)],
        }
