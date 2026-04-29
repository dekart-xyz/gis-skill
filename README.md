# geosql

Claude/Codex geospatial SQL skill for data scientists and analysts working with geospatial data on BigQuery and Snowflake.

![GeoSQL demo](assets/geosqldemo.gif)

Describe what you want geographically, and skill writes and runs SQL against free map datasets (Overture Maps) in **BigQuery or Snowflake**, checks the cost, validates the answer, and (if you ask) shows you the map — without surprise bills or hand-waved results.

Example questions it handles well:

- "Show me all bike lanes in Amsterdam"
- "How many buildings are in downtown Tokyo?"
- "Map the rail network in Germany"
- "Aggregate restaurant density in NYC by H3 cell"

It works with any private GEOGRAPHY/GEOMETRY dataset too.


## Install (Claude/Codex)

### Prerequisites

* `bq` or `snow` CLI installed and authenticated with default project/connection (!) configured.

### Install SKILL


With python

```bash
pip install geosql
geosql
```

With Node.js

```bash
npx skills add dekart-xyz/geosql
```

Then type `/geosql` in your agent's prompt to use the skill.

### Enable map rendering (optional)

```bash
pip install dekart
dekart init
```

## Feature List

### 🗺️ Data discovery
- Auto-explores warehouse metadata (tables, columns, types) instead of guessing.
- Works with **BigQuery** (`bigquery-public-data.overture_maps`) and **Snowflake** (`OVERTURE_MAPS__*` marketplace shares).

### 💸 Cost safety
- **Always dry-runs** BigQuery queries first to estimate bytes scanned.
- Enforces a **10 GiB billing cap** by default (`--maximum_bytes_billed`).
- Refuses to execute over-budget queries — rewrites them cheaper instead (tighter bbox, lower H3 resolution, more filters).
- Uses the **bbox overlap pattern** (not containment) for fast partition pruning, then `ST_INTERSECTS` for geographic correctness.

### ✅ Mandatory validation
Before showing you a final query, it:
1. Dry-runs for cost.
2. Runs `COUNT(*)` to confirm rows exist and are reasonable.
3. Computes **total area** (polygons) or **total length** (lines) as a sanity check.
4. Cross-checks numbers against domain knowledge — debugs if something looks off.

### 🔷 H3 spatial aggregation
- Built-in support for hexagonal grid rollups (heatmaps, density).
- Region-aware namespaces (`jslibs.h3.*` for US, `jslibs.eu_h3.*` for EU).
- Cost rules: filter first, aggregate before adding heavy boundary geometry.

### 🗺️ Map rendering
- Uses the `dekart` CLI to turn results into an **interactive map**.
- Workflow: create report → dataset → upload CSV → snapshot → inspect.
- Only triggers when you explicitly say "map" — never auto-renders.
- Smart styling rules: picks layer type by question (Points for positions, H3 for density, Arcs for origin-destination, etc.), uses appropriate palettes, locks zoom to the insight.
