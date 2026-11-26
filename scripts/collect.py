"""Stündlicher Abruf der aktuellen Spritpreise (Diesel, E5, E10) via Tankerkönig / MTS-K.

Ein Aufruf der list.php (type=all) mit 25 km um Berlin-Mitte deckt ganz Berlin ab.
Gespeichert werden:
  - Berlin-Statistik je Stunde und Kraftstoff (nur geöffnete Berliner Tankstellen)
  - Einzelpreise aller Tankstellen im Umkreis von local_radius_km um "home"
  - docs/latest.json: Momentaufnahme aller Tankstellen für die Umkreissuche im Dashboard
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime

from common import (BERLIN_COLS, BERLIN_FILE, DOCS, FUELS, LOCAL_COLS, LOCAL_FILE, TZ,
                    haversine_km, hour_key, is_berlin, load_config, load_stations, migrate,
                    price_stats, save_stations, upsert_csv, valid_price)

API = "https://creativecommons.tankerkoenig.de/json/list.php"


def fetch_list(key, lat, lng, rad):
    q = urllib.parse.urlencode({"lat": lat, "lng": lng, "rad": rad, "sort": "dist",
                                "type": "all", "apikey": key})
    req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": "diesel-tracker-berlin/1.1"})
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
    pool = [s for s in cands if brand in (s.get("brand") or "").lower()
            and street in (s.get("street") or "").lower()] or cands
    return min(pool, key=lambda s: s["dist_home_km"])["id"] if pool else None


def main():
    key = os.environ.get("TK_API_KEY")
    if not key:
        sys.exit("TK_API_KEY fehlt (GitHub-Secret anlegen).")
    migrate()
    cfg = load_config()
    home, b = cfg["home"], cfg["berlin"]
    now = datetime.now(TZ)
    ts = hour_key(now)

    live = fetch_list(key, b["lat"], b["lng"], b["rad_km"])
    stations = load_stations()
    berlin_prices = {f: [] for f in FUELS}
    local_rows, snapshot = [], []
    for s in live:
        d_home = haversine_km(home["lat"], home["lng"], s["lat"], s["lng"])
        local = d_home <= cfg["local_radius_km"]
        meta = {
            "id": s["id"], "name": s.get("name"), "brand": s.get("brand"),
            "street": s.get("street"), "houseNumber": s.get("houseNumber"),
            "postCode": s.get("postCode"), "place": s.get("place"),
            "lat": s["lat"], "lng": s["lng"], "dist_home_km": round(d_home, 2),
            "berlin": is_berlin(s), "local": local,
        }
        stations[s["id"]] = meta
        open_ = bool(s.get("isOpen"))
        prices = {f: (s.get(f) if valid_price(s.get(f)) else None) for f in FUELS}
        snapshot.append({
            "id": s["id"], "brand": (s.get("brand") or s.get("name") or "").strip(),
            "addr": f"{(s.get('street') or '').strip()} {(s.get('houseNumber') or '').strip()}".strip(),
            "plz": str(s.get("postCode") or ""), "place": (s.get("place") or "").strip(),
            "lat": s["lat"], "lng": s["lng"], "open": open_, **prices,
        })
        if not open_:
            continue
        if is_berlin(s):
            for f in FUELS:
                if prices[f]:
                    berlin_prices[f].append(prices[f])
        if local and any(prices.values()):
            local_rows.append({"ts": ts, "station_id": s["id"], **{f: prices[f] or "" for f in FUELS}})

    home_id = resolve_home(cfg, stations)
    for st in stations.values():
        st["home"] = st["id"] == home_id
    save_stations(stations)

    berlin_rows = [{"ts": ts, "fuel": f, **st} for f in FUELS if (st := price_stats(berlin_prices[f]))]
    upsert_csv(BERLIN_FILE, BERLIN_COLS, berlin_rows, ["ts", "fuel"])
    upsert_csv(LOCAL_FILE, LOCAL_COLS, local_rows, ["ts", "station_id"])

    DOCS.mkdir(exist_ok=True)
    (DOCS / "latest.json").write_text(json.dumps(
        {"ts": now.isoformat(timespec="minutes"), "home_id": home_id, "stations": snapshot},
        ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    hs = stations.get(home_id, {})
    print(f"{ts}: {len(live)} Tankstellen, Berlin Diesel n={len(berlin_prices['diesel'])}, "
          f"{len(local_rows)} lokal; Heim: {hs.get('brand')} ({home_id})")


if __name__ == "__main__":
    main()
