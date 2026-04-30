"""
Prepare browser-ready data for the Leaflet map.

Reads:
    data/processed/acled_burkina_faso.csv     (output of 01_filter_acled.py)
    data/raw/bfa_admin1.geojson               (17 new regions, from HDX/IGB)

Writes:
    docs/data/events_by_region.json           (~one row per region)
    docs/data/regions.geojson                 (simplified for fast browser load)

The map shows the most recent 12 months of conflict activity per region.
Each region marker carries a popup with: date range, breakdown by cause
(event type), total events, total fatalities.
"""

from collections import defaultdict
from datetime import timedelta
from pathlib import Path
import json

import pandas as pd
from shapely.geometry import shape, mapping

ACLED_CSV = Path("data/processed/acled_burkina_faso.csv")
REGIONS_IN = Path("data/raw/bfa_admin1.geojson")
EVENTS_OUT = Path("docs/data/events_by_region.json")
REGIONS_OUT = Path("docs/data/regions.geojson")

WINDOW_DAYS = 365
SIMPLIFY_TOLERANCE_DEG = 0.005


def aggregate_acled() -> dict:
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
    print("Aggregating ACLED ...")
    events = aggregate_acled()
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
