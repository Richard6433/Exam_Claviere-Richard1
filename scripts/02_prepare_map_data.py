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
import re
import unicodedata

import pandas as pd
from shapely.geometry import shape, mapping, Point
from shapely.strtree import STRtree

ATTRIBUTION_RE = re.compile(r"According to ([^,.;]+)", re.IGNORECASE)


def normalize(s) -> str:
    """Lowercase + strip accents for fuzzy name matching."""
    if not s or not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()

POP_XLSX = Path("data/raw/bfa_admpop_2023_5yr.xlsx")
ACLED_PV = Path("data/raw/bfa_acled_monthly_political_violence.xlsx")
ACLED_DM = Path("data/raw/bfa_acled_monthly_demonstrations.xlsx")
ACLED_WEEKLY = Path("data/raw/Africa_aggregated_data_up_to_week_of-2026-04-11.xlsx")
SCHOOLS_IN = Path("data/raw/bfa_osm_schools.json")
IDMC_IN = Path("data/raw/bfa_idmc_events.csv")
GCORR_IN = Path("data/raw/bfa_pdi_gcorr_may2025.xlsx")
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


def strategic_developments_by_new_region(school_age: dict) -> dict:
    """
    Strategic developments aren't in the per-province ACLED files. Read
    them from the weekly Africa file (which carries all 6 EVENT_TYPEs at
    OLD admin1 only) and allocate to NEW regions by school-age population
    share within each parent old region.

    Returns {adm1_pcode_new: estimated_strategic_developments_count}.
    """
    if not ACLED_WEEKLY.exists():
        return {}
    df = pd.read_excel(ACLED_WEEKLY)
    df = df[(df["COUNTRY"] == "Burkina Faso")
            & (df["EVENT_TYPE"] == "Strategic developments")].copy()
    df["WEEK"] = pd.to_datetime(df["WEEK"])
    cutoff = df["WEEK"].max() - pd.DateOffset(months=WINDOW_MONTHS)
    df = df[df["WEEK"] >= cutoff]
    sd_by_old = df.groupby(df["ADMIN1"].str.lower())["EVENTS"].sum().to_dict()
    print(f"  Strategic developments total (last {WINDOW_MONTHS}m): {df['EVENTS'].sum()}")

    # Build pop-share map: each new region's share within its parent old region
    g = json.load(open(ADMIN1_IN))
    new_to_old = {f["properties"]["adm1_pcode"]: f["properties"]["adm1_name_old"].lower()
                  for f in g["features"]}
    pop_by_old: dict = defaultdict(int)
    for new_pcode, old_name in new_to_old.items():
        pop_by_old[old_name] += school_age.get(new_pcode, 0)

    out: dict = {}
    for new_pcode, old_name in new_to_old.items():
        share = (school_age.get(new_pcode, 0) / pop_by_old[old_name]) if pop_by_old[old_name] else 0
        out[new_pcode] = round(sd_by_old.get(old_name, 0) * share)
    return out


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
    df = pd.read_csv(
        IDMC_IN,
        parse_dates=[
            "displacement_date",
            "displacement_start_date",
            "displacement_end_date",
        ],
    )
    before = len(df)
    df = df.drop_duplicates(subset=["event_id"], keep="first")
    if before != len(df):
        print(f"  Dropped {before - len(df)} duplicate IDMC rows (same event_id)")
    df = df.sort_values("displacement_date")
    events = []
    for r in df.itertuples():
        location = (r.locations_name or "").replace(", Burkina Faso", "")
        desc = r.description or ""
        m = ATTRIBUTION_RE.search(desc)
        attribution = m.group(1).strip() if m else None
        events.append({
            "lat": round(float(r.latitude), 4),
            "lon": round(float(r.longitude), 4),
            "date": str(r.displacement_date.date()),
            "start_date": str(r.displacement_start_date.date()),
            "end_date": str(r.displacement_end_date.date()),
            "figure": int(r.figure),
            "location": location,
            "attribution": attribution,
        })
    return {
        "period_start": str(df["displacement_date"].min().date()),
        "period_end": str(df["displacement_date"].max().date()),
        "total_displaced": int(df["figure"].sum()),
        "events": events,
    }


def gcorr_idps_by_origin_region() -> dict:
    """
    Aggregate official CONASUR/GCORR IDP figures per NEW admin1.

    The dataset records, per displacement incident, the place of origin
    (Region_Province_Commune) and the number of people displaced. We
    take the province name from the origin string, look up its NEW
    admin1 via the COD admin2 file, and sum.

    Returns ({pcode_new: people_displaced}, period_start, period_end).
    """
    df = pd.read_excel(GCORR_IN, sheet_name="Incident Data")
    origin_col = next(c for c in df.columns if "origine" in c.lower())
    df = df.rename(columns={"PDI Personne": "PDI_Personne", "Date Choc": "Date_Choc"})
    df["province"] = df[origin_col].str.split("_").str[1].apply(normalize)
    df["Date_Choc"] = pd.to_datetime(df["Date_Choc"])

    # province name (normalized) -> NEW admin1 pcode, considering both
    # current and pre-2025 province names from the COD admin2 file.
    g = json.load(open(ADMIN2_IN))
    prov_to_new_admin1: dict = {}
    for feat in g["features"]:
        p = feat["properties"]
        new_pcode = p["adm1_pcode"]
        for key in (p.get("adm2_name"), p.get("adm2_name_old"), p.get("adm2_ref_name")):
            if key:
                prov_to_new_admin1[normalize(key)] = new_pcode

    out: dict = defaultdict(int)
    unmatched = 0
    for r in df.itertuples():
        new_pcode = prov_to_new_admin1.get(r.province)
        people = int(r.PDI_Personne or 0)
        if new_pcode:
            out[new_pcode] += people
        else:
            unmatched += people
    if unmatched:
        print(f"  GCORR: {unmatched} IDPs from provinces with no admin1 match")

    return (
        dict(out),
        str(df["Date_Choc"].min().date()),
        str(df["Date_Choc"].max().date()),
    )


def displaced_by_new_region(disp: dict, regions_gj: dict) -> dict:
    """Sum people displaced per new admin1 by point-in-polygon over event coordinates."""
    polys, pcodes = [], []
    for feat in regions_gj["features"]:
        polys.append(shape(feat["geometry"]))
        pcodes.append(feat["properties"]["pcode"])
    tree = STRtree(polys)

    out: dict = defaultdict(int)
    for e in disp["events"]:
        pt = Point(e["lon"], e["lat"])
        for idx in tree.query(pt):
            if polys[idx].contains(pt):
                out[pcodes[idx]] += e["figure"]
                break
    return dict(out)


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

    print("Allocating Strategic developments by school-age population share ...")
    sd_by_new = strategic_developments_by_new_region(school_age)
    for pcode, sd in sd_by_new.items():
        bucket = acled["regions"].setdefault(
            pcode, {"events": 0, "fatalities": 0, "breakdown": {}}
        )
        bucket["events"] += sd
        bucket["breakdown"]["Strategic developments"] = sd

    print("Extracting IDMC displacement events ...")
    disp = displacement_events()
    print(f"  {len(disp['events'])} events, {disp['total_displaced']:,} people")
    with open(DISPLACEMENT_OUT, "w") as f:
        json.dump(disp, f, indent=2)
    print(f"  Wrote {DISPLACEMENT_OUT}  ({DISPLACEMENT_OUT.stat().st_size / 1024:.1f} KB)")

    print("Aggregating displacement per new region (point-in-polygon, IDMC) ...")
    displaced_per_region = displaced_by_new_region(disp, regions)
    print(f"  Regions with recorded IDMC events: {len(displaced_per_region)}")

    print("Aggregating CONASUR/GCORR IDPs by origin -> new region ...")
    gcorr_idps, gcorr_start, gcorr_end = gcorr_idps_by_origin_region()
    print(f"  GCORR period: {gcorr_start} -> {gcorr_end}; total: {sum(gcorr_idps.values()):,}")

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
            "displaced_recent": displaced_per_region.get(pcode, 0),
            "idps_origin_gcorr": gcorr_idps.get(pcode, 0),
            "breakdown": a["breakdown"],
            "period_start": acled["period_start"],
            "period_end": acled["period_end"],
        })
    records.sort(key=lambda r: r["events"], reverse=True)
    out = {
        "gcorr_period_start": gcorr_start,
        "gcorr_period_end": gcorr_end,
        "period_start": acled["period_start"],
        "period_end": acled["period_end"],
        "regions": records,
    }
    with open(EVENTS_OUT, "w") as f:
        json.dump(out, f, indent=2)
    print(f"  Wrote {EVENTS_OUT}  ({EVENTS_OUT.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
