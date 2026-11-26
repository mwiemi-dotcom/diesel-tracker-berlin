"""Einmaliger (wiederholbarer) Backfill aus dem Tankerkönig-Historienarchiv.

Das Archiv enthält jede Preisänderung jeder Tankstelle (prices/YYYY/MM/YYYY-MM-DD-prices.csv).
Daraus wird für jede volle Stunde der zu dem Zeitpunkt gültige Preis rekonstruiert –
im gleichen Format wie der stündliche Live-Abruf. Bereits vorhandene Live-Stunden
werden nicht überschrieben.

Benötigt: data/stations.json (entsteht beim ersten collect.py-Lauf).
Optional: TK_GIT_USER / TK_GIT_PASS, falls das Archiv einen Login verlangt.
Aufruf: python scripts/backfill.py [TAGE]
"""
import csv
import io
import os
import subprocess
import sys
import tempfile
import urllib.parse
from datetime import date, datetime, timedelta, timezone

from common import (BERLIN_COLS, BERLIN_FILE, LOCAL_COLS, LOCAL_FILE, TZ, berlin_stats,
                    hour_key, load_config, load_stations, read_csv, upsert_csv)

REPO = "dev.azure.com/tankerkoenig/tankerkoenig-data/_git/tankerkoenig-data"
STALE = timedelta(days=3)   # Preise älter als 3 Tage gelten als inaktiv


def repo_url():
    u, p = os.environ.get("TK_GIT_USER"), os.environ.get("TK_GIT_PASS")
    if u and p:
        return f"https://{urllib.parse.quote(u, safe='')}:{urllib.parse.quote(p, safe='')}@{REPO}"
    return f"https://{REPO}"


def parse_hist_ts(s: str) -> datetime:
    s = s.strip()
    if len(s) >= 3 and s[-3] in "+-" and s[-2:].isdigit():   # "...+01" -> "...+01:00"
        s += ":00"
    return datetime.fromisoformat(s)


def day_events(repo_dir, d: date, ids):
    path = f"prices/{d:%Y}/{d:%m}/{d:%Y-%m-%d}-prices.csv"
    res = subprocess.run(["git", "-C", repo_dir, "show", f"HEAD:{path}"],
                         capture_output=True, text=True)
    if res.returncode != 0:
        print(f"  {d}: nicht im Archiv ({res.stderr.strip()[:80]})")
        return []
    ev = []
    for r in csv.DictReader(io.StringIO(res.stdout)):
        sid = r["station_uuid"]
        if sid not in ids:
            continue
        try:
            price = float(r["diesel"])
        except (TypeError, ValueError):
            continue
        if price <= 0.5:
            continue
        ev.append((parse_hist_ts(r["date"]), sid, price))
    ev.sort()
    return ev


def main():
    cfg = load_config()
    days = int(sys.argv[1]) if len(sys.argv) > 1 else cfg.get("backfill_days", 60)
    stations = load_stations()
    if not stations:
        sys.exit("data/stations.json fehlt – zuerst collect.py laufen lassen.")
    berlin_ids = {k for k, v in stations.items() if v.get("berlin")}
    local_ids = {k for k, v in stations.items() if v.get("local")}
    ids = berlin_ids | local_ids

    have_berlin = {r["ts"] for r in read_csv(BERLIN_FILE)}
    have_local = {(r["ts"], r["station_id"]) for r in read_csv(LOCAL_FILE)}

    today = datetime.now(TZ).date()
    first = today - timedelta(days=days)
    tmp = tempfile.mkdtemp(prefix="tk-")
    print("Klone Archiv (nur Metadaten, Dateien werden einzeln geladen) …")
    subprocess.run(["git", "clone", "--filter=blob:none", "--no-checkout", "--depth", "1",
                    repo_url(), tmp], check=True)

    state = {}  # sid -> (ts, price)
    berlin_rows, local_rows = [], []
    d = first - timedelta(days=1)   # Vortag nur für den Startzustand
    while d < today:
        ev = day_events(tmp, d, ids)
        start = datetime(d.year, d.month, d.day, tzinfo=TZ).astimezone(timezone.utc)
        nxt = d + timedelta(days=1)
        end = datetime(nxt.year, nxt.month, nxt.day, tzinfo=TZ).astimezone(timezone.utc)
        i, h = 0, start
        while h < end:
            while i < len(ev) and ev[i][0] <= h:
                t, sid, p = ev[i]
                state[sid] = (t, p)
                i += 1
            if d >= first:
                ts = hour_key(h)
                active = {sid: p for sid, (t, p) in state.items() if h - t <= STALE}
                if ts not in have_berlin:
                    st = berlin_stats([p for sid, p in active.items() if sid in berlin_ids])
                    if st:
                        berlin_rows.append({"ts": ts, **st})
                for sid in local_ids:
                    if sid in active and (ts, sid) not in have_local:
                        local_rows.append({"ts": ts, "station_id": sid, "price": active[sid]})
            h += timedelta(hours=1)
        for t, sid, p in ev[i:]:
            state[sid] = (t, p)
        if d >= first:
            print(f"  {d}: {len(ev)} Preisänderungen")
        d = nxt

    nb = upsert_csv(BERLIN_FILE, BERLIN_COLS, berlin_rows, ["ts"])
    nl = upsert_csv(LOCAL_FILE, LOCAL_COLS, local_rows, ["ts", "station_id"])
    print(f"Fertig: +{len(berlin_rows)} Berlin-Stunden ({nb} gesamt), +{len(local_rows)} lokale Werte ({nl} gesamt)")


if __name__ == "__main__":
    main()
