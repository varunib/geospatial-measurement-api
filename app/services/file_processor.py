"""
Geospatial file processor.

Responsibilities:
- Read KML files via GeoPandas/Fiona (KML driver enabled explicitly).
- Safely extract ZIP Shapefiles and validate required components.
- Return a GeoDataFrame and extracted metadata dict.

This module has no knowledge of HTTP, storage, or the upload workflow.
"""
import io
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

import fiona
import fiona.drvsupport
import geopandas as gpd
from fastapi import HTTPException

# Fiona's KML driver is not enabled by default — activate it once at import time.
fiona.drvsupport.supported_drivers["KML"] = "rw"
fiona.drvsupport.supported_drivers["LIBKML"] = "rw"

# Minimum Shapefile sidecar files required for a usable dataset.
REQUIRED_SHP_EXTENSIONS = {".shp", ".shx", ".dbf"}


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def process_kml(filepath: str) -> tuple[gpd.GeoDataFrame, dict]:
    """Read a KML file and return (GeoDataFrame, metadata)."""
    try:
        gdf = gpd.read_file(filepath, driver="KML")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse KML file: {exc}")

    if gdf is None or gdf.empty:
        raise HTTPException(status_code=400, detail="KML file contains no readable features.")

    return gdf, _extract_metadata(gdf)


def process_zip_shapefile(filepath: str) -> tuple[gpd.GeoDataFrame, dict]:
    """
    Safely extract a ZIP archive, locate the Shapefile, validate required
    components, read it, and return (GeoDataFrame, metadata).
    """
    data = Path(filepath).read_bytes()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        _safe_extract_zip(data, tmp_path)

        shp_files = list(tmp_path.rglob("*.shp"))
        if not shp_files:
            raise HTTPException(
                status_code=400,
                detail="ZIP archive does not contain a Shapefile (.shp).",
            )
        if len(shp_files) > 1:
            raise HTTPException(
                status_code=400,
                detail="ZIP archive contains multiple .shp files. Please include only one.",
            )

        shp_path = shp_files[0]
        _validate_shapefile_components(shp_path)

        try:
            gdf = gpd.read_file(shp_path)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to read Shapefile: {exc}")

        if gdf is None or gdf.empty:
            raise HTTPException(status_code=400, detail="Shapefile contains no readable features.")

        return gdf, _extract_metadata(gdf)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_extract_zip(data: bytes, dest: Path) -> None:
    """Extract ZIP bytes to dest, rejecting any path-traversal entries (Zip Slip)."""
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for member in zf.infolist():
            member_path = (dest / member.filename).resolve()
            if not str(member_path).startswith(str(dest.resolve())):
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsafe path in ZIP archive: {member.filename}",
                )
            zf.extract(member, dest)


def _validate_shapefile_components(shp_path: Path) -> None:
    """Raise 400 if .shx or .dbf are missing alongside the .shp."""
    stem = shp_path.stem
    parent = shp_path.parent
    missing = [
        ext for ext in REQUIRED_SHP_EXTENSIONS
        if not (parent / f"{stem}{ext}").exists()
    ]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Shapefile is missing required components: {', '.join(missing)}",
        )


def _extract_metadata(gdf: gpd.GeoDataFrame) -> dict:
    """Pull feature count and CRS string from a GeoDataFrame."""
    crs_str: Optional[str] = None
    if gdf.crs is not None:
        try:
            crs_str = gdf.crs.to_epsg()
            crs_str = f"EPSG:{crs_str}" if crs_str else gdf.crs.to_string()
        except Exception:
            crs_str = str(gdf.crs)

    return {
        "feature_count": len(gdf),
        "crs": crs_str,
    }
