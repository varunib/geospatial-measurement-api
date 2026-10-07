from pathlib import Path

from fastapi import UploadFile, HTTPException

from app.core.config import settings
from app.storage.store import store, FileRecord
from app.utils.validators import validate_file_extension, validate_zip_integrity
from app.services.file_processor import process_kml, process_zip_shapefile


async def handle_upload(file: UploadFile) -> FileRecord:
    """Validate, persist, process, and register an uploaded geospatial file."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file was uploaded.")

    ext = validate_file_extension(file.filename)

    data = await file.read()
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if ext == ".zip":
        validate_zip_integrity(data)

    # Reserve a record first so we have the ID for the unique filename.
    record = store.save(filename=file.filename, filepath="", status="uploaded")

    # Store as "{id}_{original_filename}" to prevent collisions.
    safe_name = f"{record.id}_{file.filename}"
    dest: Path = settings.upload_dir / safe_name
    dest.write_bytes(data)
    record.filepath = str(dest)

    # --- Geospatial processing ---
    try:
        if ext == ".kml":
            gdf, meta = process_kml(str(dest))
        else:
            gdf, meta = process_zip_shapefile(str(dest))

        record.geodataframe = gdf
        record.feature_count = meta["feature_count"]
        record.crs = meta["crs"]
        record.status = "processed"
    except HTTPException:
        record.status = "failed"
        store.update(record)
        raise
    except Exception as exc:
        record.status = "failed"
        store.update(record)
        raise HTTPException(status_code=500, detail=f"Unexpected processing error: {exc}")

    store.update(record)
    return record
