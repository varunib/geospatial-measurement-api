"""
CRS handler service.

Strategy
--------
Measurements (area, length) require metric units. Calculating them directly
from geographic coordinates (degrees, e.g. EPSG:4326) produces meaningless
results. This module ensures every GeoDataFrame is in a suitable projected
CRS before measurements are taken.

Decision tree:
1. No CRS → raise ValueError. We never guess a CRS; the caller must handle
   this and surface a clear error to the API user.
2. CRS is already projected (linear units = metres or feet) → use it as-is.
   We trust that the data provider chose an appropriate projection.
3. CRS is geographic (angular units = degrees, e.g. EPSG:4326) → select the
   best-fit UTM zone automatically using PyProj's query_utm_crs_info(), which
   queries the PROJ database for the UTM CRS whose area-of-use best covers the
   dataset's bounding box. This handles both hemispheres correctly without any
   manual zone arithmetic.

Why UTM?
- UTM zones are 6° wide and preserve area/length well within each zone.
- PyProj's query_utm_crs_info() picks the zone whose area-of-use best
  overlaps the dataset extent, so datasets that span a zone boundary get the
  most representative zone.
- For datasets that span many UTM zones (e.g. continental scale) this is still
  a reasonable approximation; a truly global dataset would need an equal-area
  projection (e.g. Mollweide), but that is outside the scope of this assignment.
"""
from typing import Optional

import geopandas as gpd
from pyproj import CRS
from pyproj.aoi import AreaOfInterest
from pyproj.database import query_utm_crs_info


class MissingCRSError(ValueError):
    """Raised when a GeoDataFrame has no CRS and metric measurement is requested."""


def get_projected_gdf(gdf: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, str]:
    """
    Return (reprojected_gdf, epsg_string) ready for metric measurement.

    Raises MissingCRSError if the GeoDataFrame has no CRS.
    """
    if gdf.crs is None:
        raise MissingCRSError(
            "The file has no CRS (coordinate reference system). "
            "Metric measurements cannot be calculated without knowing the CRS. "
            "Please provide a file that includes CRS information (e.g. a .prj sidecar file)."
        )

    if gdf.crs.is_projected:
        return gdf, _crs_to_string(gdf.crs)

    # Geographic CRS → find the best UTM zone for this dataset.
    target_crs = _select_utm_crs(gdf)
    reprojected = gdf.to_crs(target_crs)
    return reprojected, _crs_to_string(target_crs)


def _select_utm_crs(gdf: gpd.GeoDataFrame) -> CRS:
    """
    Choose the UTM CRS whose area-of-use best covers the dataset's bounding box.

    Uses PyProj's query_utm_crs_info() which queries the PROJ authority database
    and returns results ordered by how well they cover the requested area of interest.
    The first result is always the best match.
    """
    bounds = gdf.total_bounds  # [minx, miny, maxx, maxy] in source CRS degrees
    aoi = AreaOfInterest(
        west_lon_degree=float(bounds[0]),
        south_lat_degree=float(bounds[1]),
        east_lon_degree=float(bounds[2]),
        north_lat_degree=float(bounds[3]),
    )

    utm_crs_list = query_utm_crs_info(datum_name="WGS 84", area_of_interest=aoi)

    if not utm_crs_list:
        # Extremely rare fallback — dataset at poles or invalid bounds.
        # EPSG:3857 (Web Mercator) is a last resort; it distorts area at high
        # latitudes but will not crash the application.
        return CRS.from_epsg(3857)

    best = utm_crs_list[0]
    return CRS.from_authority(best.auth_name, best.code)


def _crs_to_string(crs: CRS) -> str:
    """Serialise a CRS to 'EPSG:XXXX' where possible, otherwise WKT name."""
    epsg = crs.to_epsg()
    return f"EPSG:{epsg}" if epsg else crs.name
