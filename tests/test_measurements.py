"""
Phase 4 tests — measurement engine.

Verifies:
- Polygon area in m² (geographic input → UTM reprojection → correct area)
- LineString length in m
- Point returns null measurement
- Projected CRS input used directly
- Missing CRS handled safely
- Unsupported geometry type
- Empty geometry
- Null geometry
- MultiPolygon and MultiLineString (extended support)
- Measurements are NOT in degrees (sanity check)
"""
import geopandas as gpd
import pytest
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPolygon,
    Point,
    Polygon,
)

from app.services.crs_handler import MissingCRSError, get_projected_gdf
from app.services.measurement import compute_measurements


def _measure(geometries: list, crs: str | None = "EPSG:4326") -> list:
    """Helper: build GDF, reproject if needed, compute measurements."""
    gdf = gpd.GeoDataFrame({"geometry": geometries}, crs=crs)
    projected, _ = get_projected_gdf(gdf)
    return compute_measurements(projected)


# ---------------------------------------------------------------------------
# 1. Polygon area — geographic input (EPSG:4326)
# ---------------------------------------------------------------------------

def test_polygon_area_is_returned():
    poly = Polygon([(-1, 51), (0, 51), (0, 52), (-1, 52), (-1, 51)])
    results = _measure([poly])
    assert results[0].area_m2 is not None
    assert results[0].length_m is None


def test_polygon_area_is_in_square_metres_not_degrees():
    """
    A 1-degree square near London is ~7,700 km².
    In raw degrees it would be 1.0 — so any value > 1000 confirms metric units.
    """
    poly = Polygon([(-1, 51), (0, 51), (0, 52), (-1, 52), (-1, 51)])
    results = _measure([poly])
    area = results[0].area_m2
    assert area > 1_000_000, f"Area suspiciously small ({area}), likely in degrees not metres"


def test_polygon_area_approximate_value():
    """1-degree square near London should be roughly 6–8 billion m² (6,000–8,000 km²)."""
    poly = Polygon([(-1, 51), (0, 51), (0, 52), (-1, 52), (-1, 51)])
    results = _measure([poly])
    area = results[0].area_m2
    assert 6e9 < area < 8e9, f"Unexpected area: {area}"


def test_polygon_geometry_type_label():
    poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
    results = _measure([poly])
    assert results[0].geometry_type == "Polygon"


# ---------------------------------------------------------------------------
# 2. LineString length — geographic input (EPSG:4326)
# ---------------------------------------------------------------------------

def test_linestring_length_is_returned():
    line = LineString([(0, 51), (1, 51)])
    results = _measure([line])
    assert results[0].length_m is not None
    assert results[0].area_m2 is None


def test_linestring_length_is_in_metres_not_degrees():
    """
    A 1-degree horizontal line at 51°N is ~70 km.
    In raw degrees it would be 1.0 — any value > 1000 confirms metric units.
    """
    line = LineString([(0, 51), (1, 51)])
    results = _measure([line])
    length = results[0].length_m
    assert length > 1000, f"Length suspiciously small ({length}), likely in degrees not metres"


def test_linestring_length_approximate_value():
    """1-degree horizontal line at 51°N ≈ 69–72 km."""
    line = LineString([(0, 51), (1, 51)])
    results = _measure([line])
    length = results[0].length_m
    assert 65_000 < length < 75_000, f"Unexpected length: {length}"


# ---------------------------------------------------------------------------
# 3. Point — no measurement
# ---------------------------------------------------------------------------

def test_point_returns_null_measurements():
    results = _measure([Point(0, 51)])
    assert results[0].area_m2 is None
    assert results[0].length_m is None


def test_point_has_informative_message():
    results = _measure([Point(0, 51)])
    assert results[0].message is not None
    assert "Point" in results[0].message


# ---------------------------------------------------------------------------
# 4. Already-projected CRS — used directly, no re-reprojection
# ---------------------------------------------------------------------------

def test_polygon_projected_crs_area():
    """A 100m × 100m square in EPSG:27700 should have area = 10,000 m²."""
    poly = Polygon([(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)])
    gdf = gpd.GeoDataFrame({"geometry": [poly]}, crs="EPSG:27700")
    projected, crs_str = get_projected_gdf(gdf)
    results = compute_measurements(projected)
    assert abs(results[0].area_m2 - 10_000) < 0.01


def test_linestring_projected_crs_length():
    """A 500m line in EPSG:27700 should have length = 500 m."""
    line = LineString([(0, 0), (500, 0)])
    gdf = gpd.GeoDataFrame({"geometry": [line]}, crs="EPSG:27700")
    projected, _ = get_projected_gdf(gdf)
    results = compute_measurements(projected)
    assert abs(results[0].length_m - 500) < 0.01


# ---------------------------------------------------------------------------
# 5. Missing CRS — safe error, no crash
# ---------------------------------------------------------------------------

def test_missing_crs_raises_before_measurement():
    gdf = gpd.GeoDataFrame({"geometry": [Point(0, 0)]})
    with pytest.raises(MissingCRSError):
        get_projected_gdf(gdf)


# ---------------------------------------------------------------------------
# 6. Unsupported geometry type
# ---------------------------------------------------------------------------

def test_unsupported_geometry_returns_null_with_message():
    gc = GeometryCollection([Point(0, 0), LineString([(0, 0), (1, 1)])])
    gdf = gpd.GeoDataFrame({"geometry": [gc]}, crs="EPSG:27700")
    results = compute_measurements(gdf)
    assert results[0].area_m2 is None
    assert results[0].length_m is None
    assert "Unsupported" in results[0].message


# ---------------------------------------------------------------------------
# 7. Empty geometry
# ---------------------------------------------------------------------------

def test_empty_polygon_returns_message():
    empty = Polygon()
    gdf = gpd.GeoDataFrame({"geometry": [empty]}, crs="EPSG:27700")
    results = compute_measurements(gdf)
    assert results[0].area_m2 is None
    assert "Empty" in results[0].message


def test_empty_linestring_returns_message():
    empty = LineString()
    gdf = gpd.GeoDataFrame({"geometry": [empty]}, crs="EPSG:27700")
    results = compute_measurements(gdf)
    assert results[0].length_m is None
    assert "Empty" in results[0].message


# ---------------------------------------------------------------------------
# 8. Null geometry
# ---------------------------------------------------------------------------

def test_null_geometry_returns_message():
    gdf = gpd.GeoDataFrame({"geometry": [None]}, crs="EPSG:27700")
    results = compute_measurements(gdf)
    assert results[0].area_m2 is None
    assert results[0].length_m is None
    assert results[0].message is not None


# ---------------------------------------------------------------------------
# 9. MultiPolygon (extended support)
# ---------------------------------------------------------------------------

def test_multipolygon_area_is_returned():
    p1 = Polygon([(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)])
    p2 = Polygon([(200, 0), (300, 0), (300, 100), (200, 100), (200, 0)])
    mp = MultiPolygon([p1, p2])
    gdf = gpd.GeoDataFrame({"geometry": [mp]}, crs="EPSG:27700")
    results = compute_measurements(gdf)
    assert results[0].area_m2 is not None
    assert abs(results[0].area_m2 - 20_000) < 0.01  # two 100×100 squares


# ---------------------------------------------------------------------------
# 10. MultiLineString (extended support)
# ---------------------------------------------------------------------------

def test_multilinestring_length_is_returned():
    ml = MultiLineString([[(0, 0), (500, 0)], [(1000, 0), (1500, 0)]])
    gdf = gpd.GeoDataFrame({"geometry": [ml]}, crs="EPSG:27700")
    results = compute_measurements(gdf)
    assert results[0].length_m is not None
    assert abs(results[0].length_m - 1000) < 0.01  # two 500m segments
