# Diesel-Tracker Berlin

Stündlicher Dieselpreis-Abgleich für eine Heim-Tankstelle, deren Umkreis (5 km) und ganz Berlin – mit Tagestiefs, Wochenverlauf und typischem Tagesprofil.

Datenquelle: Markttransparenzstelle für Kraftstoffe (MTS-K) via [Tankerkönig](https://creativecommons.tankerkoenig.de), Lizenz CC BY 4.0.

## Einrichtung (einmalig, ~5 Minuten)

1. **Repo anlegen** (z. B. `diesel-tracker-berlin`) und diesen Ordner hochladen bzw. pushen.
2. **Secret anlegen:** Settings → Secrets and variables → Actions → *New repository secret*
   - `TK_API_KEY` = dein Tankerkönig-API-Key
   - optional `TK_GIT_USER` / `TK_GIT_PASS`, falls das Historien-Archiv einen Login verlangt
3. **Erster Lauf:** Actions → „Dieselpreise stündlich“ → *Run workflow*.
   Prüfe im Log, ob die richtige Heim-Tankstelle erkannt wurde.
4. **Historie nachladen:** Actions → „Historie nachladen (Backfill)“ → *Run workflow* (Standard: 60 Tage).
5. **Dashboard:** Settings → Pages → Source *Deploy from a branch*, Branch `main`, Ordner `/docs`.
   (Pages bei privaten Repos braucht GitHub Pro – alternativ das Repo öffentlich machen; es enthält nur öffentliche Preisdaten, der API-Key liegt geschützt im Secret.)

Danach läuft alles automatisch: jede Stunde ein neuer Datenpunkt, das Dashboard aktualisiert sich mit.

## Anpassen

`config.json`:
- `home_station_id`: feste Tankstellen-ID (steht nach dem ersten Lauf in `data/stations.json`), sonst automatische Erkennung über `home_station_match`
- `local_radius_km`: Umkreis für den Nachbarschaftsvergleich
- `backfill_days`: Standard-Tiefe für den Backfill

## Dateien

| Datei | Inhalt |
|---|---|
| `data/berlin_hourly.csv` | je Stunde: Anzahl, Min, 25 %-Quantil, Median, Mittel aller geöffneten Berliner Tankstellen |
| `data/local_hourly.csv` | je Stunde und Tankstelle im Umkreis: Dieselpreis |
| `data/stations.json` | Stammdaten der Tankstellen |
| `docs/data.json` | verdichtete Daten fürs Dashboard |

Hinweise: GitHub startet Cron-Jobs teils ein paar Minuten verspätet. Die Live-Werte zählen nur geöffnete Tankstellen, die rekonstruierte Historie kennt keine Öffnungszeiten.
