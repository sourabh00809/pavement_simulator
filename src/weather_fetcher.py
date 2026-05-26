import requests
import pandas as pd
from datetime import datetime, timedelta, date
from typing import Optional, Tuple


ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

HOURLY_PARAMS = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "rain",
]

DAILY_PARAMS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "rain_sum",
]


def _fetch_archive(lat: float, lon: float, start_date: str, end_date: str) -> pd.DataFrame:
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": HOURLY_PARAMS,
        "timezone": "auto",
    }
    response = requests.get(ARCHIVE_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    df = pd.DataFrame(data["hourly"])
    df["time"] = pd.to_datetime(df["time"])
    return df


def _fetch_forecast(lat: float, lon: float, start_date: str, end_date: str) -> pd.DataFrame:
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": HOURLY_PARAMS,
        "timezone": "auto",
    }
    response = requests.get(FORECAST_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    df = pd.DataFrame(data["hourly"])
    df["time"] = pd.to_datetime(df["time"])
    return df


def _datetime_to_days(df: pd.DataFrame) -> pd.DataFrame:
    if len(df) == 0:
        return df
    t0 = df["time"].iloc[0]
    df = df.copy()
    df["time"] = (df["time"] - t0).dt.total_seconds() / 86400.0
    return df


def fetch_weather(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    today = date.today()
    archive_cutoff = today - timedelta(days=2)

    start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()

    if end_dt <= archive_cutoff:
        df = _fetch_archive(lat, lon, start_date, end_date)
    elif start_dt >= today:
        df = _fetch_forecast(lat, lon, start_date, end_date)
    else:
        cutoff_str = archive_cutoff.strftime("%Y-%m-%d")
        next_day = (archive_cutoff + timedelta(days=1)).strftime("%Y-%m-%d")

        df_hist = _fetch_archive(lat, lon, start_date, cutoff_str)
        df_fcst = _fetch_forecast(lat, lon, next_day, end_date)
        df = pd.concat([df_hist, df_fcst], ignore_index=True)

    return _datetime_to_days(df)


def fetch_weather_by_days(
    lat: float,
    lon: float,
    days: int,
) -> pd.DataFrame:
    end_date = date.today() + timedelta(days=days)
    start_date = end_date - timedelta(days=days)
    return fetch_weather(
        lat, lon,
        start_date.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d"),
    )
