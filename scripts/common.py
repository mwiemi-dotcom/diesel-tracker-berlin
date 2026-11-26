"""Gemeinsame Helfer: Pfade, Konfiguration, Geo, CSV-Speicher."""
import csv
import json
import math
import statistics
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Berlin")
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DOCS = ROOT / "docs"
STATIONS_FILE = DATA / "stations.json"
LOCAL_FILE = DATA / "local_hourly.csv"      # ts, station_id, price
BERLIN_FILE = DATA / "berlin_hourly.csv"    # ts, n, min, p25, median, mean

LOCAL_COLS = ["ts", "station_id", "price"]
BERLIN_COLS = ["ts", "n", "min", "p25", "median", "mean"]


def load_config():
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def haversine_km(lat1, lng1, lat2, lng2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def hour_key(d: datetime) -> str:
    """Volle Stunde in Berliner Zeit mit Offset, z. B. 2026-11-26T08:00+01:00."""
    d = d.astimezone(TZ).replace(minute=0, second=0, microsecond=0)
    return d.isoformat(timespec="minutes")


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s).astimezone(TZ)


def is_berlin(st: dict) -> bool:
    place = (st.get("place") or "").strip().lower()
    return place.startswith("berlin")


def load_stations() -> dict:
    if STATIONS_FILE.exists():
        return json.loads(STATIONS_FILE.read_text(encoding="utf-8"))
    return {}


def save_stations(stations: dict):
    DATA.mkdir(exist_ok=True)
    STATIONS_FILE.write_text(json.dumps(stations, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def berlin_stats(prices):
    prices = sorted(p for p in prices if p and p > 0.5)
    if not prices:
        return None
    q = statistics.quantiles(prices, n=4) if len(prices) >= 2 else [prices[0]] * 3
    return {
        "n": len(prices),
        "min": round(prices[0], 3),
        "p25": round(q[0], 3),
        "median": round(statistics.median(prices), 3),
        "mean": round(statistics.fmean(prices), 4),
    }


def read_csv(path: Path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def upsert_csv(path: Path, cols, new_rows, key_fields):
    """Fügt Zeilen ein; vorhandene Zeilen mit gleichem Schlüssel werden ersetzt."""
    rows = {tuple(r[k] for k in key_fields): r for r in read_csv(path)}
    for r in new_rows:
        rows[tuple(str(r[k]) for k in key_fields)] = {c: r[c] for c in cols}
    out = sorted(rows.values(), key=lambda r: (parse_ts(r["ts"]), *(r[k] for k in key_fields[1:])))
    DATA.mkdir(exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out)
    return len(out)
