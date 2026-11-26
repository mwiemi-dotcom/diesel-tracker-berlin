"""Verdichtet die Rohdaten zu docs/data.json für das Dashboard."""
import json
import statistics
from collections import defaultdict
from datetime import datetime, timedelta

from common import (BERLIN_FILE, DOCS, LOCAL_FILE, TZ, load_config, load_stations,
                    parse_ts, read_csv)


def r3(x):
    return None if x is None else round(x, 3)


def main():
    cfg = load_config()
    stations = load_stations()
    home_id = next((k for k, v in stations.items() if v.get("home")), None)
    berlin = [(parse_ts(r["ts"]), r) for r in read_csv(BERLIN_FILE)]
    local = defaultdict(dict)   # ts -> {sid: price}
    for r in read_csv(LOCAL_FILE):
        local[parse_ts(r["ts"])][r["station_id"]] = float(r["price"])
    if not berlin and not local:
        raise SystemExit("Keine Daten vorhanden.")

    all_ts = sorted(set(t for t, _ in berlin) | set(local))
    bmap = {t: r for t, r in berlin}
    hourly = []
    for t in all_ts:
        lp = local.get(t, {})
        b = bmap.get(t)
        hourly.append({
            "ts": t.isoformat(timespec="minutes"),
            "home": lp.get(home_id),
            "local_min": min(lp.values()) if lp else None,
            "local_median": r3(statistics.median(lp.values())) if lp else None,
            "berlin_min": float(b["min"]) if b else None,
            "berlin_median": float(b["median"]) if b else None,
        })

    # Tageswerte
    by_day = defaultdict(list)
    for h in hourly:
        by_day[h["ts"][:10]].append(h)
    daily = []
    for day in sorted(by_day):
        hs = by_day[day]
        home = [(h["home"], h["ts"][11:16]) for h in hs if h["home"] is not None]
        lmin = [h["local_min"] for h in hs if h["local_min"] is not None]
        bmin = [h["berlin_min"] for h in hs if h["berlin_min"] is not None]
        bmed = [h["berlin_median"] for h in hs if h["berlin_median"] is not None]
        lo = min(home) if home else None
        daily.append({
            "date": day,
            "home_min": lo[0] if lo else None,
            "home_min_time": lo[1] if lo else None,
            "home_max": max(p for p, _ in home) if home else None,
            "home_avg": r3(statistics.fmean(p for p, _ in home)) if home else None,
            "local_min": min(lmin) if lmin else None,
            "berlin_min": min(bmin) if bmin else None,
            "berlin_median_avg": r3(statistics.fmean(bmed)) if bmed else None,
            "hours": len(hs),
        })

    # Stundenprofil der letzten 28 Tage: Abweichung vom jeweiligen Tagesmittel (in Cent)
    cutoff = all_ts[-1] - timedelta(days=28)
    prof = {"home": defaultdict(list), "berlin": defaultdict(list)}
    davg = {d["date"]: d for d in daily}
    for h in hourly:
        t = datetime.fromisoformat(h["ts"])
        if t < cutoff:
            continue
        d = davg[h["ts"][:10]]
        if d["hours"] < 20:
            continue
        if h["home"] is not None and d["home_avg"]:
            prof["home"][t.hour].append((h["home"] - d["home_avg"]) * 100)
        if h["berlin_median"] is not None and d["berlin_median_avg"]:
            prof["berlin"][t.hour].append((h["berlin_median"] - d["berlin_median_avg"]) * 100)
    profile = [{"hour": hr,
                "home_ct": round(statistics.fmean(prof["home"][hr]), 2) if prof["home"][hr] else None,
                "berlin_ct": round(statistics.fmean(prof["berlin"][hr]), 2) if prof["berlin"][hr] else None}
               for hr in range(24)]

    # Aktueller Stand
    last_t = all_ts[-1]
    last = hourly[-1]
    week = [h for h in hourly if datetime.fromisoformat(h["ts"]) >= last_t - timedelta(days=7)]
    wk_home = sorted(h["home"] for h in week if h["home"] is not None)
    signal = None
    if last["home"] is not None and len(wk_home) >= 24:
        below = sum(1 for p in wk_home if p < last["home"])
        signal = {"percentile": round(100 * below / len(wk_home)),
                  "week_min": wk_home[0], "week_max": wk_home[-1],
                  "week_median": r3(statistics.median(wk_home))}
    table = []
    for sid, p in sorted(local.get(last_t, {}).items(), key=lambda kv: kv[1]):
        s = stations.get(sid, {})
        table.append({"id": sid, "brand": s.get("brand") or s.get("name"),
                      "street": f"{s.get('street') or ''} {s.get('houseNumber') or ''}".strip(),
                      "dist_km": s.get("dist_home_km"), "price": p, "home": sid == home_id})

    hs = stations.get(home_id, {})
    out = {
        "generated": datetime.now(TZ).isoformat(timespec="minutes"),
        "home_label": cfg["home"]["label"],
        "local_radius_km": cfg["local_radius_km"],
        "home_station": {"id": home_id, "brand": hs.get("brand"),
                         "address": f"{hs.get('street') or ''} {hs.get('houseNumber') or ''}, {hs.get('postCode') or ''} {hs.get('place') or ''}".strip()},
        "now": {**last, "signal": signal, "local_table": table},
        "hourly_14d": [h for h in hourly if datetime.fromisoformat(h["ts"]) >= last_t - timedelta(days=14)],
        "daily": daily[-90:],
        "hour_profile": profile,
    }
    DOCS.mkdir(exist_ok=True)
    (DOCS / "data.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"data.json: {len(hourly)} Stunden, {len(daily)} Tage, Stand {last['ts']}")


if __name__ == "__main__":
    main()
