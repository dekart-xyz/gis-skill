Dekart is available. Here is your validated query:

---

```sql
SELECT
  id,
  names.primary AS name,
  subtype,
  class,
  geometry
FROM `bigquery-public-data.overture_maps.division_area`
WHERE country = 'GB'
  AND region = 'GB-ENG'
  AND subtype = 'county'
  AND class = 'land'
  AND names.primary IN (
    'Barking and Dagenham','Barnet','Bexley','Brent','Bromley',
    'Camden','City of London','Croydon','Ealing','Enfield',
    'Greenwich','Hackney','Hammersmith and Fulham','Haringey','Harrow',
    'Havering','Hillingdon','Hounslow','Islington','Kensington and Chelsea',
    'Kingston upon Thames','Lambeth','Lewisham','Merton','Newham',
    'Redbridge','Richmond upon Thames','Southwark','Sutton','Tower Hamlets',
    'Waltham Forest','Wandsworth','Westminster'
  )
  AND bbox.xmax >= -0.5104
  AND bbox.xmin <= 0.3340
  AND bbox.ymax >= 51.2867
  AND bbox.ymin <= 51.6920
```

**Validation:** 33 rows (all London boroughs + City of London), total area 1,577 km² (matches real Greater London ~1,572 km²).

**Notes:**
- Source: `division_area`, `subtype='county'`, `class='land'`
- Bbox filter prunes partitions; name IN-list excludes neighboring counties (Essex, Surrey, Kent, etc.) that bbox-overlap London
- `geometry` is a polygon `GEOGRAPHY` — ready for `ST_UNION_AGG` if you want a single outer boundary

Would you like me to create a Dekart map from these results?
