# Strategy — Education Bridge Initiative RFP

This document records the intellectual structure of the proposal: the
case study chosen, the angle taken, how the visual artifact answers
the RFP, and the data-granularity decisions that underpin the work.

---

## 1. Summary

The proposed project equips EBI with a **lightweight monthly watchlist
method** — an open-data routine that surfaces, in any country of
operation, the small set of regions where conflict pressure,
displacement, and school-age population converge enough to warrant a
structured conversation with field teams.

The Burkina Faso map demonstrates the method on one country. The
method, not the map, is the deliverable.

---

## 2. Case study — Burkina Faso (posture: acute / emergency)

Burkina Faso was chosen because:

- Education disruption is the dominant humanitarian story (~6,000
  schools closed at peak; >1 million children out of school).
- Open-data depth is high: ACLED, UNFPA, IDMC, OSM, OCHA / IGB all
  publish granular country data.
- The 2025 administrative reorganization (13 → 17 regions) is recent
  enough that the spatial-accuracy question is non-trivial — a good
  test of whether the method is robust to changing boundaries.
- Recent (2024–2026) dynamics are visible and dramatic in the data.

The artifact takes **posture #1: acute / emergency programming**.
The argument is *"these are the regions where children have been
newly displaced into a deteriorating security environment"* —
distinct from posture #2 (sustained pressure / continuity
programming).

---

## 3. The angle

Three positions, in priority order:

### a. Reframe what the RFP is asking for

The RFP asks for "data, geospatial, and AI tools." EBI's own diagnosis
in the same RFP describes a **method gap**, not a tooling gap:

> *"information reaches headquarters unevenly… the broader picture is
> difficult to assemble quickly."*

A dashboard built before EBI has a shared way to triage attention
becomes another input nobody acts on. So the proposal's spine is:

> **Before tools, a method. The tool demonstrates the method, it
> doesn't replace it.**

### b. Complement, don't replace, field expertise

The map produces a list of *places to ask about*, not a ranking of
*places to invest in*. The data names the conversation; field teams
resolve it. This is consistent with EBI's stated interest that
"approaches… complement rather than replace the knowledge of field
teams."

### c. Be honest about what open data cannot say

A real strength of the proposal: the artifact exposes its own
limits. Examples baked into the visual:

- OSM under-maps the very regions that matter most. Visually, the
  Sahel is sparsest in blue dots and densest in red circles — the
  open-data picture is *thinnest* exactly where need is *highest*.
  This is itself the argument that field-team knowledge is
  irreplaceable.
- Strategic developments are only published at old-admin1 level, so
  for the 3 split regions we explicitly *estimate* their share. The
  method doesn't pretend otherwise.

---

## 4. How the artifact answers the RFP

| RFP element | How the proposal addresses it |
|---|---|
| **Objective**: strengthen planning and prioritisation | We don't sell a tool — we sell a *method* that strengthens prioritisation by giving HQ a structured prep-step before field-team conversations. |
| **Needs assessment** | The watchlist routine *is* a needs-assessment routine, run monthly, fed by open data on conflict, displacement, schools, and population. |
| **Approach and methodology** | Documented, repeatable workflow with named data sources and explicit join logic. The artifact proves the method works on one country. |
| **Use of AI** | Four scoped tasks, each with safeguards: event extraction from cluster reports, place-name disambiguation, French → English summarisation, conflict-event clustering. AI is *excluded* from prioritisation decisions. |
| **Adaptability** | Modular pipeline. New country = swap admin boundaries (COD), ACLED country slice, UNFPA country population. Method survives changing dynamics because the window is rolling. |

---

## 5. Data granularity audit

Every data source feeds the same NEW 17-region structure, but each
arrives at a different native granularity. The pipeline takes care
to operate at the **finest available level** and aggregate up
through stable identifiers — no information is smeared across the
13 → 17 split unless explicitly noted.

| Source | Native granularity | Used granularity | Aggregation path | Why |
|---|---|---|---|---|
| OCHA COD admin boundaries | New 17 regions, 47 provinces (admin0–3) | New 17 regions for polygons | Direct | The spatial skeleton; carries `adm1_name_old` + `adm2_pcode_old` for legacy joins |
| ACLED political violence + demonstrations | OLD 45 provinces × month | New 17 regions | `Admin2 Pcode` → COD `adm2_pcode_old` → COD `adm1_pcode` (new) | Provinces are stable across the reorganization; aggregating up is mathematically clean |
| ACLED Strategic developments | OLD 13 admin1 × week | New 17 regions (estimated) | Allocate parent old-admin1 totals to new constituents by school-age population share | Not published at province level. For 10 old regions that map 1:1 to new, share = 100% (exact). For 3 split old regions (Sahel, Est, Boucle du Mouhoun), the share is estimated. |
| UNFPA population (5–14) | OLD 45 provinces × age band × sex | New 17 regions | Same `adm2_pcode` join as ACLED | Ensures the events / population rate uses the same denominator path as the numerator |
| OSM schools | Point coordinates | New 17 regions (count) and individual points | Point-in-polygon against new admin1 polygons | Leverages exact lat/lon — no aggregation loss |
| IDMC displacement events | Event-level (lat/lon, date, figure) | Event-level | None — rendered at exact coordinates | The strongest possible granularity; events keep their identity |

### Why this matters for the proposal

The granularity choices are deliberate, and the rationale is itself
part of the proposal's defensible methodology:

1. **Same denominator path as numerator**: events per 100,000
   children compares apples to apples — both are aggregated from
   province → new region through identical pcode joins.
2. **Reorganization-robust**: the 13 → 17 region change is fully
   respected for 95%+ of the data. Goulmou, Sirba, Tapoa, Liptako,
   Soum, Bankui, Sourou all carry numbers that are theirs alone, not
   inherited from their parent old region.
3. **Honest where it has to be**: the one estimated quantity
   (Strategic developments for split regions) is documented above
   and represents ~18% of total events; the allocation method is
   transparent and defensible.

---

## 6. Known limitations

- **OSM coverage is uneven**: ~5,594 schools mapped vs the Ministry of
  Education's estimated total of ~16,000. Coverage is sparsest in
  the most conflict-affected regions. The map labels OSM explicitly;
  the limitation is itself part of the argument.
- **Strategic developments allocation is estimated for 3 split
  regions**: Sahel → Liptako + Soum, Est → Goulmou + Sirba + Tapoa,
  Boucle du Mouhoun → Bankui + Sourou. Allocation is by school-age
  population share within the parent old region.
- **DTM displacement** is not on the map. Only IDMC's event-level
  data was used, since DTM's HDX mirror is a stub (rounds 1–2 only,
  2018–2019). Granular DTM lives behind registration and was out of
  scope for the v1 demonstration.
- **No school-closure data**: The Burkinabè *Cellule Education en
  Situation d'Urgence (CES)* publishes school-closure counts, but
  primarily in PDFs. Extracting them is a phase-2 candidate and a
  natural place to demonstrate scoped AI use (LLM extraction with
  human verification).

---

## 7. What's next

The current artifact establishes the v1 method on Burkina Faso.
Plausible next moves, in order:

1. **Choropleth coloring** of regions by events-per-100k-children so
   the headline answer is visible at country zoom.
2. **Top-hotspots panel** — surfaces the proposal-relevant insight
   without requiring clicks.
3. **CES PDF extraction** — adds school-closure data and demonstrates
   AI use with safeguards.
4. **Second-country test** — re-run the pipeline on a different
   country (Mali or northern Nigeria) to prove adaptability.
