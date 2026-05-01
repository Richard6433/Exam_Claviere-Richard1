# Burkina Faso — conflict pressure on school-age population

A data-driven proposal artifact for the **Education Bridge Initiative**
RFP. Demonstrates how open data can support EBI's planning and
prioritisation in conflict-affected education programming.

## Live map

🌐 **<https://richard6433.github.io/Exam_Claviere-Richard1/docs/>**

A choropleth of Burkina Faso's 17 regions, ranked by ACLED conflict
events per 100,000 school-age children over the last 12 months. Recent
IDMC displacement events sit on top as black triangles; OSM-mapped
schools as dark dots. Click any region for the four-stat snapshot
(events / children / rate / schools / IDPs).

## Repository layout

```
.
├── README.md                  ← you are here
├── SOURCES.md                 ← every data source, with provenance
├── data/
│   ├── raw/                   ← third-party inputs, organised by source
│   │   ├── acled/             ← ACLED conflict-event exports
│   │   ├── cod/               ← OCHA/IGB admin boundaries
│   │   ├── idmc/              ← IDMC displacement events
│   │   ├── osm/               ← OpenStreetMap schools
│   │   └── unfpa/             ← UNFPA subnational population
│   └── processed/             ← outputs of the pipeline (committed)
│       ├── bf-acled-events.csv
│       └── dataset-manifest.csv
├── docs/                      ← published map (GitHub Pages from main /docs)
│   ├── index.html
│   ├── style.css
│   ├── map.js
│   └── data/                  ← browser-loaded JSON
└── scripts/
    ├── 01_filter_acled.py     ← filter ACLED weekly export → BF rows only
    ├── 02_prepare_map_data.py ← join ACLED + UNFPA + OSM + IDMC → map JSON
    └── 03_make_manifest.py    ← regenerate dataset-manifest.csv
```

## Reproducing the pipeline

```bash
# 1. Install the few dependencies
pip install pandas openpyxl shapely

# 2. Drop the raw files into the right subdirectories of data/raw/
#    (see SOURCES.md for download links)

# 3. Run the pipeline from the project root
python scripts/01_filter_acled.py
python scripts/02_prepare_map_data.py
python scripts/03_make_manifest.py

# 4. Open docs/index.html in a browser, or serve docs/ via any static server
python -m http.server --directory docs 8000
# then visit http://localhost:8000/
```

## Where to look first

- **For the headline finding**, open the live map.
- **For the proposal's argument**, read the PDF proposal.
- **For data quality questions**, see [`SOURCES.md`](SOURCES.md) and
  [`data/processed/dataset-manifest.csv`](data/processed/dataset-manifest.csv).
