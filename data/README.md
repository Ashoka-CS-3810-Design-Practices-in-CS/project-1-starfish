# Network data

**Data version:** 0.1-draft (18 October 2026). **Network state:** after the 8 March 2026 openings.
**Verification status:** all 244 stations are `"verified": false`. The team must check each entry against the official DMRC map and set `verified` to `true` (in `source/stations.csv`, then regenerate).

## Files

| File | Edited how | Content |
|---|---|---|
| `source/stations.csv` | by hand | id (station code), name, lat, lon, aliases (`;`-separated), closed, verified, source |
| `source/lines.csv` | by hand | line id, name, colour |
| `source/services.csv` | by hand | one row per stop of each service, in order, with the running time from the previous stop and where that time came from |
| `transfers.json` | by hand | default transfer times, overrides, no-transfer pairs, walkways |
| `stations.json`, `lines.json`, `segments.json` | **generated** | `python tools/csv_to_json.py data/source data` |

After editing a CSV, regenerate the JSON and run `pytest` (the validator and the golden routes run on this data).

## Scope

Nine lines ([A6]): Red, Yellow, Blue, Green, Violet, Pink, Magenta, Grey, Airport Express. Noida Aqua Line and Rapid Metro are non-goals and are not included. The Golden Line is not in the [A6] list.

Services:
- **Blue:** `BLUE-MAIN` (Dwarka Sector 21 – Noida Electronic City) and `BLUE-BR` (Yamuna Bank – Vaishali).
- **Green:** `GREEN-MAIN` (Inderlok – Brigadier Hoshiyar Singh) and `GREEN-BR` (Kirti Nagar – Ashok Park Main).
- **Pink:** `PINK-RING` (`loop: true`, Majlis Park – … – Maujpur-Babarpur – … – Burari – back to Majlis Park) and `PINK-SPUR` (Maujpur-Babarpur – Shiv Vihar).
- **Magenta:** `MAG-1` (Krishna Park Extension – Botanical Garden) and `MAG-2` (Majlis Park – Deepali Chowk), with no transfer between them.
- One service each for Red, Yellow, Violet, Grey and Airport Express.

## Sources

| Field | Source |
|---|---|
| Station order and coordinates (230 stations) | DMRC static GTFS feed (`stops.txt`, `stop_times.txt`; feed dated 2023), published on the Delhi Open Transit Data portal (otd.delhi.gov.in). The copy used was a public mirror of that feed. |
| Running times (244 of 260 segments) | Median over all GTFS trips of (arrival at next stop − arrival at this stop), so the time includes the dwell at the first station. |
| Pink ring section (Majlis Park – Maujpur-Babarpur), Magenta `MAG-2` (Majlis Park – Deepali Chowk), Krishna Park Extension, Yashobhoomi Dwarka Sector 25 | Station order from Wikipedia line articles (checked October 2026); coordinates for the 14 new stations from OpenStreetMap (© OpenStreetMap contributors, ODbL). |
| Running times on those new sections (16 segments) | **Documented default of 120 s per segment.** No timetable source was available. Marked `default 120 s` in `services.csv`. |
| Station codes | Drafted 4-letter codes (first letters and consonants of the name). Not official DMRC codes; the team may replace them. |
| Display names | GTFS names, tidied to current names where they changed (e.g. Huda City Centre → Millennium City Centre Gurugram, Mayur Vihar Pocket 1 → Shree Ram Mandir Mayur Vihar). The old GTFS name is kept as an alias so search still finds it. |
| Transfer times | Team defaults: 240 s between different lines, 120 s for a branch change on the same line [A2/AS3]. |
| Walkways | Dhaula Kuan ↔ Durgabai Deshmukh South Campus (300 s) and Punjabi Bagh ↔ Punjabi Bagh West (240 s). Team estimates. |

## Known open questions for the team

1. **Soorghat** (Pink ring, between Nanaksar-Sonia Vihar and Jagatpur-Wazirabad) is listed as still under construction. It is left out of `PINK-RING` instead of being added as `closed`, because a closed station cuts its service in our model [D1] and trains do run through it.
2. **Madhuban Chowk:** the Red Line's Pitampura station has reportedly been renamed Madhuban Chowk, and the new Magenta station of the same name sits next to it, but the interchange is not open yet. They are modelled as two stations (`Pitampura` with alias "Madhuban Chowk (Red Line)", and the Magenta `Madhuban Chowk`) with no walkway.
3. **Through-running:** in reality some Blue and Green trains run through Yamuna Bank and Ashok Park Main without a change. Following the PRD, these are modelled as branch changes (two services each).
4. **Running times** come from a 2023 timetable and may have changed.

## Counts

- Stations: 244 (unverified: 244)
- Segments: 260 (GTFS-derived: 244; default 120 s: 16)
- Services: 13 on 9 lines
