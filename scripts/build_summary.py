"""Verdichtet die Rohdaten je Kraftstoff zu docs/data.json für das Dashboard."""
import json
import statistics
from collections import defaultdict
from datetime import datetime, timedelta

from common import (BERLIN_FILE, DOCS, FUELS, LOCAL_FILE, TZ, load_config, load_stations,
                    migrate, parse_ts, read_csv)


def r3(x):
    return None if x is None else round(x, 3)


def fuel_summary(fuel, berlin_rows, local_rows, stations, home_id):
    berlin = {parse_ts(r["ts"]): r for r in berlin_rows if r["fuel"] == fuel}
    local = defaultdict(dict)
    for r in local_rows:
        if r.get(fuel):
            local[parse_ts(r["ts"])][r["station_id"]] = float(r[fuel])
    all_ts = sorted(set(berlin) | set(local))
    if not all_ts:
        return None

    hourly = []
    for t in all_ts:
        lp, b = local.get(t, {}), berlin.get(t)
        hourly.append({
            "ts": t.isoformat(timespec="minutes"),
            "home": lp.get(home_id),
            "local_min": min(lp.values()) if lp else None,
            "local_median": r3(statistics.median(lp.values())) if lp else None,
            "berlin_min": float(b["min"]) if b else None,
            "berlin_median": float(b["median"]) if b else None,
        })

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
            "home_min": lo[0] if lo else None, "home_min_time": lo[1] if lo else None,
            "home_max": max(p for p, _ in home) if home else None,
            "home_avg": r3(statistics.fmean(p for p, _ in home)) if home else None,
            "local_min": min(lmin) if lmin else None,
            "berlin_min": min(bmin) if bmin else None,
            "berlin_median_avg": r3(statistics.fmean(bmed)) if bmed else None,
            "hours": len(hs),
        })

    cutoff = all_ts[-1] - timedelta(days=28)
    prof = {"home": defaultdict(list), "berlin": defaultdict(list)}
    davg = {d["date"]: d for d in daily}
    for h in hourly:
        t = datetime.fromisoformat(h["ts"])
        d = davg[h["ts"][:10]]
        if t < cutoff or d["hours"] < 20:
            continue
        if h["home"] is not None and d["home_avg"]:
            prof["home"][t.hour].append((h["home"] - d["home_avg"]) * 100)
        if h["berlin_median"] is not None and d["berlin_median_avg"]:
            prof["berlin"][t.hour].append((h["berlin_median"] - d["berlin_median_avg"]) * 100)
    profile = [{"hour": hr,
                "home_ct": round(statistics.fmean(prof["home"][hr]), 2) if prof["home"][hr] else None,
                "berlin_ct": round(statistics.fmean(prof["berlin"][hr]), 2) if prof["berlin"][hr] else None}
               for hr in range(24)]

    last_t, last = all_ts[-1], hourly[-1]
    week = [h["home"] for h in hourly
            if h["home"] is not None and datetime.fromisoformat(h["ts"]) >= last_t - timedelta(days=7)]
    week.sort()
    signal = None
    if last["home"] is not None and len(week) >= 24:
        signal = {"percentile": round(100 * sum(p < last["home"] for p in week) / len(week)),
                  "week_min": week[0], "week_max": week[-1], "week_median": r3(statistics.median(week))}
    table = []
    for sid, p in sorted(local.get(last_t, {}).items(), key=lambda kv: kv[1]):
        s = stations.get(sid, {})
        table.append({"id": sid, "brand": s.get("brand") or s.get("name"),
                      "street": f"{s.get('street') or ''} {s.get('houseNumber') or ''}".strip(),
                      "dist_km": s.get("dist_home_km"), "price": p, "home": sid == home_id,
                      "lat": s.get("lat"), "lng": s.get("lng")})
    return {
        "now": {**last, "signal": signal, "local_table": table},
        "hourly_14d": [h for h in hourly if datetime.fromisoformat(h["ts"]) >= last_t - timedelta(days=14)],
        "daily": daily[-90:],
        "hour_profile": profile,
    }


def main():
    migrate()
    cfg = load_config()
    stations = load_stations()
    home_id = next((k for k, v in stations.items() if v.get("home")), None)
    berlin_rows, local_rows = read_csv(BERLIN_FILE), read_csv(LOCAL_FILE)
    fuels = {f: s for f in FUELS if (s := fuel_summary(f, berlin_rows, local_rows, stations, home_id))}
    if not fuels:
        raise SystemExit("Keine Daten vorhanden.")
    hs = stations.get(home_id, {})
    out = {
        "generated": datetime.now(TZ).isoformat(timespec="minutes"),
        "home_label": cfg["home"]["label"],
        "local_radius_km": cfg["local_radius_km"],
        "home_station": {"id": home_id, "brand": hs.get("brand"), "lat": hs.get("lat"), "lng": hs.get("lng"),
                         "address": f"{hs.get('street') or ''} {hs.get('houseNumber') or ''}, {hs.get('postCode') or ''} {hs.get('place') or ''}".strip()},
        "fuels": fuels,
    }
    DOCS.mkdir(exist_ok=True)
    (DOCS / "data.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("data.json: " + ", ".join(f"{f}: {len(v['hourly_14d'])} h" for f, v in fuels.items()))


if __name__ == "__main__":
    main()
