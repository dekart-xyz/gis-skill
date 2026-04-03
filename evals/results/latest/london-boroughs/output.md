33 rows confirmed. Here's your validated query for all London borough boundaries:

```sql
SELECT
  id,
  names.primary AS borough_name,
  geometry
FROM `bigquery-public-data.overture_maps.division_area`
WHERE country = 'GB'
  AND region = 'GB-ENG'
  AND subtype = 'county'
  AND class = 'land'
  -- bbox overlap gate (fast partition pruning)
  AND bbox.xmax >= -0.5097
  AND bbox.xmin <= 0.334
  AND bbox.ymax >= 51.28
  AND bbox.ymin <= 51.692
  -- exclude adjacent non-London counties that overlap the bbox
  AND names.primary NOT IN (
    'Buckinghamshire', 'Essex', 'Hertfordshire',
    'Kent', 'Surrey', 'Slough', 'Thurrock', 'Windsor and Maidenhead'
  )
ORDER BY borough_name;
```

**What it returns:** 33 rows — the 32 London boroughs + City of London — each with its full polygon geometry.

**Estimated cost:** ~707 MB (~$0.004 at standard pricing).
