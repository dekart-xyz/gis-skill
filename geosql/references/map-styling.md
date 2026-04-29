# Map Styling Reference (Kepler.gl / Dekart)

Deep reference for styling choices after data is loaded. SKILL.md contains the short rules; this file explains the why and lists concrete pixel values.

## 1. Pick the layer for the question, not the data shape

| Question | Best layer | Avoid |
| --- | --- | --- |
| Where are things? | Point | Heatmap (hides positions) |
| Where is the density? | Point with tuned radius/opacity | Adding heatmap on top of points |
| Hotspots over a normalized area | H3 or hexbin | Cluster (hides magnitude) |
| Flows between two places | Arc | Line (implies a path) |
| Movement along a path | Line / Trip | Arc |
| Categorical comparison across regions | Polygon choropleth | Point color by category |
| Vertical magnitude (revenue, count) | 3D Polygon height or H3 height | Color alone |

Heuristic: if a well-tuned Point layer already shows the density, a Heatmap is redundant. Pick one.

## 2. High-density defaults

Claude's default instinct is to clamp rows and use large symbols. Invert:

- Points: radius 2-4 px, opacity 0.6-0.8, fill 50k-1M rows.
- Lines (networks, roads): stroke 0.5-1.5 px. Emphasis lines 2-4 px.
- Polygon borders: 0.5-1 px hairline, lower opacity than fill.
- Arcs: thin (1-2 px), low opacity (0.3-0.5) when many overlap.
- H3/hexbin: resolution 7-9 for city, 5-6 for country.

Never pre-cap `LIMIT` below 50k unless cost forces it. Dekart handles 1M rows.

## 3. Encode with multiple channels

Color alone wastes channels. For a single layer:

- Color: primary categorical or sequential variable.
- Radius / stroke width: magnitude.
- Height (3D extrusion): second numerical dimension.
- Opacity: overlap management, not a data variable.

Example: charger stations. Color = operator (qualitative), radius = kW rating (sequential), height off.

## 4. Palette rules

- Sequential: one-direction magnitude. Examples: Viridis, Sunset, YlOrRd.
- Diverging: meaningful midpoint (e.g. growth vs decline). Examples: RdBu, BrBG.
- Qualitative: distinct categories, max 8. Examples: Set2, Tableau10.
- Avoid: rainbow, jet, hue-cycling palettes. Not perceptually uniform.
- Dark basemap pairs with bright saturated colors. Light basemap pairs with deep saturated colors.

## 5. Don't show the same thing twice

Redundant encodings dilute attention. Pick one:

- Point + heatmap of the same points: drop the heatmap.
- Polygon fill + outline colored by the same value: drop the outline color.
- Choropleth + labels of the same value: drop one.
- Cluster + point: pick the zoom level's winner.

## 6. Layer order (z-stack)

Bottom to top:

1. Basemap
2. Area fills (polygon, choropleth)
3. Lines and routes
4. Points
5. Labels and selected / highlighted features

Kepler layer panel is top-to-bottom = render order top layer. Drag accordingly.

## 7. Basemap choice

- Dark: density, flows, point clouds. Best contrast for bright data.
- Light: choropleths, printable maps, small multiples.
- Satellite: only when imagery is part of the narrative (infrastructure, terrain).
- Muted (Positron, Dark Matter): always safer than default vector basemap for presentations.

## 8. Framing and initial view

- Lock the initial view to the zoom at which the insight is visible.
- If the insight reads at city scale, do not save a country-level view.
- Crop the extent around meaningful data, not the full dataset.

## 9. Common Claude mistakes to avoid

- Adding a heatmap on top of points "to show density".
- Using a rainbow palette for sequential data.
- Setting point radius to 10 px by default.
- Clamping `LIMIT 1000` when 100k would show the pattern.
- Encoding only with color when stroke/size/height are free.
- Choosing Light basemap for a dense point cloud.
- Leaving the default world-view extent on a city-scale insight.

## 10. Sources

- https://www.axismaps.com/guide
- https://docs.kepler.gl/docs/user-guides
- ColorBrewer: https://colorbrewer2.org
