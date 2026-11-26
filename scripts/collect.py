"""Stündlicher Abruf der aktuellen Dieselpreise (Tankerkönig / MTS-K).

Ein Aufruf der list.php mit 25 km um Berlin-Mitte deckt ganz Berlin ab.
Gespeichert werden:
  - Berlin-Statistik je Stunde (nur geöffnete Berliner Tankstellen)
  - Einzelpreise aller Tankstellen im Umkreis von local_radius_km um "home"
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime

from common import (BERLIN_COLS, BERLIN_FILE, LOCAL_COLS, LOCAL_FILE, TZ, berlin_stats,
                    haversine_km, hour_key, is_berlin, load_config, load_stations,
                    save_stations, upsert_csv)

API = "https://creativecommons.tankerkoenig.de/json/list.php"


def fetch_list(key, lat, lng, rad):
    q = urllib.parse.urlencode({"lat": lat, "lng": lng, "rad": rad, "sort": "dist",
                                "type": "diesel", "apikey": key})
    req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": "diesel-tracker-berlin/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    if not data.get("ok"):
        sys.exit(f"Tankerkönig-Fehler: {data.get('message')}")
    return data["stations"]


def resolve_home(cfg, stations):
    if cfg.get("home_station_id"):
        return cfg["home_station_id"]
    m = cfg.get("home_station_match", {})
    brand, street = m.get("brand", "").lower(), m.get("street", "").lower()
    cands = [s for s in stations.values() if s.get("local")]
    exact = [s for s in cands if brand in (s.get("brand") or "").lower()
             and street in (s.get("street") or "").lower()]
    pool = exact or [s for s in cands if brand in (s.get("brand") or "").lower()]
    if not pool:
        return None
    return min(pool, key=lambda s: s["dist_home_km"])["id"]


def main():
    key = os.environ.get("TK_API_KEY")
    if not key:
        sys.exit("TK_API_KEY fehlt (GitHub-Secret anlegen).")
    cfg = load_config()
    home, b = cfg["home"], cfg["berlin"]
    now = datetime.now(TZ)
    ts = hour_key(now)

    live = fetch_list(key, b["lat"], b["lng"], b["rad_km"])
    stations = load_stations()
    berlin_prices, local_rows = [], []
    for s in live:
        d_home = haversine_km(home["lat"], home["lng"], s["lat"], s["lng"])
        local = d_home <= cfg["local_radius_km"]
        stations[s["id"]] = {
            "id": s["id"], "name": s.get("name"), "brand": s.get("brand"),
            "street": s.get("street"), "houseNumber": s.get("houseNumber"),
            "postCode": s.get("postCode"), "place": s.get("place"),
            "lat": s["lat"], "lng": s["lng"], "dist_home_km": round(d_home, 2),
            "berlin": is_berlin(s), "local": local,
        }
        price = s.get("price")
        if not s.get("isOpen") or not isinstance(price, (int, float)) or price <= 0:
            continue
        if is_berlin(s):
            berlin_prices.append(price)
        if local:
            local_rows.append({"ts": ts, "station_id": s["id"], "price": price})

    home_id = resolve_home(cfg, stations)
    for st in stations.values():
        st["home"] = st["id"] == home_id
    save_stations(stations)

    stats = berlin_stats(berlin_prices)
    if stats:
        upsert_csv(BERLIN_FILE, BERLIN_COLS, [{"ts": ts, **stats}], ["ts"])
    upsert_csv(LOCAL_FILE, LOCAL_COLS, local_rows, ["ts", "station_id"])
    hs = stations.get(home_id, {})
    print(f"{ts}: {len(berlin_prices)} Berliner Preise, {len(local_rows)} lokal; "
          f"Heim-Tankstelle: {hs.get('brand')} {hs.get('street')} ({home_id})")


if __name__ == "__main__":
    main()
