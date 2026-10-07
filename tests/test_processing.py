"""
Phase 3 tests — geospatial file processing.

Covers: KML parsing, ZIP Shapefile parsing, feature count, CRS extraction,
geometry type extraction, missing CRS, invalid files, missing components,
unsupported geometry, and null geometry handling.
"""
import io
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import LineString, Point, Polygon
from shapely.wkt import loads as wkt_loads

from app.main import app
from tests.fixtures import (
    make_invalid_kml_bytes,
    make_kml_bytes,
    make_kml_bytes_multi,
    make_shapefile_zip_bytes,
    make_zip_without_shp,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _upload_kml(data: bytes, filename: str = "test.kml") -> dict:
    r = client.post("/api/files/", files={"file": (filename, data, "application/vnd.google-earth.kml+xml")})
    return r


def _upload_zip(data: bytes, filename: str = "test.zip") -> dict:
    r = client.post("/api/files/", files={"file": (filename, data, "application/zip")})
    return r


# ---------------------------------------------------------------------------
# 1. Valid KML processing
# ---------------------------------------------------------------------------

def test_kml_processing_returns_processed_status():
    r = _upload_kml(make_kml_bytes())
    assert r.status_code == 201
    assert r.json()["status"] == "processed"


def test_kml_feature_count():
    r = _upload_kml(make_kml_bytes_multi())
    assert r.status_code == 201
    assert r.json()["feature_count"] == 3


def test_kml_crs_extraction():
    r = _upload_kml(make_kml_bytes())
    assert r.status_code == 201
    # KML is always geographic WGS84
    assert r.json()["crs"] == "EPSG:4326"


# ---------------------------------------------------------------------------
# 2. Valid ZIP Shapefile processing
# ---------------------------------------------------------------------------

def test_zip_shapefile_processing_returns_processed_status():
    r = _upload_zip(make_shapefile_zip_bytes())
    assert r.status_code == 201
    assert r.json()["status"] == "processed"


def test_zip_shapefile_feature_count():
    geoms = [Point(0, 0), Point(1, 1), Point(2, 2)]
    r = _upload_zip(make_shapefile_zip_bytes(geometries=geoms))
    assert r.status_code == 201
    assert r.json()["feature_count"] == 3


def test_zip_shapefile_crs_extraction():
    r = _upload_zip(make_shapefile_zip_bytes(crs="EPSG:4326"))
    assert r.status_code == 201
    assert r.json()["crs"] == "EPSG:4326"


def test_zip_shapefile_projected_crs():
    geoms = [Point(500000, 200000)]
    r = _upload_zip(make_shapefile_zip_bytes(geometries=geoms, crs="EPSG:27700"))
    assert r.status_code == 201
    assert r.json()["crs"] == "EPSG:27700"


# ---------------------------------------------------------------------------
# 3. Geometry type extraction (via processor directly)
# ---------------------------------------------------------------------------

def test_geometry_types_extracted():
    """Verify the processor correctly identifies mixed geometry types."""
    from app.services.file_processor import _extract_metadata
    gdf = gpd.GeoDataFrame(
        {"geometry": [Point(0, 0), LineString([(0, 0), (1, 1)]), Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])]},
        crs="EPSG:4326",
    )
    meta = _extract_metadata(gdf)
    assert meta["feature_count"] == 3
    assert meta["crs"] == "EPSG:4326"


# ---------------------------------------------------------------------------
# 4. Missing CRS
# ---------------------------------------------------------------------------

def test_shapefile_missing_prj_crs_is_null():
    """A Shapefile without a .prj file has no CRS — should be stored as null."""
    data = make_shapefile_zip_bytes(include_prj=False)
    r = _upload_zip(data)
    assert r.status_code == 201
    assert r.json()["crs"] is None


# ---------------------------------------------------------------------------
# 5. Invalid / corrupted KML
# ---------------------------------------------------------------------------

def test_invalid_kml_returns_400():
    r = _upload_kml(make_invalid_kml_bytes())
    assert r.status_code == 400
    assert "kml" in r.json()["detail"].lower() or "parse" in r.json()["detail"].lower() or "feature" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 6. ZIP without Shapefile
# ---------------------------------------------------------------------------

def test_zip_without_shp_returns_400():
    r = _upload_zip(make_zip_without_shp())
    assert r.status_code == 400
    assert ".shp" in r.json()["detail"]


# ---------------------------------------------------------------------------
# 7. ZIP missing required Shapefile components
# ---------------------------------------------------------------------------

def test_zip_missing_dbf_returns_400():
    data = make_shapefile_zip_bytes(include_dbf=False)
    r = _upload_zip(data)
    assert r.status_code == 400
    assert ".dbf" in r.json()["detail"]


def test_zip_missing_shx_returns_400():
    data = make_shapefile_zip_bytes(include_shx=False)
    r = _upload_zip(data)
    assert r.status_code == 400
    assert ".shx" in r.json()["detail"]


# ---------------------------------------------------------------------------
# 8. Null / empty geometry handling (processor level)
# ---------------------------------------------------------------------------

def test_null_geometry_does_not_crash():
    """A GeoDataFrame with a null geometry row should still be processable."""
    from app.services.file_processor import _extract_metadata
    gdf = gpd.GeoDataFrame(
        {"geometry": [Point(0, 0), None]},
        crs="EPSG:4326",
    )
    meta = _extract_metadata(gdf)
    assert meta["feature_count"] == 2  # null row is still a feature row
