"""
Phase 5 tests — GET /api/files/{id}/measurements/ and GET /api/files/{id}/

Each test uploads its own file to get a fresh file_id, making tests
fully independent of store state and execution order.
"""
import geopandas as gpd
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import GeometryCollection, LineString, Point, Polygon

from app.main import app
from app.storage.store import store
from tests.fixtures import make_kml_bytes, make_kml_bytes_multi, make_shapefile_zip_bytes

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _upload_kml(data: bytes, filename: str = "test.kml") -> int:
    """Upload a KML file and return its assigned file_id."""
    r = client.post(
        "/api/files/",
        files={"file": (filename, data, "application/vnd.google-earth.kml+xml")},
    )
    assert r.status_code == 201, f"Upload failed: {r.json()}"
    return r.json()["id"]


def _upload_zip(data: bytes, filename: str = "test.zip") -> int:
    """Upload a ZIP Shapefile and return its assigned file_id."""
    r = client.post(
        "/api/files/",
        files={"file": (filename, data, "application/zip")},
    )
    assert r.status_code == 201, f"Upload failed: {r.json()}"
    return r.json()["id"]


def _inject_gdf(file_id: int, gdf: gpd.GeoDataFrame) -> None:
    """
    Directly replace the GeoDataFrame on a stored record.
    Used to test edge cases (missing CRS, unsupported geometry) without
    needing to produce a real file that GeoPandas would reject at read time.
    """
    record = store.get(file_id)
    record.geodataframe = gdf
    record.crs = str(gdf.crs) if gdf.crs else None
    store.update(record)


# ---------------------------------------------------------------------------
# GET /api/files/{id}/ — file info endpoint
# ---------------------------------------------------------------------------

def test_get_file_info_returns_metadata():
    file_id = _upload_kml(make_kml_bytes())
    r = client.get(f"/api/files/{file_id}/")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == file_id
    assert "filename" in data
    assert "status" in data
    assert "feature_count" in data
    assert "crs" in data


def test_get_file_info_not_found():
    r = client.get("/api/files/99999/")
    assert r.status_code == 404
    assert "99999" in r.json()["detail"]


# ---------------------------------------------------------------------------
# 1. Valid Polygon file
# ---------------------------------------------------------------------------

def test_measurements_polygon():
    geoms = [Polygon([(-1, 51), (0, 51), (0, 52), (-1, 52), (-1, 51)])]
    file_id = _upload_zip(make_shapefile_zip_bytes(geometries=geoms))
    r = client.get(f"/api/files/{file_id}/measurements/")
    assert r.status_code == 200
    data = r.json()
    assert data["file_id"] == file_id
    m = data["measurements"][0]
    assert m["geometry_type"] == "Polygon"
    assert m["area_m2"] is not None
    assert m["area_m2"] > 1_000_000  # must be in m², not degrees
    assert m["length_m"] is None


# ---------------------------------------------------------------------------
# 2. Valid LineString file
# ---------------------------------------------------------------------------

def test_measurements_linestring():
    geoms = [LineString([(0, 51), (1, 51)])]
    file_id = _upload_zip(make_shapefile_zip_bytes(geometries=geoms))
    r = client.get(f"/api/files/{file_id}/measurements/")
    assert r.status_code == 200
    m = r.json()["measurements"][0]
    assert m["geometry_type"] == "LineString"
    assert m["length_m"] is not None
    assert m["length_m"] > 1000  # must be in metres, not degrees
    assert m["area_m2"] is None


# ---------------------------------------------------------------------------
# 3. Valid Point file
# ---------------------------------------------------------------------------

def test_measurements_point():
    file_id = _upload_kml(make_kml_bytes("Point"))
    r = client.get(f"/api/files/{file_id}/measurements/")
    assert r.status_code == 200
    m = r.json()["measurements"][0]
    assert m["geometry_type"] == "Point"
    assert m["area_m2"] is None
    assert m["length_m"] is None
    assert m["message"] is not None
    assert "Point" in m["message"]


# ---------------------------------------------------------------------------
# 4. Mixed geometry file (Point + LineString + Polygon)
# ---------------------------------------------------------------------------

def test_measurements_mixed_geometries():
    file_id = _upload_kml(make_kml_bytes_multi())
    r = client.get(f"/api/files/{file_id}/measurements/")
    assert r.status_code == 200
    data = r.json()
    assert len(data["measurements"]) == 3
    types = {m["geometry_type"] for m in data["measurements"]}
    assert "Point" in types
    assert "LineString" in types
    assert "Polygon" in types


# ---------------------------------------------------------------------------
# 5. EPSG:4326 input — verify reprojection happened
# ---------------------------------------------------------------------------

def test_measurements_epsg4326_reprojected():
    """source_crs must be EPSG:4326 but projected_crs must differ (UTM)."""
    geoms = [Polygon([(-1, 51), (0, 51), (0, 52), (-1, 52), (-1, 51)])]
    file_id = _upload_zip(make_shapefile_zip_bytes(geometries=geoms, crs="EPSG:4326"))
    r = client.get(f"/api/files/{file_id}/measurements/")
    assert r.status_code == 200
    data = r.json()
    assert data["source_crs"] == "EPSG:4326"
    assert data["projected_crs"] != "EPSG:4326"
    assert data["projected_crs"].startswith("EPSG:326")  # UTM North zone


# ---------------------------------------------------------------------------
# 6. Already-projected CRS — passes through unchanged
# ---------------------------------------------------------------------------

def test_measurements_projected_crs_passthrough():
    """EPSG:27700 is already projected — projected_crs must equal source_crs."""
    poly = Polygon([(0, 0), (1000, 0), (1000, 1000), (0, 1000), (0, 0)])
    file_id = _upload_zip(make_shapefile_zip_bytes(geometries=[poly], crs="EPSG:27700"))
    r = client.get(f"/api/files/{file_id}/measurements/")
    assert r.status_code == 200
    data = r.json()
    assert data["source_crs"] == "EPSG:27700"
    assert data["projected_crs"] == "EPSG:27700"
    m = data["measurements"][0]
    assert abs(m["area_m2"] - 1_000_000) < 1  # 1000m × 1000m = 1,000,000 m²


# ---------------------------------------------------------------------------
# 7. Missing CRS — returns 422 with informative message
# ---------------------------------------------------------------------------

def test_measurements_missing_crs_returns_422():
    """Inject a GDF with no CRS onto a processed record."""
    file_id = _upload_kml(make_kml_bytes())
    gdf_no_crs = gpd.GeoDataFrame({"geometry": [Point(0, 0)]})  # no CRS
    _inject_gdf(file_id, gdf_no_crs)
    r = client.get(f"/api/files/{file_id}/measurements/")
    assert r.status_code == 422
    assert "CRS" in r.json()["detail"]


# ---------------------------------------------------------------------------
# 8. Unsupported geometry — structured result, no crash
# ---------------------------------------------------------------------------

def test_measurements_unsupported_geometry_no_crash():
    """Inject a GeometryCollection — should return null measurements + message."""
    file_id = _upload_kml(make_kml_bytes())
    gc = GeometryCollection([Point(0, 0), LineString([(0, 0), (1, 1)])])
    gdf = gpd.GeoDataFrame({"geometry": [gc]}, crs="EPSG:27700")
    _inject_gdf(file_id, gdf)
    r = client.get(f"/api/files/{file_id}/measurements/")
    assert r.status_code == 200
    m = r.json()["measurements"][0]
    assert m["area_m2"] is None
    assert m["length_m"] is None
    assert "Unsupported" in m["message"]


# ---------------------------------------------------------------------------
# 9. Nonexistent file ID
# ---------------------------------------------------------------------------

def test_measurements_nonexistent_file_id():
    r = client.get("/api/files/99999/measurements/")
    assert r.status_code == 404
    assert "99999" in r.json()["detail"]


# ---------------------------------------------------------------------------
# 10. Processing failure / unavailable GeoDataFrame
# ---------------------------------------------------------------------------

def test_measurements_failed_status_returns_422():
    """Simulate a record that failed processing — geodataframe will be None."""
    file_id = _upload_kml(make_kml_bytes())
    record = store.get(file_id)
    record.status = "failed"
    record.geodataframe = None
    store.update(record)
    r = client.get(f"/api/files/{file_id}/measurements/")
    assert r.status_code == 422
    assert "failed" in r.json()["detail"].lower()


def test_measurements_no_geodataframe_returns_422():
    """Simulate a processed record whose GeoDataFrame was somehow lost."""
    file_id = _upload_kml(make_kml_bytes())
    record = store.get(file_id)
    record.geodataframe = None  # status stays "processed"
    store.update(record)
    r = client.get(f"/api/files/{file_id}/measurements/")
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Response structure completeness
# ---------------------------------------------------------------------------

def test_measurements_response_structure():
    """Verify every required field is present in the response."""
    geoms = [Polygon([(-1, 51), (0, 51), (0, 52), (-1, 52), (-1, 51)])]
    file_id = _upload_zip(make_shapefile_zip_bytes(geometries=geoms))
    r = client.get(f"/api/files/{file_id}/measurements/")
    assert r.status_code == 200
    data = r.json()
    for key in ("file_id", "filename", "source_crs", "projected_crs", "measurements"):
        assert key in data, f"Missing key: {key}"
    m = data["measurements"][0]
    for key in ("feature_id", "geometry_type", "area_m2", "length_m", "message"):
        assert key in m, f"Missing measurement key: {key}"
