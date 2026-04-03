Query validated - returns 1 row with the full Paris boundary polygon.

---

Here is the SQL for Paris boundaries:

```sql
SELECT
  id,
  subtype,
  class,
  names.primary AS name,
  geometry
FROM `bigquery-public-data.overture_maps.division_area`
WHERE country = 'FR'
  AND subtype = 'localadmin'
  AND class = 'land'
  AND LOWER(names.primary) = 'paris'
  -- bbox overlap scan gate (partition pruning)
  AND bbox.xmax >= 2.2241218090057373
  AND bbox.xmin <= 2.4697604179382324
  AND bbox.ymax >= 48.815574645996094
  AND bbox.ymin <= 48.902156829833984
LIMIT 1;
```

**What it returns:** The single `localadmin` polygon for Paris (city boundary), including the `geometry` column as a BigQuery `GEOGRAPHY` type — ready for `ST_INTERSECTS`, `ST_AREA`, or map rendering.

**Notes:**
- `subtype = 'localadmin'` is the authoritative administrative unit for the city of Paris.
- To get the `county` or `locality` variant instead, swap the subtype value — all three share the same bbox and geometry in this dataset.
- Estimated scan: ~663 MB (under 10 GiB budget).
