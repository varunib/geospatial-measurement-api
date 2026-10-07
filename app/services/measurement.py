"""
Measurement service.

Calculates per-feature metric measurements from a GeoDataFrame.

Supported geometry types and their measurements:
  Polygon        → area_m2  (square metres)
  LineString     → length_m (metres)
  Point          → no measurement (null), informational message returned
  MultiPolygon   → area_m2  (treated as an extended supported type; sum of all parts)
  MultiLineString→ length_m (treated as an extended supported type; sum of all parts)

Unsupported types (e.g. GeometryCollection) → null measurement + message.

All measurements are performed on a projected GeoDataFrame supplied by the
caller (via crs_handler.get_projected_gdf). This module never reprojects data
itself — separation of concerns is intentional.

Units:
  area   → square metres (m²)
  length → metres (m)

Values are returned as raw floats; rounding is the responsibility of the
serialisation layer (Pydantic response model).
"""
from typing import Optional

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

from app.models.schemas import MeasurementResult

# Geometry types that produce an area measurement.
_AREA_TYPES = {"Polygon", "MultiPolygon"}
# Geometry types that produce a length measurement.
_LENGTH_TYPES = {"LineString", "MultiLineString"}
# Geometry types that are valid but have no applicable measurement.
_NO_MEASURE_TYPES = {"Point", "MultiPoint"}


def compute_measurements(projected_gdf: gpd.GeoDataFrame) -> list[MeasurementResult]:
    """
    Return one MeasurementResult per feature row in the projected GeoDataFrame.

    The GeoDataFrame MUST already be in a projected (metric) CRS.
    """
    results: list[MeasurementResult] = []

    for feature_id, row in projected_gdf.iterrows():
        result = _measure_feature(int(feature_id), row.geometry)
        results.append(result)

    return results


def _measure_feature(feature_id: int, geom: Optional[BaseGeometry]) -> MeasurementResult:
    """Produce a MeasurementResult for a single geometry, handling all edge cases."""

    # --- Null geometry ---
    if geom is None:
        return MeasurementResult(
            feature_id=feature_id,
            geometry_type="Unknown",
            message="Null geometry — no measurement possible.",
        )

    geom_type = geom.geom_type  # e.g. "Polygon", "LineString", "Point"

    # --- Empty geometry ---
    if geom.is_empty:
        return MeasurementResult(
            feature_id=feature_id,
            geometry_type=geom_type,
            message="Empty geometry — no measurement possible.",
        )

    # --- Invalid geometry (self-intersecting etc.) ---
    # We do not crash; we attempt measurement anyway and note invalidity.
    # Shapely's .area / .length still return a value for invalid geometries.
    invalid_note = "" if geom.is_valid else " (geometry is invalid; result may be approximate)"

    # --- Area types ---
    if geom_type in _AREA_TYPES:
        return MeasurementResult(
            feature_id=feature_id,
            geometry_type=geom_type,
            area_m2=geom.area,
            message=f"Area calculated in m²{invalid_note}" if invalid_note else None,
        )

    # --- Length types ---
    if geom_type in _LENGTH_TYPES:
        return MeasurementResult(
            feature_id=feature_id,
            geometry_type=geom_type,
            length_m=geom.length,
            message=f"Length calculated in metres{invalid_note}" if invalid_note else None,
        )

    # --- Point types — valid but no measurement ---
    if geom_type in _NO_MEASURE_TYPES:
        return MeasurementResult(
            feature_id=feature_id,
            geometry_type=geom_type,
            message=f"No measurement applicable for {geom_type}.",
        )

    # --- Truly unsupported (GeometryCollection, etc.) ---
    return MeasurementResult(
        feature_id=feature_id,
        geometry_type=geom_type,
        message=f"Unsupported geometry type: {geom_type}.",
    )
