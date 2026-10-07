from fastapi import APIRouter, HTTPException, UploadFile, File, status

from app.models.schemas import FileUploadResponse, MeasurementsResponse
from app.services.file_service import handle_upload
from app.services.measurement_service import get_measurements_for_file
from app.storage.store import store

router = APIRouter()


@router.post(
    "/",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a geospatial file",
    description=(
        "Upload a **.kml** or **.zip** (ESRI Shapefile) file. "
        "The file is validated, stored, and processed immediately. "
        "Returns file metadata including feature count and source CRS."
    ),
)
async def upload_file(file: UploadFile = File(..., description="A .kml or .zip file")):
    record = await handle_upload(file)
    return FileUploadResponse(
        id=record.id,
        filename=record.filename,
        feature_count=record.feature_count,
        crs=record.crs,
        status=record.status,
    )


@router.get(
    "/{file_id}/",
    response_model=FileUploadResponse,
    summary="Get file information",
    description="Retrieve metadata for a previously uploaded file by its ID.",
)
def get_file(file_id: int):
    record = store.get(file_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"File with id {file_id} not found.")
    return FileUploadResponse(
        id=record.id,
        filename=record.filename,
        feature_count=record.feature_count,
        crs=record.crs,
        status=record.status,
    )


@router.get(
    "/{file_id}/measurements/",
    response_model=MeasurementsResponse,
    summary="Get measurements for a file",
    description=(
        "Calculate and return per-feature measurements for a processed file.\n\n"
        "- **Polygon** → `area_m2` in square metres\n"
        "- **LineString** → `length_m` in metres\n"
        "- **Point** → no measurement (`null`)\n\n"
        "Geographic CRS (e.g. EPSG:4326) is automatically reprojected to the "
        "appropriate UTM zone before measurement. The `projected_crs` field in "
        "the response shows which CRS was used for calculation."
    ),
)
def get_measurements(file_id: int):
    return get_measurements_for_file(file_id)
