"""
Prepare browser-ready data for the Leaflet map (17-region version).

Reads:
    data/raw/bfa_admin1.geojson                                    (17 new regions)
    data/raw/bfa_admin2.geojson                                    (47 new provinces, with adm2_pcode_old + adm1_pcode_new)
    data/raw/bfa_admpop_2023_5yr.xlsx (sheet bfa_admpop_adm2_2023) (UNFPA 2023 admin2 5-yr age bands)
    data/raw/bfa_acled_monthly_political_violence.xlsx             (ACLED per-province monthly)
    data/raw/bfa_acled_monthly_demonstrations.xlsx                 (ACLED per-province monthly)
    data/raw/bfa_osm_schools.json                                  (OSM schools via Overpass)
    data/raw/bfa_idmc_events.csv                                   (IDMC displacement events)

Writes:
    docs/data/regions.geojson           (simplified 17-region polygons)
    docs/data/events_by_region.json     (one record per NEW region)
    docs/data/schools.json              (compact [lat, lon] pairs)
    docs/data/displacement.json         (recent IDMC events)

Key trick: ACLED and UNFPA both use the OLD admin2 pcodes (45 provinces).
The COD admin2 file carries adm2_pcode_old + adm1_pcode_new, giving us
a clean province -> new region mapping that aggregates correctly.
"""

from collections import defaultdict
from datetime import timedelta
from pathlib import Path
import json

import pandas as pd
from shapely.geometry import shape, mapping, Point
from shapely.strtree import STRtree

POP_XLSX = Path("data/raw/bfa_admpop_2023_5yr.xlsx")
ACLED_PV = Path("data/raw/bfa_acled_monthly_political_violence.xlsx")
ACLED_DM = Path("data/raw/bfa_acled_monthly_demonstrations.xlsx")
SCHOOLS_IN = Path("data/raw/bfa_osm_schools.json")
IDMC_IN = Path("data/raw/bfa_idmc_events.csv")
ADMIN1_IN = Path("data/raw/bfa_admin1.geojson")
ADMIN2_IN = Path("data/raw/bfa_admin2.geojson")

EVENTS_OUT = Path("docs/data/events_by_region.json")
REGIONS_OUT = Path("docs/data/regions.geojson")
SCHOOLS_OUT = Path("docs/data/schools.json")
DISPLACEMENT_OUT = Path("docs/data/displacement.json")

WINDOW_MONTHS = 12
SIMPLIFY_TOLERANCE_DEG = 0.005


def province_to_new_region() -> dict:
    """Return {adm2_pcode_old: (adm1_pcode_new, adm1_name_new)}."""
    g = json.load(open(ADMIN2_IN))
    out: dict = {}
    for feat in g["features"]:
        p = feat["properties"]
        out[p["adm2_pcode_old"]] = (p["adm1_pcode"], p["adm1_name"])
    return out


def new_region_centroids() -> dict:
    """Return {adm1_pcode_new: (lat, lon, name)} using polygon centroids."""
    g = json.load(open(ADMIN1_IN))
    out: dict = {}
    for feat in g["features"]:
        p = feat["properties"]
        c = shape(feat["geometry"]).centroid
        out[p["adm1_pcode"]] = (c.y, c.x, p["adm1_name"])
    return out


def school_age_by_new_region(prov_to_region: dict) -> dict:
    """{adm1_pcode_new: school_age (5-14)} aggregated from UNFPA province data."""
    df = pd.read_excel(POP_XLSX, sheet_name="bfa_admpop_adm2_2023")
    df["school_age"] = df["T_05_09"] + df["T_10_14"]
    out: dict = defaultdict(int)
    for r in df.itertuples():
        match = prov_to_region.get(r.ADM2_PCODE)
        if match:
            out[match[0]] += int(r.school_age)
    return dict(out)


def acled_per_new_region(prov_to_region: dict) -> dict:
    """
    {adm1_pcode_new: {events_total, fatalities, breakdown:{...}, period_start, period_end}}
    Combines political-violence and demonstrations, filtered to the last
    WINDOW_MONTHS months ending at the most recent data point.
    """
    pv = pd.read_excel(ACLED_PV, sheet_name="Data")
    dm = pd.read_excel(ACLED_DM, sheet_name="Data")
    pv["category"] = "Political violence"
    dm["category"] = "Demonstrations"
    if "Fatalities" not in dm.columns:
        dm["Fatalities"] = 0
    cols = ["Admin2 Pcode", "Year", "Month", "Events", "Fatalities", "category"]
    df = pd.concat([pv[cols], dm[cols]], ignore_index=True)
    df["date"] = pd.to_datetime(
        df["Year"].astype(str) + "-" + df["Month"], format="%Y-%B",
    )
    cutoff = df["date"].max() - pd.DateOffset(months=WINDOW_MONTHS)
    recent = df[df["date"] >= cutoff].copy()
    period_start = str(recent["date"].min().date())
    period_end = str((recent["date"].max() + pd.offsets.MonthEnd(0)).date())
    print(f"  ACLED rows in last {WINDOW_MONTHS} months: {len(recent):,}")
    print(f"  Period: {period_start} -> {period_end}")

    out: dict = defaultdict(
        lambda: {
            "events": 0,
            "fatalities": 0,
            "breakdown": defaultdict(int),
        }
    )
    unmatched = 0
    for r in recent.itertuples():
        match = prov_to_region.get(getattr(r, "_1"))  # 'Admin2 Pcode' -> _1
        if not match:
            unmatched += int(r.Events)
            continue
        new_pcode = match[0]
        out[new_pcode]["events"] += int(r.Events)
        out[new_pcode]["fatalities"] += int(r.Fatalities)
        out[new_pcode]["breakdown"][r.category] += int(r.Events)
    if unmatched:
        print(f"  WARNING: {unmatched} events failed pcode match")
    return {
        "period_start": period_start,
        "period_end": period_end,
        "regions": {k: {**v, "breakdown": dict(v["breakdown"])} for k, v in out.items()},
    }


def schools_by_new_region(prov_to_region: dict, simplified_admin1: dict) -> tuple:
    """Spatial-join OSM schools to NEW admin1 polygons. Returns (counts, points)."""
    polys, pcodes = [], []
    for feat in simplified_admin1["features"]:
        polys.append(shape(feat["geometry"]))
        pcodes.append(feat["properties"]["pcode"])
    tree = STRtree(polys)

    schools = json.load(open(SCHOOLS_IN))["elements"]
    print(f"  OSM schools loaded: {len(schools):,}")

    counts: dict = defaultdict(int)
    points: list = []
    for el in schools:
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        if lat is None or lon is None:
            continue
        pt = Point(lon, lat)
        for idx in tree.query(pt):
            if polys[idx].contains(pt):
                counts[pcodes[idx]] += 1
                points.append([round(lat, 4), round(lon, 4)])
                break
    print(f"  Schools matched: {len(points):,}")
    return dict(counts), points


def simplify_regions() -> dict:
    g = json.load(open(ADMIN1_IN))
    print(f"  Source size: {ADMIN1_IN.stat().st_size / 1e6:.1f} MB")
    for feat in g["features"]:
        geom = shape(feat["geometry"]).simplify(
            SIMPLIFY_TOLERANCE_DEG, preserve_topology=True
        )
        feat["geometry"] = mapping(geom)
        feat["properties"] = {
            "name": feat["properties"]["adm1_name"],
            "name_old": feat["properties"]["adm1_name_old"],
            "pcode": feat["properties"]["adm1_pcode"],
        }
    return g


def displacement_events() -> dict:
    df = pd.read_csv(IDMC_IN, parse_dates=["displacement_date"])
    df = df.sort_values("displacement_date")
    events = []
    for r in df.itertuples():
        location = (r.locations_name or "").replace(", Burkina Faso", "")
        desc = (r.description or "")[:280]
        events.append({
            "lat": round(float(r.latitude), 4),
            "lon": round(float(r.longitude), 4),
            "date": str(r.displacement_date.date()),
            "figure": int(r.figure),
            "type": r.displacement_type,
            "location": location,
            "description": desc,
        })
    return {
        "period_start": str(df["displacement_date"].min().date()),
        "period_end": str(df["displacement_date"].max().date()),
        "total_displaced": int(df["figure"].sum()),
        "events": events,
    }


def main() -> None:
    print("Building province -> new region map ...")
    prov_to_region = province_to_new_region()
    print(f"  {len(prov_to_region)} province pcodes mapped")

    print("Simplifying region boundaries ...")
    regions = simplify_regions()
    REGIONS_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(REGIONS_OUT, "w") as f:
        json.dump(regions, f)
    print(f"  Wrote {REGIONS_OUT}  ({REGIONS_OUT.stat().st_size / 1e6:.2f} MB)")

    centroids = new_region_centroids()

    print("Aggregating UNFPA school-age population per new region ...")
    school_age = school_age_by_new_region(prov_to_region)
    print(f"  Total: {sum(school_age.values()):,} children across {len(school_age)} new regions")

    print("Counting OSM schools per new region (point-in-polygon) ...")
    schools, points = schools_by_new_region(prov_to_region, regions)
    with open(SCHOOLS_OUT, "w") as f:
        json.dump(points, f)
    print(f"  Wrote {SCHOOLS_OUT}  ({SCHOOLS_OUT.stat().st_size / 1024:.1f} KB)")

    print("Aggregating ACLED political violence + demonstrations per new region ...")
    acled = acled_per_new_region(prov_to_region)

    print("Extracting IDMC displacement events ...")
    disp = displacement_events()
    print(f"  {len(disp['events'])} events, {disp['total_displaced']:,} people")
    with open(DISPLACEMENT_OUT, "w") as f:
        json.dump(disp, f, indent=2)
    print(f"  Wrote {DISPLACEMENT_OUT}  ({DISPLACEMENT_OUT.stat().st_size / 1024:.1f} KB)")

    print("Building per-region records ...")
    records = []
    for pcode, (lat, lon, name) in centroids.items():
        a = acled["regions"].get(pcode, {"events": 0, "fatalities": 0, "breakdown": {}})
        records.append({
            "pcode": pcode,
            "region": name,
            "lat": round(lat, 4),
            "lon": round(lon, 4),
            "events": a["events"],
            "fatalities": a["fatalities"],
            "school_age_pop": school_age.get(pcode, 0),
            "schools_osm": schools.get(pcode, 0),
            "breakdown": a["breakdown"],
            "period_start": acled["period_start"],
            "period_end": acled["period_end"],
        })
    records.sort(key=lambda r: r["events"], reverse=True)
    out = {
        "period_start": acled["period_start"],
        "period_end": acled["period_end"],
        "regions": records,
    }
    with open(EVENTS_OUT, "w") as f:
        json.dump(out, f, indent=2)
    print(f"  Wrote {EVENTS_OUT}  ({EVENTS_OUT.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
