# A6 quality-control report — `a6-worldpop-r2025a-2026-v1`

Built 2026-10-28T19:35:35+00:00

| Severity | Checks |
|---|---|
| ✅ PASS | 23 |
| ℹ️ INFO | 4 |
| ⚠️ WARNING | 0 |
| ❌ ERROR | 0 |
| ❓ UNRESOLVED | 0 |

**Receptors:** 1,034,281 populated cells · **study-area population:** 8,114,810

## Population within distance of the OEJN reference point

| radius (km) | population | populated cells |
|---|---|---|
| 5 | 143,592 | 7,726 |
| 10 | 798,292 | 28,967 |
| 15 | 1,599,008 | 55,897 |
| 20 | 2,133,793 | 82,951 |
| 30 | 3,089,165 | 136,283 |
| 40 | 3,720,546 | 191,053 |
| 60 | 4,133,741 | 294,089 |
| 80 | 5,569,183 | 407,146 |
| 100 | 6,729,674 | 522,159 |

## Checks

| check | severity | message |
|---|---|---|
| a6.source.mode | ℹ️ INFO | Using study-area extract a6_study_area_extract.tif created 2026-10-28T19:31:40+00:00 (rasterio 1.5.2, GDAL 3.12.2) |
| a6.source.sha256 | ✅ PASS | Extract manifest: national source SHA-256 matches the locked value |
| a6.source.extract_sha256 | ✅ PASS | Extract file SHA-256 matches its manifest |
| a6.raster.dimensions | ✅ PASS | National raster dimensions (from manifest): (25407, 18930) |
| a6.raster.crs | ✅ PASS | National raster crs (from manifest): 4326 |
| a6.raster.nodata | ✅ PASS | National raster nodata (from manifest): -99999.0 |
| a6.raster.dtype | ✅ PASS | National raster dtype (from manifest): float32 |
| a6.raster.pixel_size | ✅ PASS | National raster pixel_size (from manifest): True |
| a6.study_area.inside_raster | ✅ PASS | Study area {'south': 20.0, 'north': 23.0, 'west': 38.0, 'east': 41.0} lies inside the raster (pixel window cols 4206-7807, rows 10986-14587) |
| a6.extract.window | ✅ PASS | Extract window {'col_off': 4206, 'row_off': 10986, 'width': 3601, 'height': 3601} equals the window recomputed from the study area |
| a6.extract.aligned | ✅ PASS | Extract is pixel-aligned with the national WorldPop grid |
| a6.extract.properties | ✅ PASS | Extract CRS, nodata, dtype and size as expected |
| a6.extract.total | ✅ PASS | Extract total equals the total recorded at extraction time |
| a6.values.no_nan | ✅ PASS | No NaN/inf values in the study window |
| a6.values.non_negative | ✅ PASS | No negative population values (other than nodata) |
| a6.values.audit | ℹ️ INFO | Study window 3601 x 3601 pixels: 11,932,335 nodata (sea / outside settlements), 585 zero, 1,034,281 populated; max 80.88 people per cell |
| a6.crs.utm_roundtrip | ✅ PASS | WGS84 -> UTM 37N -> WGS84 round trip error 1.4e-14 deg (< 1e-9 deg, i.e. < 0.1 mm) |
| a6.conservation.total | ✅ PASS | Population conserved exactly: window total = receptor total = 8,114,810.242 |
| a6.receptors.unique_ids | ✅ PASS | 1,034,281 receptors, each identified by its unique (src_row, src_col) in the national raster |
| a6.receptors.inside_window | ✅ PASS | Every receptor lies inside the study window |
| a6.cell_area.sanity | ✅ PASS | Geodesic cell area agrees with the spherical approximation within 0.51% (cells 7,885-8,045 m^2) |
| a6.national_total | ℹ️ INFO | National raster total (Saudi Arabia 2026, WorldPop R2025A): 34,868,384 people in 8,109,692 populated cells; study area holds 23.3% |
| a6.sanity.airport_core | ℹ️ INFO | Population within 1 km of the OEJN reference point: 1,584.2 (expected to be small: airfield) |
| a6.aggregate.6px.conserved | ✅ PASS | 6x6-pixel grid (0.005 deg): 66,305 bins, total conserved |
| a6.aggregate.12px.conserved | ✅ PASS | 12x12-pixel grid (0.010 deg): 24,446 bins, total conserved |
| a6.aggregate.24px.conserved | ✅ PASS | 24x24-pixel grid (0.020 deg): 8,766 bins, total conserved |
| a6.clip.bit_identical | ✅ PASS | Clipped GeoTIFF is bit-identical to the source window (no resampling) |
