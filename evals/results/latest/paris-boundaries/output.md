1 row, area ~105 km² — correct for Paris. Here's the validated query:

```sql
SELECT
  id,
  names.primary AS name,
  subtype,
  class,
  country,
  region,
  geometry
FROM `bigquery-public-data.overture_maps.division_area`
WHERE country = 'FR'
  AND subtype = 'county'
  AND class = 'land'
  AND bbox.xmax >= 2.2241218090057373
  AND bbox.xmin <= 2.4697604179382324
  AND bbox.ymax >= 48.815574645996094
  AND bbox.ymin <= 48.902156829833984
  AND LOWER(names.primary) = 'paris'
LIMIT 10;
```

**Validation:**
- Dry run: ~680 MB processed, within 10 GiB budget
- Rows: 1 (Paris county boundary)
- Area: ~105 km² — matches the real city of Paris

Would you like me to create a Dekart map from this result?
