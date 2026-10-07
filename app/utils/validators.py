import zipfile
from fastapi import UploadFile, HTTPException

ALLOWED_EXTENSIONS = {".kml", ".zip"}


def validate_file_extension(filename: str) -> str:
    """Return the lowercased extension or raise 400."""
    if not filename:
        raise HTTPException(status_code=400, detail="No filename provided.")
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: .kml, .zip",
        )
    return ext


def validate_zip_integrity(data: bytes) -> None:
    """Raise 400 if the bytes do not form a valid ZIP archive."""
    if not zipfile.is_zipfile(__import__("io").BytesIO(data)):
        raise HTTPException(status_code=400, detail="Uploaded ZIP file is corrupted or invalid.")
