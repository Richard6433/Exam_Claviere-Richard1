"""
Prepare browser-ready data for the Leaflet map.

Reads:
    data/processed/acled_burkina_faso.csv     (output of 01_filter_acled.py)
    data/raw/bfa_admin1.geojson               (17 new regions, from HDX/IGB)
    data/raw/bfa_admpop_adm1_2023_5yr.csv     (UNFPA COD-PS 2023, age x sex)
    data/raw/bfa_osm_schools.json             (OSM schools, via Overpass)

Writes:
    docs/data/events_by_region.json           (~one row per region)
    docs/data/regions.geojson                 (simplified for fast browser load)
    docs/data/schools.json                    (compact [lat, lon] pairs)

The map shows the most recent 12 months of conflict activity per region.
Each region marker carries a popup with: date range, breakdown by cause
(event type), total events, total fatalities.
"""

from collections import defaultdict
from datetime import timedelta
from pathlib import Path
import json

import pandas as pd
from shapely.geometry import shape, mapping, Point
from shapely.strtree import STRtree

ACLED_CSV = Path("data/processed/acled_burkina_faso.csv")
POP_CSV = Path("data/raw/bfa_admpop_adm1_2023_5yr.csv")
SCHOOLS_IN = Path("data/raw/bfa_osm_schools.json")
REGIONS_IN = Path("data/raw/bfa_admin1.geojson")
EVENTS_OUT = Path("docs/data/events_by_region.json")
REGIONS_OUT = Path("docs/data/regions.geojson")
SCHOOLS_OUT = Path("docs/data/schools.json")

WINDOW_DAYS = 365
SIMPLIFY_TOLERANCE_DEG = 0.005


def school_age_by_region() -> dict:
    """Return {region_name_lowercase: school_age_population} for ages 5-14."""
    pop = pd.read_csv(POP_CSV)
    pop["school_age"] = pop["T_05_09"] + pop["T_10_14"]
    return {row.ADM1_FR.lower(): int(row.school_age) for row in pop.itertuples()}


def schools_data() -> tuple:
    """
    Spatial-join OSM school points to the new 17-region polygons.
    Returns (counts_per_old_region, points) where:
      - counts_per_old_region maps {old_region_lowercase: count}
      - points is a list of [lat, lon] pairs rounded to 4 decimals
    """
    with open(REGIONS_IN) as f:
        regions = json.load(f)
    polys, old_names = [], []
    for feat in regions["features"]:
        polys.append(shape(feat["geometry"]))
        old_names.append(feat["properties"]["adm1_name_old"])
    tree = STRtree(polys)

    with open(SCHOOLS_IN) as f:
        schools = json.load(f)["elements"]
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
                counts[old_names[idx].lower()] += 1
                points.append([round(lat, 4), round(lon, 4)])
                break
    print(f"  Schools matched to a region: {len(points):,}")
    return dict(counts), points


def aggregate_acled(school_age: dict, schools: dict) -> dict:
    df = pd.read_csv(ACLED_CSV, parse_dates=["WEEK"])
    cutoff = df["WEEK"].max() - timedelta(days=WINDOW_DAYS)
    recent = df[df["WEEK"] >= cutoff].copy()
    print(f"  ACLED rows in last {WINDOW_DAYS} days: {len(recent):,}")
    print(f"  Period: {recent['WEEK'].min().date()} -> {recent['WEEK'].max().date()}")

    out = []
    for region, g in recent.groupby("ADMIN1"):
        breakdown = (
            g.groupby("EVENT_TYPE")["EVENTS"].sum().sort_values(ascending=False).to_dict()
        )
        out.append(
            {
                "region": region,
                "lat": float(g["CENTROID_LATITUDE"].mean()),
                "lon": float(g["CENTROID_LONGITUDE"].mean()),
                "events": int(g["EVENTS"].sum()),
                "fatalities": int(g["FATALITIES"].sum()),
                "school_age_pop": school_age.get(region.lower()),
                "schools_osm": schools.get(region.lower(), 0),
                "breakdown": {k: int(v) for k, v in breakdown.items()},
                "period_start": str(g["WEEK"].min().date()),
                "period_end": str(g["WEEK"].max().date()),
            }
        )
    out.sort(key=lambda r: r["events"], reverse=True)
    return {
        "period_start": str(recent["WEEK"].min().date()),
        "period_end": str(recent["WEEK"].max().date()),
        "regions": out,
    }


def simplify_regions() -> dict:
    with open(REGIONS_IN) as f:
        gj = json.load(f)
    print(f"  Original size: {REGIONS_IN.stat().st_size / 1e6:.1f} MB")
    for feat in gj["features"]:
        geom = shape(feat["geometry"]).simplify(
            SIMPLIFY_TOLERANCE_DEG, preserve_topology=True
        )
        feat["geometry"] = mapping(geom)
        feat["properties"] = {
            "name": feat["properties"]["adm1_name"],
            "name_old": feat["properties"]["adm1_name_old"],
            "pcode": feat["properties"]["adm1_pcode"],
        }
    return gj


def main() -> None:
    print("Loading school-age population (UNFPA 2023) ...")
    school_age = school_age_by_region()
    total = sum(school_age.values())
    print(f"  {len(school_age)} regions, total 5-14 children: {total:,}")

    print("Counting OSM schools per region (point-in-polygon) ...")
    schools, points = schools_data()
    print(f"  Total schools assigned: {sum(schools.values()):,}")
    with open(SCHOOLS_OUT, "w") as f:
        json.dump(points, f)
    print(f"  Wrote {SCHOOLS_OUT}  ({SCHOOLS_OUT.stat().st_size / 1024:.1f} KB)")

    print("Aggregating ACLED ...")
    events = aggregate_acled(school_age, schools)
    EVENTS_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(EVENTS_OUT, "w") as f:
        json.dump(events, f, indent=2)
    print(f"  Wrote {EVENTS_OUT}  ({EVENTS_OUT.stat().st_size / 1024:.1f} KB)")

    print("Simplifying region boundaries ...")
    regions = simplify_regions()
    with open(REGIONS_OUT, "w") as f:
        json.dump(regions, f)
    print(f"  Wrote {REGIONS_OUT}  ({REGIONS_OUT.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
