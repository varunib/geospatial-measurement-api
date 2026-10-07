"""
Shared test fixtures — programmatic geospatial data builders.

All fixtures produce minimal but real geospatial data using GeoPandas
and Shapely so tests never depend on files on disk or external resources.
"""
import io
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, Point, Polygon


# ---------------------------------------------------------------------------
# KML
# ---------------------------------------------------------------------------

def make_kml_bytes(geometry_type: str = "Point") -> bytes:
    """Return a minimal valid KML file as bytes."""
    if geometry_type == "Polygon":
        coords = "-1,51 1,51 1,52 -1,52 -1,51"
        geom_tag = f"<Polygon><outerBoundaryIs><LinearRing><coordinates>{coords}</coordinates></LinearRing></outerBoundaryIs></Polygon>"
    elif geometry_type == "LineString":
        geom_tag = "<LineString><coordinates>-1,51 1,52</coordinates></LineString>"
    else:
        geom_tag = "<Point><coordinates>-0.1,51.5,0</coordinates></Point>"

    kml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
  <Placemark><name>Feature 1</name>{geom_tag}</Placemark>
</Document>
</kml>""".encode()
    return kml


def make_kml_bytes_multi() -> bytes:
    """KML with mixed geometry types: Point + LineString + Polygon."""
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
  <Placemark><name>P</name><Point><coordinates>0,0,0</coordinates></Point></Placemark>
  <Placemark><name>L</name><LineString><coordinates>0,0 1,1</coordinates></LineString></Placemark>
  <Placemark><name>A</name><Polygon><outerBoundaryIs><LinearRing><coordinates>0,0 1,0 1,1 0,1 0,0</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>
</Document>
</kml>"""


def make_invalid_kml_bytes() -> bytes:
    """Bytes that look like KML but are not parseable."""
    return b"<?xml version='1.0'?><kml><broken></kml>"


# ---------------------------------------------------------------------------
# Shapefile ZIP
# ---------------------------------------------------------------------------

def make_shapefile_zip_bytes(
    geometries: list | None = None,
    crs: str = "EPSG:4326",
    include_shx: bool = True,
    include_dbf: bool = True,
    include_prj: bool = True,
) -> bytes:
    """
    Build a real in-memory Shapefile ZIP using GeoPandas.
    Optionally omit sidecar files to test validation.
    """
    if geometries is None:
        geometries = [Point(0, 0), Point(1, 1)]

    gdf = gpd.GeoDataFrame(
        {"name": [f"feature_{i}" for i in range(len(geometries))]},
        geometry=geometries,
        crs=crs,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        shp_path = Path(tmpdir) / "data.shp"
        gdf.to_file(shp_path)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for f in Path(tmpdir).iterdir():
                ext = f.suffix.lower()
                if ext == ".shx" and not include_shx:
                    continue
                if ext == ".dbf" and not include_dbf:
                    continue
                if ext == ".prj" and not include_prj:
                    continue
                zf.write(f, f.name)
        return buf.getvalue()


def make_zip_without_shp() -> bytes:
    """ZIP that contains no .shp file at all."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", "no shapefile here")
    return buf.getvalue()


def make_corrupted_zip_bytes() -> bytes:
    return b"PK\x03\x04this is not a real zip archive"
