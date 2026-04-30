"""
Filter an ACLED CSV export down to Burkina Faso rows only.

Usage:
    1. Download an ACLED CSV from https://acleddata.com (Data Export Tool)
       and save it as:  data/raw/acled_export.csv
    2. From the project root, run:
           python scripts/01_filter_acled.py
    3. The filtered file will be written to:
           data/processed/acled_burkina_faso.csv
"""

from pathlib import Path

import pandas as pd

INPUT_PATH = Path("data/raw/acled_export.csv")
OUTPUT_PATH = Path("data/processed/acled_burkina_faso.csv")
TARGET_COUNTRY = "Burkina Faso"


def main() -> None:
    print(f"Reading {INPUT_PATH} ...")
    df = pd.read_csv(INPUT_PATH)
    print(f"  Loaded {len(df):,} rows, {len(df.columns)} columns")

    print(f"Filtering to country == '{TARGET_COUNTRY}' ...")
    bf = df[df["country"] == TARGET_COUNTRY].copy()
    print(f"  Kept {len(bf):,} rows")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    bf.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
