from pydantic import BaseModel


class FileUploadResponse(BaseModel):
    id: int
    filename: str
    feature_count: int | None = None
    crs: str | None = None
    status: str

    model_config = {"from_attributes": True}


class MeasurementResult(BaseModel):
    """Measurement for a single feature."""

    feature_id: int
    geometry_type: str
    area_m2: float | None = None
    length_m: float | None = None
    message: str | None = None


class MeasurementsResponse(BaseModel):
    """Full measurement response for a processed file."""

    file_id: int
    filename: str
    source_crs: str | None       # Original CRS stored on the file record
    projected_crs: str           # CRS actually used for measurement (always metric)
    measurements: list[MeasurementResult]
