---
name: dwg-to-webgis
description: "Turn AutoCAD DWG/DXF drawings into a working web GIS map: DWG to DXF, georeference (CRS), convert with GDAL/OGR to GeoPackage/GeoJSON, build PMTiles vector tiles, and publish a MapLibre GL JS web map. Use when the user has CAD drawings (DWG/DXF, site plans, parcels, utilities, survey) and wants them on an interactive web map. Not for 3D BIM/IFC or SolidWorks models."
metadata:
  version: "1.0.0"
  derived_from: "isaaccorley/geospatial-skills@gdal and jaakla/openmapstack-skills@open-map-stack, plus CAD-specific steps"
---

# DWG to Web GIS

End-to-end pipeline: **DWG -> DXF -> georeferenced GeoPackage -> (GeoJSON | PMTiles) -> MapLibre web map.**

CAD files are drawings, not geodata. Three things break most conversions, so settle them first:
1. **DWG has no reliable CRS.** Coordinates are usually local or projected, and the file does not say which. Never guess.
2. **Units.** Drawing units may be metres, millimetres or feet.
3. **Semantics.** CAD stores layers, blocks and text, not typed features. Map layers to feature classes deliberately.

## Step 0: Ask before starting (do not assume)

- Which **CRS/EPSG** were the drawings made in (e.g. UTM zone, national grid, or a local arbitrary origin)? For Iran common choices are EPSG:32638 / 32639 / 32640 (UTM 38N-40N); confirm with the user.
- **Drawing units** (`INSUNITS`) and whether coordinates are real-world or local.
- Which **layers** matter (parcels, roads, buildings, utilities, annotation)? Which to drop (title block, hatches, dimensions)?
- Target: static site, or a server with updates? Expected size (features, number of files)?
- A **known control point** (a real coordinate for a known corner/feature) to verify placement.

If the CRS is unknown, say so and stop at a local-coordinates preview. Fabricating a CRS puts the data in the wrong place.

## Step 1: DWG to DXF (GDAL cannot read DWG without commercial drivers)

Use one of (never overwrite the original DWG):
- **AutoCAD** (user has 2027 at `C:\Program Files\Autodesk\AutoCAD 2027\acad.exe`): open the DWG and run `DXFOUT` (or Save As DXF, AutoCAD 2018 DXF is a safe target). Scripted via COM (`pywin32`) is possible; verify the DXF format constant against the installed type library rather than hard-coding a number.
- **ODA File Converter** (free, batch): `ODAFileConverter "<in_dir>" "<out_dir>" ACAD2018 DXF 0 1` (args: input folder, output folder, version, type, recurse, audit). Verify the argument order with its help text.
- Keep ASCII DXF; binary DXF is poorly supported by many tools.

## Step 2: Inspect the DXF before converting

```bash
ogrinfo input.dxf -so -al            # layers/summary (bare -so without -al prints little)
```
```python
# pip/conda: ezdxf   (Python 3.10+; use -I when running scripts on untrusted files)
import ezdxf
doc = ezdxf.readfile("input.dxf")
print(doc.header.get("$INSUNITS"), doc.header.get("$EXTMIN"), doc.header.get("$EXTMAX"))
print([l.dxf.name for l in doc.layers])
msp = doc.modelspace()
from collections import Counter
print(Counter(e.dxftype() for e in msp))
```
Check: extents plausible for the claimed CRS (e.g. UTM eastings ~100000-900000), entity types (LWPOLYLINE, LINE, CIRCLE, ARC, HATCH, INSERT blocks, TEXT/MTEXT), and which layers hold real geometry.

### Step 2b: See the drawing the way AutoCAD shows it (layer colours, text, per-layer)

Claude cannot open a DWG directly, but it can **render the DXF to a PNG and look at it** (tested). `scripts/render_dxf.py` (in this skill's folder) uses ezdxf's drawing add-on with the matplotlib backend, so layer colours, text and linetypes follow the drawing's own layer table on a dark AutoCAD-like background.

```bash
# layer table + entity counts per layer (no image)
python -I <skill>/scripts/render_dxf.py input.dxf --list
# whole drawing
python -I <skill>/scripts/render_dxf.py input.dxf all.png
# only chosen layers (others are switched off), e.g. to check one layer at a time
python -I <skill>/scripts/render_dxf.py input.dxf parcels.png --layers PARCELS,TEXT --dpi 200
```
Then view the PNG with the Read tool. Workflow: render everything, then each important layer on its own, and compare with the user's description or a screenshot from AutoCAD. Use this **before** and **after** conversion (render the GeoPackage layers with geopandas/matplotlib to compare against the DXF render) to catch dropped layers, wrong scale or flipped axes.

Limits: it shows modelspace only (not paper-space layouts, plotted lineweights or xrefs that are missing); fonts may differ from AutoCAD (SHX fonts); a huge drawing needs a lower `--dpi` or a layer subset. `$EXTMIN/$EXTMAX` in the header can be unset (1e+20) or stale; compute real extents from the entities, not the header. If a render and AutoCAD disagree, trust AutoCAD and report the difference.

## Step 3: Convert to GeoPackage with an explicit CRS

DXF carries no CRS, so **assign** the source CRS with `-a_srs` (labels it) and reproject separately. Preserve the layer name as an attribute.

```bash
# Label the CAD coordinates with the CRS the user confirmed (EPSG:XXXXX), keep as GeoPackage
ogr2ogr -f GPKG out.gpkg input.dxf -a_srs EPSG:XXXXX -nln cad_entities

# Web copy in WGS84 (GeoJSON/web layers use lon,lat order)
ogr2ogr -f GPKG web.gpkg out.gpkg -t_srs EPSG:4326
ogr2ogr -f GeoJSON out.geojson out.gpkg -t_srs EPSG:4326
```
If `ogr2ogr` is not on PATH (it is not when GDAL came only from `pip install pyogrio`), do the same with Python; this exact flow was tested with a sample DXF (GDAL 3.12 via pyogrio, DXF driver present):
```python
import geopandas as gpd
g = gpd.read_file("input.dxf")                 # one OGR layer "entities", columns include Layer; crs is None
g = g.set_crs(32639, allow_override=True)      # LABEL with the CRS the user confirmed (not a reprojection)
g.to_file("out.gpkg", layer="cad_entities", driver="GPKG")
g.to_crs(4326).to_file("out.geojson", driver="GeoJSON")
```
Observed with the DXF driver: DXF has **no CRS** (`crs is None`); **closed LWPOLYLINEs and CIRCLEs come out as LineString, not Polygon**; TEXT comes out as Point; the CAD layer is in the `Layer` column.

Notes:
- Prefer **GeoPackage** (or GeoParquet) as the working format; never produce Shapefile as new output (truncated field names, 2 GB limit, no UTF-8).
- OGR's DXF driver exposes entities with a `Layer` field and puts text as points (label in style/attributes). Blocks (INSERT) are inlined by default.
- Split by CAD layer into typed feature layers (parcels as polygons, roads as lines, etc.): filter with SQL, e.g. `-dialect SQLite -sql "SELECT * FROM entities WHERE Layer = 'PARCELS'"`. OGR's default SQL dialect has no GROUP BY or spatial functions, so use `-dialect SQLite` for anything beyond simple SELECT/WHERE.
- **Closed polylines are lines, not polygons.** Build polygons deliberately (`ogr2ogr ... -nlt` plus `ST_BuildArea`/polygonize with SQLite dialect, or `shapely.polygonize`), and report what was inferred.
- Drop construction junk: title blocks, dimension lines, hatches, frames; zero-length geometries; duplicates.
- Never calculate distance/area/buffer in EPSG:4326 (degrees). Use the projected CRS for metric work.
- Check units: if the drawing is in millimetres and the CRS is metres, scale first (`-ct` or `ST_Scale`), and report the factor.

## Step 4: Validate (do not skip)

```bash
ogrinfo out.gpkg cad_entities -so                         # feature count, extent, CRS
ogrinfo out.gpkg -dialect SQLite -sql "SELECT COUNT(*) FROM cad_entities"
```
- Feature count per layer matches the DXF counts for the kept entity types.
- **Control point test:** transform the known real-world coordinate and confirm it lands on the right place on a basemap. A correct CRS label does not prove correct coordinates.
- Extent sits inside the expected area of interest. A layer far outside signals a wrong CRS, an axis swap, or wrong units.
- Geometries valid (`ST_IsValid`), no empty geometries.

## Step 5: Tiles (only if the data is large)

Small data (a few MB): serve GeoJSON directly. Larger: PMTiles.
```bash
ogr2ogr -f GeoJSONSeq /vsistdout/ web.gpkg parcels -t_srs EPSG:4326 \
  | tippecanoe -o parcels.pmtiles -l parcels -zg --drop-densest-as-needed
pmtiles show parcels.pmtiles       # verify
```
Watch tippecanoe tile-size warnings; prefer simplification and attribute pruning over dropping classes. Use Martin in front of PostGIS only when data changes often or needs per-user filtering.

## Step 6: MapLibre web map

Layer placement and coordinate order: GeoJSON and MapLibre use **[lon, lat]** (Leaflet uses [lat, lng]). Basemap and attribution must be visible; use a provider the user approves (OSM tiles are not for heavy production traffic).

Minimal page (GeoJSON source):
```html
<link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet">
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<div id="map" style="position:absolute;inset:0"></div>
<script>
const map = new maplibregl.Map({
  container: 'map',
  style: { version: 8, sources: { osm: { type: 'raster',
    tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'], tileSize: 256,
    attribution: '&copy; OpenStreetMap contributors' } },
    layers: [{ id: 'osm', type: 'raster', source: 'osm' }] },
  center: [LON, LAT], zoom: 15
});
map.on('load', () => {
  map.addSource('cad', { type: 'geojson', data: 'out.geojson' });
  map.addLayer({ id: 'cad-lines', type: 'line', source: 'cad',
    filter: ['==', '$type', 'LineString'], paint: { 'line-color': '#e11d48', 'line-width': 1.5 } });
  map.addLayer({ id: 'cad-fill', type: 'fill', source: 'cad',
    filter: ['==', '$type', 'Polygon'], paint: { 'fill-color': '#2563eb', 'fill-opacity': 0.3 } });
});
</script>
```
For PMTiles, register the `pmtiles` protocol and set `source: { type: 'vector', url: 'pmtiles://parcels.pmtiles' }` with the `source-layer` name used in tippecanoe (`-l`). Pin library versions and, for production, either self-host MapLibre (`npm i maplibre-gl`) or add `integrity="sha384-..."` and `crossorigin="anonymous"` to the CDN `<script>`/`<link>` tags (compute the hash for the exact pinned file; the example above omits it). Add popups on click showing the CAD `Layer` and key attributes. Preview locally with a static server, not `file://` (fetch and range requests need HTTP).

## Step 7: Deliver and document

Deliver: the converted data, the page, and a short README recording **source file names, CRS assumed/confirmed, units, scale factor, layers kept/dropped, polygons inferred, validation results (counts, control point) and open risks.** Make the pipeline a script so it reruns cleanly from the original DWG.

## Anti-patterns

- Guessing the CRS or silently assuming metres.
- Treating closed polylines as polygons without saying so.
- Shapefile as new output; calculating metric values in EPSG:4326; mixing CRS silently.
- Dropping layers or blocks without telling the user; losing the CAD `Layer` attribute.
- Fabricating geometry or placeholder coordinates to make the map "look right".
- Skipping the control-point check; delivering without recording assumptions.

## Prerequisites (tell the user if missing)

Python with `ezdxf`, `matplotlib`, `geopandas`, `pyogrio`, `shapely`, `pyproj` (`python -m pip install ezdxf matplotlib geopandas pyogrio shapely pyproj`; `pyogrio` wheels bundle GDAL with the DXF driver). The `ogr2ogr`/`ogrinfo` CLIs are **not** included by pip; for them install GDAL separately (conda-forge, OSGeo4W, QGIS or the official GDAL container; prefer these over pip-only builds for the CLI), and the Python equivalents above work without it. Optionally `tippecanoe` and `pmtiles` CLIs for tiles, and AutoCAD or ODA File Converter for DWG->DXF. If something is missing, tell the user before continuing.
