---
name: giskill
description: Build cost-safe GIS SQL for BigQuery or Snowflake. Render results on an interactive map only when the user explicitly asks for a map.
---

# GIS Skill (Claude)

## Tools/CLI

This skill uses the following CLIs:
- `bq` for BigQuery SQL execution and cost control.
- `snow` for Snowflake SQL execution (`snow sql`).
- `dekart` for rendering maps. Used ONLY when the user explicitly asks for a map. Never run map flow for SQL-only questions.

Before using CLIs, verify availability if it was not done before:

```bash
for c in bq snow dekart; do command -v $c >/dev/null && echo $c=ok || echo $c=missing; done
```

## Required Workflow

Follow these steps in order. Do NOT write a final query until steps 1-3 are complete.

### Step 1: Discover schema

Discover available data objects before writing any query: start with database/share availability (where applicable), then confirm schemas, tables, and columns.
Always verify exact object names and column types from the warehouse metadata; do not assume from general knowledge.

When multiple tables match the entity, sample each candidate for attribute density and prefer the richer source. Richer attributes enable stronger visual encoding in Step 5 and a stronger map validation case.

BigQuery:

```sql
SELECT table_name
FROM `bigquery-public-data.overture_maps.INFORMATION_SCHEMA.TABLES`
ORDER BY table_name;
```

```sql
SELECT column_name, data_type
FROM `bigquery-public-data.overture_maps.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name = '<target_table>'
ORDER BY ordinal_position;
```

Snowflake:

```sql
SHOW DATABASES LIKE 'OVERTURE_MAPS__%';
```

If this returns no rows, stop and ask the user to install Overture Maps shares from Snowflake Marketplace before continuing.

```sql
SELECT table_catalog, table_schema, table_name
FROM OVERTURE_MAPS__TRANSPORTATION.INFORMATION_SCHEMA.TABLES
WHERE table_schema = 'CARTO'
ORDER BY table_name;
```

```sql
SELECT column_name, data_type
FROM OVERTURE_MAPS__TRANSPORTATION.INFORMATION_SCHEMA.COLUMNS
WHERE table_schema = 'CARTO'
  AND table_name = '<TARGET_TABLE>'
ORDER BY ordinal_position;
```

### Step 2: Resolve the target area

When the user asks about a named area (city, district, country), query `division_area` first to discover how it is actually stored (subtype, class, naming conventions). Do not assume from general knowledge.

BigQuery:

```sql
SELECT subtype, class, names.primary, bbox.xmin, bbox.xmax, bbox.ymin, bbox.ymax
FROM `bigquery-public-data.overture_maps.division_area`
WHERE country = '<iso2>'
  AND LOWER(names.primary) LIKE '%<area_name>%'
LIMIT 20;
```

Snowflake:

```sql
SELECT subtype,
       class,
       names:primary::string AS name_primary,
       bbox:xmin::float AS xmin,
       bbox:xmax::float AS xmax,
       bbox:ymin::float AS ymin,
       bbox:ymax::float AS ymax
FROM OVERTURE_MAPS__DIVISIONS.CARTO.DIVISION_AREA
WHERE country = '<ISO2>'
  AND LOWER(names:primary::string) LIKE '%<area_name>%'
LIMIT 20;
```

Extract the exact bbox constants from the result. Use the full precision values returned by the query, do not round or truncate them.

### Step 3: Draft the query

- Use hardcoded bbox from step 2 as a scan gate (fast partition pruning).
- Add `ST_INTERSECTS` against the real geometry from `division_area` for geographic correctness. bbox alone is rectangular and overshoots.
- Both are required for named-area queries. Never omit `ST_INTERSECTS`.
- Select only required columns; avoid `SELECT *`.
- Add `LIMIT` for exploration.

**CRITICAL: bbox overlap filter direction.** The scan gate must use the OVERLAP pattern, not containment. The feature's bbox must overlap the target area:

```
-- CORRECT (overlap): feature extends into our area
AND bbox.xmax >= <area_xmin>   -- feature's right edge is east of area's left
AND bbox.xmin <= <area_xmax>   -- feature's left edge is west of area's right
AND bbox.ymax >= <area_ymin>   -- feature's top edge is above area's bottom
AND bbox.ymin <= <area_ymax>   -- feature's bottom edge is below area's top

-- WRONG (containment): do NOT use this
AND bbox.xmin >= <area_xmin>   -- WRONG
AND bbox.xmax <= <area_xmax>   -- WRONG
```

BigQuery:

```sql
WITH area AS (
  SELECT geometry
  FROM `bigquery-public-data.overture_maps.division_area`
  WHERE country = 'DE'
    AND region = 'DE-BE'
    AND subtype = 'region'
    AND class = 'land'
  LIMIT 1
)
SELECT s.id, s.geometry
FROM `bigquery-public-data.overture_maps.segment` s
CROSS JOIN area a
WHERE s.subtype = 'rail'
  -- overlap pattern: xmax >= area_xmin, xmin <= area_xmax
  AND s.bbox.xmax >= 13.08834457397461
  AND s.bbox.xmin <= 13.761162757873535
  AND s.bbox.ymax >= 52.33823776245117
  AND s.bbox.ymin <= 52.67551040649414
  AND ST_INTERSECTS(s.geometry, a.geometry)
LIMIT 1000;
```

Snowflake:

```sql
WITH area AS (
  SELECT geometry
  FROM OVERTURE_MAPS__DIVISIONS.CARTO.DIVISION_AREA
  WHERE country = 'DE'
    AND region = 'DE-BE'
    AND subtype = 'region'
    AND class = 'land'
  LIMIT 1
)
SELECT s.id, s.geometry
FROM OVERTURE_MAPS__TRANSPORTATION.CARTO.SEGMENT s
CROSS JOIN area a
WHERE s.subtype = 'rail'
  AND s.bbox:xmax::float >= 13.08834457397461
  AND s.bbox:xmin::float <= 13.761162757873535
  AND s.bbox:ymax::float >= 52.33823776245117
  AND s.bbox:ymin::float <= 52.67551040649414
  AND ST_INTERSECTS(s.geometry, a.geometry)
LIMIT 1000;
```

### Step 4: Validate (mandatory)

Do NOT present the query to the user without validating it first.

1. Dry run (BigQuery only) `bq query --use_legacy_sql=false --dry_run --format=json '<SQL>'` to check estimated bytes.
   * If dry run fails: read the bq error output. Common causes: string vs int type mismatch, missing backtick escaping, reserved keyword collision.
   * If estimated bytes exceed budget: do NOT execute. Instead, rewrite the query to be cheaper (tighter bbox, more filters, lower H3 resolution, etc) and validate again.
2. Validate row count: execute `COUNT(*)` (or equivalent) to confirm count is reasonable. If count is zero, debug before presenting.
3. Validate geometry magnitude when possible:
   - If output includes polygonal `GEOGRAPHY`, compute total area (for example `SUM(ST_AREA(geometry))`) and return units in square meters (and optionally km²).
   - If output includes line `GEOGRAPHY`, compute total length (for example `SUM(ST_LENGTH(geometry))`) and return units in meters (and optionally km).
   - If geometry is point-only or no geometry is selected, explicitly state area/length validation is not applicable.
4. Sanity-check whether row count and area/length are reasonable for the place and feature type (use domain knowledge). If numbers look implausible, debug before presenting.
5. If validation fails debug before presenting. Check bbox direction, value truncation, filter logic, and column types.


Iterate. Fix issues in small steps. Do not run broad or full extraction queries unless explicitly requested. All validation must be done in SQL.


### Step 5: Map Data

Maps catch what rows cannot: misplaced points, duplicates, coverage gaps.

If user did not ask for map, answer first (SQL + results + cost), then propose map validation as a separate "Next step" section with 2-3 sentences on what to look for and which failure modes rows cannot catch.

Do not start map workflow without user request.

Do not claim visual insights until the styled snapshot is rendered and inspected; never dress row-derived facts as map observations.

If dekart CLI is missing, ask the user to `pip install dekart-cli && dekart init` and wait until the user confirms with `ready`, `done`, or `ok`. If unauthed, ask to run `dekart init`.


## Running Queries with `bq` CLI

Use `bq` CLI directly. Always use standard SQL and enforce a budget:

```bash
# Dry run (check cost before executing)
bq query --use_legacy_sql=false --dry_run --format=json --maximum_bytes_billed=10737418240 'SELECT ...'

# Execute
bq query --use_legacy_sql=false --format=json --maximum_bytes_billed=10737418240 --max_rows=50 'SELECT ...'
```

Guardrails:
1. Always dry run before execution.
2. Always include `--maximum_bytes_billed` (default 10 GiB = `10737418240`).
3. If estimated bytes exceed budget: do not execute, provide a cheaper SQL variant.
4. Prefer bounded SQL (bbox + date/limit + minimal columns).

## Running Queries with `snow` CLI

Use `snow sql` directly for Snowflake data and keep queries bounded.

```bash
# First verify Overture shares are installed
snow sql --query "SHOW DATABASES LIKE 'OVERTURE_MAPS__%';"

# Validate quickly with row count first
snow sql --query "WITH area AS (...) SELECT COUNT(*) FROM ...;"

# Execute preview rows (table output)
snow sql --query "WITH area AS (...) SELECT ... LIMIT 50;"

# CSV output for piping (clean stdout)
snow sql --format CSV --silent --query "WITH area AS (...) SELECT ... LIMIT 50000;"
```

Guardrails:
1. Always validate with tight filters and `COUNT(*)` first.
2. Always keep extraction bounded (`bbox` + `ST_INTERSECTS` + `LIMIT`) unless the user explicitly asks for full export.
3. For map export, use CSV mode with `--format CSV --silent`.
4. Ensure a default Snow CLI connection is configured before running commands.
5. If `SHOW DATABASES LIKE 'OVERTURE_MAPS__%'` returns no rows, ask the user to install Overture Maps from Snowflake Marketplace, then retry.

## Map Flow with `dekart` CLI

Use this to execute the map validation step from SQL query output. Use only if dekart CLI is available.

### Artifact model

The CLI stores map artifacts in this hierarchy:
- `report`: top-level map container.
- `dataset`: one data layer slot inside a report.
- `file`: uploaded data artifact attached to a dataset.

Control plane: create `report` -> create `dataset` -> create `file`. The CLI provides an upload wrapper that performs multipart upload and completion.

### Workflow rules

1. Use CLI help for current command behavior: `dekart --help`, `dekart tools --help`, `dekart call --help`, `dekart upload-file --help`.
2. Gate: enter this flow ONLY after the analytical answer is delivered AND the user confirms the map step with `ready`, `done`, or `ok`. If user declines or is silent, stop; do not export CSV, do not create reports.
3. Once gated-in, export result rows to CSV with explicit row controls. `--max_rows` is mandatory because BigQuery CLI defaults to 100 rows when omitted.
   - CSV export must keep stderr separate from CSV bytes.
   - Never use `2>&1` when output is redirected to `.csv`.
   - BigQuery:
     `bq query ... --format=csv --max_rows=50000 'SELECT ...' | dekart upload-file --stdin --file-id <file_id> --name result.csv --mime-type text/csv`
   - Snowflake:
     `snow sql --format CSV --silent --query "<SQL with LIMIT 50000>" | dekart upload-file --stdin --file-id <file_id> --name result.csv --mime-type text/csv`
4. Discover MCP tools and schemas from `dekart tools`.
5. Resolve required tool names from schema, not hardcoded names:
   - report creation tool: creates a report container
   - dataset creation tool: requires `report_id`
   - file creation tool: requires `dataset_id`
6. Execute control plane in this exact order: report -> dataset -> file.
7. Upload CSV with `dekart upload-file` and use returned `complete` payload/status.
   - BigQuery:
     `bq query ... --format=csv --max_rows=50000 'SELECT ...' | dekart upload-file --stdin --file-id <file_id> --name result.csv --mime-type text/csv`
   - Snowflake:
     `snow sql --format CSV --silent --query "<SQL with LIMIT 50000>" | dekart upload-file --stdin --file-id <file_id> --name result.csv --mime-type text/csv`
   - File-based fallback:
     `dekart upload-file --file /tmp/result.csv --file-id <file_id>`
8. Treat upload as successful only when completion status is `completed`.
9. Validate map output with snapshot after successful upload:
   - run CLI snapshot command for the target report:
     `dekart snapshot --report-id <report_id> --out /tmp/<report_id>-snapshot.png`
   - inspect the saved local PNG output from that command; do not use direct PNG URLs/links
   - verify snapshot render reflects expected area/content before finalizing
10. Return resulting IDs and URL in final response.

### Failure handling
* Do not run `dekart init`, `dekart config` on your own. Ask user to re-run `dekart init` if needed.
* If create-report or create-dataset returns 404 it likely issue with token or auth. Ask user to re-run `dekart init` and confirm before retrying.
* Snapshot equals browser. If the snapshot looks wrong, the config is wrong.
* If remote snapshot fails with timeout (for example HTTP 504 / `snapshot timeout`), ask the user to enable local snapshots:
  `dekart snapshot-local install`
  Then retry snapshot with `dekart snapshot --report-id <report_id>`.
* Datasets auto-style by default. Kepler would apply a default styling if no config is provided for dataset provided.
* If snapshot shows only basemap (no features), debug binding first:
  - confirm `layer.config.dataId` points to the report dataset id
  - confirm bound column names match exported dataset headers exactly (case-sensitive). Note: snowflake export columns names are uppercase by default.
* Never call Dekart HTTP, config files, or anything outside the documented dekart CLI.



### URL rules

1. Use `report_url` from create-report response when available.
2. Fallback to `report_path` if `report_url` is missing.
3. Never reconstruct map URL from config-derived host strings.
4. Never call create-report multiple times just to get URL fields.

## Styling the Map

After upload, review the map snapshot and tune the layer. These rules override Claude's default styling instincts. Full reference: `references/map-styling.md`.

Non-obvious rules:

1. Pick the layer for the question, not the data shape. Point for positions, H3/hexbin for normalized density, Arc for OD pairs, Line for paths, 3D Polygon for vertical magnitude.
2. Prefer high density. Points radius `0.5-4` px, lines stroke `0.5-1.5` px, polygon borders `0.5-1` px hairline. Do not clamp `LIMIT` below 50k unless cost forces it.
3. Do not show the same thing twice. A tuned Point layer already shows density, so skip the Heatmap on top. Skip outline-color when fill encodes the same value.
4. Encode with multiple channels. Color for the primary variable, radius or stroke width for magnitude, height for a second numerical dimension. Opacity is for overlap, not data.
5. Palette by data type. Sequential (Viridis, Sunset) for magnitude, Diverging (RdBu) for signed / midpoint data, Qualitative (Set2, Tableau10) for up to 8 categories. Never rainbow / jet.
6. Match basemap to density. Dark basemap for point clouds and flows, light basemap for choropleths and print.
7. Layer order bottom-up: basemap, polygon fills, lines, points, labels. Selected features always on top.
8. Lock the initial view to the zoom where the insight is visible. Do not save a world-view for a city-scale insight.

When uncertain about a specific pixel value or palette, read `references/map-styling.md`.

## H3 Aggregation

Use H3 when the user requests spatial aggregation, heatmaps, density, or cell-based rollups.

Namespace by location:
- US/default: `jslibs.h3.*`
- EU: `jslibs.eu_h3.*`

Functions:
- `jslibs.h3.ST_H3(<point>, <resolution>)` - point to cell
- `jslibs.h3.ST_H3_POLYFILLFROMGEOG(<polygon>, <resolution>)` - polygon fill
- `jslibs.h3.ST_H3_BOUNDARY(<h3_index>)` - cell boundary for visualization

Cost rules:
1. Apply `WHERE` + hardcoded bbox first, then compute H3.
2. Return `h3` + aggregate metrics before adding boundaries.
3. Use `COUNT(*)` previews before geometry-heavy `ST_H3_BOUNDARY` output.
4. Default resolution `7`-`9` for city scale.
5. If over budget, lower resolution or narrow filters before retrying.

## Failure Handling

- `bq query` unavailable or auth fails: return exact fix commands only, no auto-install.
- `snow sql` unavailable or auth fails: ask user to install/configure `snow`, then retry using `snow sql`.
- Snowflake Overture shares missing (`SHOW DATABASES LIKE 'OVERTURE_MAPS__%'` returns no rows): ask user to install Overture data from Snowflake Marketplace, then continue.
- Over budget: do not execute, return cheaper variant.
- Invalid query: return corrected SQL and rerun validation (`dry_run` for BigQuery, `COUNT(*)`/bounded preview for Snowflake).
- Never install software automatically. Report prerequisite commands for the user to run.
