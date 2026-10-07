"""
Measurement orchestration service.

Sits between the route and the Phase 4 engines.
Responsibilities:
  - Retrieve the FileRecord from the store.
  - Validate that the record is in a processable state.
  - Delegate CRS handling to crs_handler.get_projected_gdf().
  - Delegate per-feature calculation to measurement.compute_measurements().
  - Return a MeasurementsResponse ready for serialisation.

No geospatial logic lives here — this layer only orchestrates.
"""
from fastapi import HTTPException

from app.models.schemas import MeasurementsResponse
from app.services.crs_handler import MissingCRSError, get_projected_gdf
from app.services.measurement import compute_measurements
from app.storage.store import store


def get_measurements_for_file(file_id: int) -> MeasurementsResponse:
    record = store.get(file_id)

    if record is None:
        raise HTTPException(status_code=404, detail=f"File with id {file_id} not found.")

    if record.status == "failed":
        raise HTTPException(
            status_code=422,
            detail=f"File {file_id} failed during processing and cannot be measured.",
        )

    if record.status != "processed" or record.geodataframe is None:
        raise HTTPException(
            status_code=422,
            detail=f"File {file_id} has not been successfully processed yet (status: '{record.status}').",
        )

    try:
        projected_gdf, projected_crs = get_projected_gdf(record.geodataframe)
    except MissingCRSError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    measurements = compute_measurements(projected_gdf)

    return MeasurementsResponse(
        file_id=record.id,
        filename=record.filename,
        source_crs=record.crs,
        projected_crs=projected_crs,
        measurements=measurements,
    )
