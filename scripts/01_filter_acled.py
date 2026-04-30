"""
Filter an ACLED export down to Burkina Faso rows only.

Supports both:
  - The row-level CSV from acleddata.com (column 'country', lowercase)
  - The weekly aggregated Africa XLSX from the ACLED Conflict Index
    (column 'COUNTRY', uppercase)

Usage:
    1. Save the ACLED file under data/raw/, e.g.:
           data/raw/acled_export.csv                                      (CSV)
           data/raw/Africa_aggregated_data_up_to_week_of-2026-04-11.xlsx  (XLSX)
    2. Set INPUT_PATH below to point at it.
    3. From the project root, run:
           python scripts/01_filter_acled.py
    4. Output is written to:
           data/processed/acled_burkina_faso.csv
"""

from pathlib import Path

import pandas as pd

INPUT_PATH = Path("data/raw/Africa_aggregated_data_up_to_week_of-2026-04-11.xlsx")
OUTPUT_PATH = Path("data/processed/acled_burkina_faso.csv")
TARGET_COUNTRY = "Burkina Faso"


def load(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    return pd.read_csv(path)


def main() -> None:
    print(f"Reading {INPUT_PATH} ...")
    df = load(INPUT_PATH)
    print(f"  Loaded {len(df):,} rows, {len(df.columns)} columns")

    country_col = "country" if "country" in df.columns else "COUNTRY"
    print(f"Filtering on column '{country_col}' == '{TARGET_COUNTRY}' ...")
    bf = df[df[country_col] == TARGET_COUNTRY].copy()
    print(f"  Kept {len(bf):,} rows")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    bf.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
