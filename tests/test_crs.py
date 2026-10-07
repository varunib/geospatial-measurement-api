"""
Phase 4 tests — CRS handler.

Verifies:
- Geographic CRS (EPSG:4326) triggers UTM reprojection
- Projected CRS passes through unchanged
- Missing CRS raises MissingCRSError
- Northern hemisphere UTM zone selection
- Southern hemisphere UTM zone selection
- Reprojected GDF has metric (projected) CRS
"""
import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point, Polygon

from app.services.crs_handler import MissingCRSError, get_projected_gdf


def _gdf(geom, crs):
    return gpd.GeoDataFrame({"geometry": [geom]}, crs=crs)


def _gdf_no_crs(geom):
    return gpd.GeoDataFrame({"geometry": [geom]})


# ---------------------------------------------------------------------------
# 1. Geographic CRS triggers reprojection
# ---------------------------------------------------------------------------

def test_geographic_crs_is_reprojected():
    gdf = _gdf(Point(-0.1, 51.5), "EPSG:4326")
    projected, crs_str = get_projected_gdf(gdf)
    assert projected.crs.is_projected
    assert projected.crs != gdf.crs


def test_geographic_crs_result_is_metric():
    """After reprojection the CRS units must be metres, not degrees."""
    gdf = _gdf(Point(-0.1, 51.5), "EPSG:4326")
    projected, _ = get_projected_gdf(gdf)
    assert projected.crs.axis_info[0].unit_name in ("metre", "meter")


# ---------------------------------------------------------------------------
# 2. Projected CRS passes through unchanged
# ---------------------------------------------------------------------------

def test_projected_crs_passes_through():
    """EPSG:27700 (British National Grid) is already projected — no change."""
    gdf = _gdf(Point(530000, 180000), "EPSG:27700")
    projected, crs_str = get_projected_gdf(gdf)
    assert projected.crs == gdf.crs
    assert crs_str == "EPSG:27700"


def test_projected_crs_utm_passes_through():
    gdf = _gdf(Point(500000, 5700000), "EPSG:32632")  # UTM zone 32N
    projected, crs_str = get_projected_gdf(gdf)
    assert projected.crs.is_projected
    assert "32632" in crs_str


# ---------------------------------------------------------------------------
# 3. Missing CRS raises MissingCRSError
# ---------------------------------------------------------------------------

def test_missing_crs_raises_error():
    gdf = _gdf_no_crs(Point(0, 0))
    with pytest.raises(MissingCRSError):
        get_projected_gdf(gdf)


def test_missing_crs_error_message_is_informative():
    gdf = _gdf_no_crs(Point(0, 0))
    with pytest.raises(MissingCRSError, match="CRS"):
        get_projected_gdf(gdf)


# ---------------------------------------------------------------------------
# 4. Northern hemisphere UTM selection
# ---------------------------------------------------------------------------

def test_northern_hemisphere_utm_selected():
    """London (51.5°N) should map to a UTM North zone (EPSG:326xx)."""
    gdf = _gdf(Point(-0.1, 51.5), "EPSG:4326")
    projected, crs_str = get_projected_gdf(gdf)
    epsg_code = int(crs_str.split(":")[1])
    # UTM North zones: 32601–32660
    assert 32601 <= epsg_code <= 32660, f"Expected UTM North, got {crs_str}"


# ---------------------------------------------------------------------------
# 5. Southern hemisphere UTM selection
# ---------------------------------------------------------------------------

def test_southern_hemisphere_utm_selected():
    """Sydney (33.9°S) should map to a UTM South zone (EPSG:327xx)."""
    gdf = _gdf(Point(151.2, -33.9), "EPSG:4326")
    projected, crs_str = get_projected_gdf(gdf)
    epsg_code = int(crs_str.split(":")[1])
    # UTM South zones: 32701–32760
    assert 32701 <= epsg_code <= 32760, f"Expected UTM South, got {crs_str}"


# ---------------------------------------------------------------------------
# 6. Correct UTM zone for known locations
# ---------------------------------------------------------------------------

def test_london_maps_to_utm_zone_30():
    """London is in UTM zone 30N → EPSG:32630."""
    gdf = _gdf(Point(-0.1, 51.5), "EPSG:4326")
    _, crs_str = get_projected_gdf(gdf)
    assert crs_str == "EPSG:32630"


def test_new_york_maps_to_utm_zone_18():
    """New York City is in UTM zone 18N → EPSG:32618."""
    gdf = _gdf(Point(-74.0, 40.7), "EPSG:4326")
    _, crs_str = get_projected_gdf(gdf)
    assert crs_str == "EPSG:32618"


def test_sydney_maps_to_utm_zone_56():
    """Sydney is in UTM zone 56S → EPSG:32756."""
    gdf = _gdf(Point(151.2, -33.9), "EPSG:4326")
    _, crs_str = get_projected_gdf(gdf)
    assert crs_str == "EPSG:32756"
