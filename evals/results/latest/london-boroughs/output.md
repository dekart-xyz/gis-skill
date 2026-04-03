All 33 London boroughs confirmed. Here's the validated SQL:

---

### London Boundaries — all 33 boroughs (individual polygons)

```sql
WITH london_boroughs AS (
  SELECT names.primary AS borough_name, geometry
  FROM `bigquery-public-data.overture_maps.division_area`
  WHERE country = 'GB'
    AND region = 'GB-ENG'
    AND subtype = 'county'
    AND class = 'land'
    -- bbox overlap gate (Greater London extent)
    AND bbox.xmax >= -0.5097206234931946
    AND bbox.xmin <= 0.33399567008018494
    AND bbox.ymax >= 51.28675842285156
    AND bbox.ymin <= 51.69187927246094
    AND names.primary IN (
      'Barking and Dagenham', 'Barnet', 'Bexley', 'Brent', 'Bromley',
      'Camden', 'City of London', 'Croydon', 'Ealing', 'Enfield',
      'Greenwich', 'Hackney', 'Hammersmith and Fulham', 'Haringey',
      'Harrow', 'Havering', 'Hillingdon', 'Hounslow', 'Islington',
      'Kensington and Chelsea', 'Kingston upon Thames', 'Lambeth',
      'Lewisham', 'Merton', 'Newham', 'Redbridge', 'Richmond upon Thames',
      'Southwark', 'Sutton', 'Tower Hamlets', 'Waltham Forest',
      'Wandsworth', 'Westminster'
    )
)
SELECT borough_name, geometry
FROM london_boroughs
ORDER BY borough_name;
```

**Returns:** 33 rows — one polygon per London borough + City of London.  
**Estimated cost:** ~671 MB processed.

---

### Variant — single outer boundary (dissolved Greater London)

If you need a single merged polygon of the entire Greater London area:

```sql
WITH london_boroughs AS (
  -- same CTE as above
  SELECT geometry
  FROM `bigquery-public-data.overture_maps.division_area`
  WHERE country = 'GB'
    AND region = 'GB-ENG'
    AND subtype = 'county'
    AND class = 'land'
    AND bbox.xmax >= -0.5097206234931946
    AND bbox.xmin <= 0.33399567008018494
    AND bbox.ymax >= 51.28675842285156
    AND bbox.ymin <= 51.69187927246094
    AND names.primary IN (
      'Barking and Dagenham', 'Barnet', 'Bexley', 'Brent', 'Bromley',
      'Camden', 'City of London', 'Croydon', 'Ealing', 'Enfield',
      'Greenwich', 'Hackney', 'Hammersmith and Fulham', 'Haringey',
      'Harrow', 'Havering', 'Hillingdon', 'Hounslow', 'Islington',
      'Kensington and Chelsea', 'Kingston upon Thames', 'Lambeth',
      'Lewisham', 'Merton', 'Newham', 'Redbridge', 'Richmond upon Thames',
      'Southwark', 'Sutton', 'Tower Hamlets', 'Waltham Forest',
      'Wandsworth', 'Westminster'
    )
)
SELECT ST_UNION_AGG(geometry) AS greater_london_boundary
FROM london_boroughs;
```

**Note:** "Greater London" has no single row in Overture Maps — the dataset models it as 33 borough-level county polygons. The IN list above is the authoritative filter.
