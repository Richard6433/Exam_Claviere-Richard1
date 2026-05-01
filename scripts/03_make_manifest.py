"""
Generate data/processed/dataset_manifest.csv listing every dataset
used by the map, with format, source URL, record count, and quality
caveats — so the data layer is auditable in one place.
"""

from pathlib import Path
import csv
import json

import pandas as pd


MANIFEST_OUT = Path("data/processed/dataset_manifest.csv")


ROWS = [
    {
        "id": 1,
        "dataset": "Burkina Faso administrative boundaries (region level)",
        "publisher": "Institut Geographique Burkina (IGB) via OCHA Field Information Services",
        "source_url": "https://data.humdata.org/dataset/cod-ab-bfa",
        "format": "GeoJSON",
        "local_file": "data/raw/bfa_admin1.geojson",
        "as_of": "2026-04-02",
        "records_count_fn": lambda: len(json.load(open("data/raw/bfa_admin1.geojson"))["features"]),
        "granularity": "Polygons, admin level 1 (regions)",
        "role_in_map": "Light-grey backdrop polygons; the spatial skeleton",
        "quality_notes": "Reflects the 17-region 2025 reorganization; carries adm1_name_old + adm1_pcode_old fields for joins to legacy datasets",
    },
    {
        "id": 2,
        "dataset": "ACLED conflict events (Burkina Faso slice)",
        "publisher": "Armed Conflict Location & Event Data Project (ACLED)",
        "source_url": "https://acleddata.com",
        "format": "CSV (filtered from XLSX upload)",
        "local_file": "data/processed/acled_burkina_faso.csv",
        "as_of": "2026-04-11",
        "records_count_fn": lambda: len(pd.read_csv("data/processed/acled_burkina_faso.csv")),
        "granularity": "Per region x week x event type, with region centroid lat/lon",
        "role_in_map": "Red circles per region (size = events in last 12 months); cause breakdown in popup",
        "quality_notes": "Uses OLD 13-region naming in ADMIN1 column; centroid coordinates are admin1 centroids, not exact event coordinates",
    },
    {
        "id": 3,
        "dataset": "Burkina Faso subnational population statistics (5-year age bands)",
        "publisher": "UNFPA / Institut National de la Statistique et de la Démographie (INSD)",
        "source_url": "https://data.humdata.org/dataset/cod-ps-bfa",
        "format": "CSV",
        "local_file": "data/raw/bfa_admpop_adm1_2023_5yr.csv",
        "as_of": "2025-01-10 (reference year 2023)",
        "records_count_fn": lambda: len(pd.read_csv("data/raw/bfa_admpop_adm1_2023_5yr.csv")),
        "granularity": "Per region x 5-year age band x sex (totals also provided)",
        "role_in_map": "School-age (5-14) population per region in popup, used for events-per-100k-children rate",
        "quality_notes": "Uses OLD 13-region structure; 'school-age' computed as T_05_09 + T_10_14",
    },
    {
        "id": 4,
        "dataset": "OpenStreetMap schools in Burkina Faso (amenity=school)",
        "publisher": "OpenStreetMap contributors (queried via Overpass API)",
        "source_url": "https://overpass-api.de/api/interpreter",
        "format": "Overpass JSON",
        "local_file": "data/raw/bfa_osm_schools.json",
        "as_of": "2026-04-30 (live query)",
        "records_count_fn": lambda: len(json.load(open("data/raw/bfa_osm_schools.json"))["elements"]),
        "granularity": "Point per school (named or unnamed)",
        "role_in_map": "Blue dots on map; school count per region in popup",
        "quality_notes": "Crowd-sourced and incomplete; coverage is uneven by region (e.g., Sahel under-mapped vs Centre-Ouest); estimated ~35% of the Ministry of Education total",
    },
    {
        "id": 5,
        "dataset": "IDMC Internal Displacements Updates (event-level)",
        "publisher": "Internal Displacement Monitoring Centre (IDMC)",
        "source_url": "https://data.humdata.org/dataset/idmc-event-data-for-bfa",
        "format": "CSV",
        "local_file": "data/raw/bfa_idmc_events.csv",
        "as_of": "2026-04-30 (events 2025-11-03 to 2026-03-15)",
        "records_count_fn": lambda: len(pd.read_csv("data/raw/bfa_idmc_events.csv")),
        "granularity": "One row per displacement event with lat/lon, date, figure, narrative",
        "role_in_map": "Black triangles (size = people displaced); date range, location in popup",
        "quality_notes": "Two duplicate rows in the raw file (same event_id) are deduped in prep. Only events crossing IDMC's reporting threshold are included — under-counts smaller and chronic-blockade incidents",
    },
    {
        "id": 6,
        "dataset": "Burkina Faso CONASUR/GCORR IDP register",
        "publisher": "Conseil National de Secours d'Urgence et de Réhabilitation (CONASUR), via Groupe de Coordination Opérationnelle de la Réponse Rapide (GCORR), hosted by OCHA Burkina Faso",
        "source_url": "https://data.humdata.org/dataset/situation-des-personnes-deplacees-internes",
        "format": "XLSX",
        "local_file": "data/raw/bfa_pdi_gcorr_may2025.xlsx",
        "as_of": "2025-05-08 (incidents Jan 2024 - Apr 2025)",
        "records_count_fn": lambda: len(pd.read_excel("data/raw/bfa_pdi_gcorr_may2025.xlsx", sheet_name="Incident Data")),
        "granularity": "One row per displacement incident with origin Region/Province/Commune, destination Region/Commune, household + persons (M/F/Boys/Girls)",
        "role_in_map": "Per-region 'IDPs originated from this region' figure shown in the region popup (more comprehensive than IDMC IDU)",
        "quality_notes": "Authoritative Burkinabè source for IDP figures; covers Jan 2024 - Apr 2025. Province names normalised + accent-stripped + matched to current and pre-2025 names from the COD admin2 file (99.8% coverage)",
    },
]


def main() -> None:
    MANIFEST_OUT.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "id", "dataset", "publisher", "source_url", "format",
        "local_file", "as_of", "records", "granularity",
        "role_in_map", "quality_notes",
    ]
    with open(MANIFEST_OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        for row in ROWS:
            count = row["records_count_fn"]()
            w.writerow({
                "id": row["id"],
                "dataset": row["dataset"],
                "publisher": row["publisher"],
                "source_url": row["source_url"],
                "format": row["format"],
                "local_file": row["local_file"],
                "as_of": row["as_of"],
                "records": count,
                "granularity": row["granularity"],
                "role_in_map": row["role_in_map"],
                "quality_notes": row["quality_notes"],
            })
            print(f"  #{row['id']} {row['dataset'][:60]:<60}  {count:>6} records")
    print(f"\nWrote {MANIFEST_OUT}")


if __name__ == "__main__":
    main()
