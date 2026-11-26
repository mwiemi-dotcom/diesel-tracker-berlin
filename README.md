# Sprit-Tracker Berlin

Stündlicher Abgleich der Spritpreise (Diesel, Super E5, E10) für eine Heim-Tankstelle, deren Umkreis (5 km) und ganz Berlin – mit Tagestiefs, Wochenverlauf und typischem Tagesprofil. Dazu eine Umkreissuche für beliebige Adressen in Berlin und Ladesäulen.

**Dashboard:** https://mwiemi-dotcom.github.io/diesel-tracker-berlin/ (am Handy „Zum Home-Bildschirm“ hinzufügen)

## So funktioniert es

- GitHub Actions ruft jede Stunde die Tankerkönig-API ab (Secret `TK_API_KEY`), speichert die Werte in `data/` und baut `docs/data.json` (Verlauf) und `docs/latest.json` (Momentaufnahme aller Tankstellen im Raum Berlin).
- Das Dashboard (`docs/index.html`, GitHub Pages) zeigt den Verlauf der Heim-Tankstelle und filtert die Momentaufnahme nach Adresse/Standort, Radius und Kraftstoff. Suchen werden nicht gespeichert – beim Neuladen ist wieder die Heim-Tankstelle eingestellt.
- Ladesäulen kommen live aus OpenStreetMap (Overpass), ohne Preise.

## Anpassen (`config.json`)

- `home_station_id`: Tankerkönig-ID der Heim-Tankstelle (siehe `data/stations.json`)
- `local_radius_km`: Umkreis für den Verlauf
- `home`: Mittelpunkt für den Umkreis

## Quellen

Markttransparenzstelle für Kraftstoffe via Tankerkönig (CC BY 4.0) · © OpenStreetMap-Mitwirkende (ODbL) · Nominatim
