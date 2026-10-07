"""
Phase 2 tests — POST /api/files/

Valid uploads now go through real geospatial processing (Phase 3),
so status is "processed" for successful uploads.
"""
import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.fixtures import make_kml_bytes, make_shapefile_zip_bytes, make_corrupted_zip_bytes

client = TestClient(app)


def test_upload_valid_kml():
    response = client.post(
        "/api/files/",
        files={"file": ("sample.kml", make_kml_bytes(), "application/vnd.google-earth.kml+xml")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "sample.kml"
    assert data["status"] == "processed"
    assert "id" in data


def test_upload_valid_zip():
    response = client.post(
        "/api/files/",
        files={"file": ("shapes.zip", make_shapefile_zip_bytes(), "application/zip")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "shapes.zip"
    assert data["status"] == "processed"
    assert "id" in data


def test_upload_unsupported_extension():
    response = client.post(
        "/api/files/",
        files={"file": ("data.geojson", b'{"type":"FeatureCollection"}', "application/json")},
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_upload_empty_file():
    response = client.post(
        "/api/files/",
        files={"file": ("empty.kml", b"", "application/vnd.google-earth.kml+xml")},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_upload_corrupted_zip():
    response = client.post(
        "/api/files/",
        files={"file": ("bad.zip", make_corrupted_zip_bytes(), "application/zip")},
    )
    assert response.status_code == 400
    assert "corrupted" in response.json()["detail"].lower()
