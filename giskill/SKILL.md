---
name: giskill
description: Build cost-safe Overture Maps SQL for BigQuery with dry-run budget checks. Use for map-ready queries, executed results, and over-budget fallbacks.
argument-hint: [task-or-query]
---

# GIS Skill (Claude)

## Required Workflow

Follow these steps in order. Do NOT call `giskill query` until steps 1-3 are complete.

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

Use `--result-max-rows 50` if you need to see more rows.

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

1. Run with `--mode sql_only` to check estimated bytes against budget.
2. Run with `--mode execute` and a SQL `COUNT(*)` or `STRING_AGG` to confirm rows > 0 and inspect results. Do NOT use Python scripts for validation - use SQL only.
3. If 0 rows: debug before presenting. Check bbox direction, value truncation, filter logic, and column types (e.g. `admin_level` is INT64, not STRING).
4. If dry run fails: read the `error` field in the JSON output carefully. Common causes: string vs int type mismatch, missing backtick escaping, reserved keyword collision.

### Step 5: Iterate

Fix issues in small steps. Do not run broad or full extraction queries unless explicitly requested. Do not use Python to post-process query results - all validation and inspection must be done in SQL.

## CLI Command

```bash
giskill query --query "SELECT ..." --mode sql_only
giskill query --query-file /path/to/query.sql --mode execute
giskill query --query "SELECT ..." --mode execute --result-max-rows 50
```

The command handles:
- `.env` loading from current working directory
- `BQ_PROJECT_ID` fallback to `gcloud config get-value project`
- `BQ_LOCATION` passthrough
- `BQ_MAX_BYTES_BILLED` default `10737418240` (10 GiB)
- Auth: `GOOGLE_APPLICATION_CREDENTIALS` or `BIGQUERY_CREDENTIALS_BASE64`
- Mandatory dry run and budget gate before execution

## Guardrails

1. Always dry run before execution.
2. Enforce `maximum_bytes_billed`.
3. Prefer bounded SQL (bbox + date/limit + minimal columns).
4. If estimated bytes exceed budget and no explicit override: do not execute.
5. If over budget: provide at least one cheaper SQL variant.

## Mode Behavior

Infer mode from user intent unless explicitly stated.

- **`sql_only`** (default): build SQL, dry run, return SQL + estimated bytes + pass/fail.
- **`execute`**: build SQL, dry run, execute if within budget, return rows + SQL.

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

- `bq` unavailable or auth fails: return exact fix commands only, no auto-install.
- Over budget: set `status=blocked_over_budget`, do not execute, return cheaper variant.
- Invalid query: return corrected SQL and rerun dry-run logic.
- Never install software automatically. Report prerequisite commands for the user to run.

## Output Contract

Always return:
- `mode`
- `status` (`dry_run_only | executed | blocked_over_budget`)
- `project_id`, `location`
- `estimated_bytes`, `max_bytes_billed`
- `query_sql`
- `result_preview` (if executed)
- `next_steps`
