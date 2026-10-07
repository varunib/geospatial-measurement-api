"""
In-memory file metadata store.

Design decision: a plain dict keyed by integer ID is used here so that
the rest of the application never imports a database driver.  The public
interface (save / get / all) is the only contract the routes depend on,
making it straightforward to swap this module for a SQLAlchemy/PostGIS
implementation later without touching any other layer.
"""
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import geopandas as gpd


@dataclass
class FileRecord:
    id: int
    filename: str
    filepath: str
    status: str
    feature_count: Optional[int] = None
    crs: Optional[str] = None
    geodataframe: Optional["gpd.GeoDataFrame"] = None  # held in memory; not serialised


class InMemoryStore:
    def __init__(self) -> None:
        self._records: dict[int, FileRecord] = {}
        self._next_id: int = 1

    def save(self, filename: str, filepath: str, status: str = "uploaded") -> FileRecord:
        record = FileRecord(
            id=self._next_id,
            filename=filename,
            filepath=filepath,
            status=status,
        )
        self._records[self._next_id] = record
        self._next_id += 1
        return record

    def get(self, file_id: int) -> Optional[FileRecord]:
        return self._records.get(file_id)

    def update(self, record: FileRecord) -> None:
        self._records[record.id] = record

    def all(self) -> list[FileRecord]:
        return list(self._records.values())


# Module-level singleton — one store for the lifetime of the process.
store = InMemoryStore()
