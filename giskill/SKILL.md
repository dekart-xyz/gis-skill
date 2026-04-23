---
name: giskill
description: Build cost-safe Overture Maps SQL for BigQuery, then create Dekart maps by uploading query results through giskill CLI + Dekart MCP.
---

# GIS Skill (Claude)

## Required Workflow

Follow these steps in order. Do NOT write a final query until steps 1-3 are complete.

### Step 1: Discover schema

Run INFORMATION_SCHEMA to confirm table and column names before writing any query.

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

### Step 2: Resolve the target area

When the user asks about a named area (city, district, country), query `division_area` first to discover how it is actually stored (subtype, class, naming conventions). Do not assume from general knowledge.

```sql
SELECT subtype, class, names.primary, bbox.xmin, bbox.xmax, bbox.ymin, bbox.ymax
FROM `bigquery-public-data.overture_maps.division_area`
WHERE country = '<iso2>'
  AND LOWER(names.primary) LIKE '%<area_name>%'
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

Full pattern:

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

### Step 4: Validate (mandatory)

Do NOT present the query to the user without validating it first.

1. Dry run: `bq query --use_legacy_sql=false --dry_run --format=json '<SQL>'` to check estimated bytes.
2. Validate row count: execute `COUNT(*)` (or equivalent) to confirm rows > 0. Use SQL only, do NOT use Python for validation.
3. Validate total area when possible: if output includes polygonal `GEOGRAPHY` geometry, compute total area (for example `SUM(ST_AREA(geometry))`) and return units in square meters (and optionally km²).
   - If geometry is non-polygonal (point/line) or no geometry is selected, explicitly state area validation is not applicable.
4. If Dekart is available, use report snapshot validation for map outputs:
   - check availability with `giskill dekart tools --json`
   - if available, create snapshot URL with Dekart MCP snapshot tool and verify rendered output matches expected extent/content
5. If Dekart is not available, continue SQL validation and explicitly offer:
   - `giskill dekart init`
   - then rerun snapshot validation for better visual QA
6. If validation fails debug before presenting. Check bbox direction, value truncation, filter logic, and column types (e.g. `admin_level` is INT64, not STRING).
7. If dry run fails: read the bq error output. Common causes: string vs int type mismatch, missing backtick escaping, reserved keyword collision.

### Step 5: Iterate

Fix issues in small steps. Do not run broad or full extraction queries unless explicitly requested. All validation must be done in SQL.

## Running Queries

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

## Create Map From BigQuery Results

Use this when the user wants a map from BigQuery query output in Dekart.

### What is Dekart

Dekart is a SQL-first map workspace. It stores map artifacts in this hierarchy:
- `report`: top-level map container.
- `dataset`: one data layer slot inside a report.
- `file`: uploaded data artifact attached to a dataset.

### Core concepts

- control plane: create `report` -> create `dataset` -> create `file`.
- upload wrapper: CLI command that performs multipart upload and completion for a local file.

### Agent behavior

1. Mandatory first step: Dekart init check.
   - run `giskill dekart tools --json`
   - if this fails due auth/init, ask user to run `giskill dekart init`
   - after init, retry `giskill dekart tools --json` and only then continue
   - do not run BigQuery, upload, or Dekart write actions before this succeeds
2. Use CLI help for current command behavior: `giskill dekart --help`, `giskill dekart tools --help`, `giskill dekart call --help`, `giskill dekart upload-file --help`.
3. After a successful analytical answer, proactively offer to create a Dekart map from the result. If user declines, stop map flow.
4. Export result rows to CSV with explicit row controls. `--max_rows` is mandatory because BigQuery CLI defaults to 100 rows when omitted.
   - CSV export must keep stderr separate from CSV bytes.
   - Never use `2>&1` when output is redirected to `.csv`.
   - Safe pattern:
     `bq query ... --format=csv ... > /tmp/result.csv 2>/tmp/result.stderr.log`
   - Optional row check:
     `wc -l /tmp/result.csv`
5. Discover MCP tools and schemas from `giskill dekart tools`.
6. Resolve required tool names from schema, not hardcoded names:
   - report creation tool: creates a report container
   - dataset creation tool: requires `report_id`
   - file creation tool: requires `dataset_id`
7. Execute control plane in this exact order: report -> dataset -> file.
8. Upload CSV with `giskill dekart upload-file` and use returned `complete` payload/status.
9. Treat upload as successful only when completion status is `completed`.
10. Validate map output with snapshot after successful upload:
   - call Dekart snapshot tool for the target report
   - verify snapshot render reflects expected area/content before finalizing
11. Return resulting IDs and URL in final response.

### Response requirements

Always return:
1. Report ID.
2. Dataset ID.
3. File ID.
4. Upload completion status.
5. Report URL.

URL rules:
1. Use `report_url` from create-report response when available.
2. Fallback to `report_path` if `report_url` is missing.
3. Never reconstruct map URL from config-derived host strings.
4. Never call create-report multiple times just to get URL fields.

## Styling the Map

After upload, review the Dekart snapshot and tune the layer. These rules override Claude's default styling instincts. Full reference: `references/map-styling.md`.

Non-obvious rules:

1. Pick the layer for the question, not the data shape. Point for positions, H3/hexbin for normalized density, Arc for OD pairs, Line for paths, 3D Polygon for vertical magnitude.
2. Prefer high density. Points radius `2-4` px, lines stroke `0.5-1.5` px, polygon borders `0.5-1` px hairline. Do not clamp `LIMIT` below 50k unless cost forces it.
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
- Over budget: do not execute, return cheaper variant.
- Invalid query: return corrected SQL and rerun dry-run.
- Never install software automatically. Report prerequisite commands for the user to run.
