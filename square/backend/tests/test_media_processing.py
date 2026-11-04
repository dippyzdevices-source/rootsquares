"""Tests for media processing (9 tests), e.g. process upload extracts dimensions and generates a thumbnail; process upload rejects a file over the size limit; process upload rejects a non image file."""
from io import BytesIO

import pytest
from PIL import Image

from app.gallery.media_processing import MediaValidationError, process_upload


class FakeFileStorage:
    """Minimal stand-in for werkzeug's FileStorage — just what process_upload needs."""

    def __init__(self, data: bytes, filename: str = "photo.jpg"):
        self._data = data
        self.filename = filename

    def read(self) -> bytes:
        return self._data


def _jpeg_bytes(width=800, height=600) -> bytes:
    image = Image.new("RGB", (width, height), color="red")
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def test_process_upload_extracts_dimensions_and_generates_a_thumbnail():
    result = process_upload(FakeFileStorage(_jpeg_bytes(800, 600)))

    assert result.width == 800
    assert result.height == 600
    assert result.original_content_type == "image/webp"
    assert Image.open(BytesIO(result.original_bytes)).format == "WEBP"

    thumb = Image.open(BytesIO(result.thumbnail_bytes))
    assert thumb.format == "JPEG"
    assert max(thumb.size) <= 400


def test_process_upload_rejects_a_file_over_the_size_limit():
    oversized = b"0" * (10 * 1024 * 1024 + 1)

    with pytest.raises(MediaValidationError, match="10MB"):
        process_upload(FakeFileStorage(oversized))


def test_process_upload_rejects_a_non_image_file():
    with pytest.raises(MediaValidationError, match="valid image"):
        process_upload(FakeFileStorage(b"this is not an image", filename="fake.jpg"))


def test_process_upload_rejects_an_unsupported_format():
    image = Image.new("RGB", (10, 10), color="blue")
    buffer = BytesIO()
    image.save(buffer, format="BMP")

    with pytest.raises(MediaValidationError, match="Unsupported"):
        process_upload(FakeFileStorage(buffer.getvalue(), filename="photo.bmp"))


def test_process_upload_shrinks_a_large_noisy_photo_under_700kb():
    import os

    noisy = Image.frombytes("RGB", (3000, 2000), os.urandom(3000 * 2000 * 3))
    buffer = BytesIO()
    noisy.save(buffer, format="JPEG", quality=95)

    result = process_upload(FakeFileStorage(buffer.getvalue()))

    assert len(result.original_bytes) <= 700 * 1024
    assert max(result.width, result.height) <= 2000


def test_process_upload_converts_an_iphone_heic_photo_to_webp():
    from pillow_heif import register_heif_opener

    register_heif_opener()
    buffer = BytesIO()
    Image.new("RGB", (640, 480), color="green").save(buffer, format="HEIF")

    result = process_upload(FakeFileStorage(buffer.getvalue(), filename="IMG_0001.HEIC"))

    assert result.original_content_type == "image/webp"
    assert Image.open(BytesIO(result.original_bytes)).format == "WEBP"
    assert (result.width, result.height) == (640, 480)


def test_process_upload_accepts_a_phone_mpo_photo_and_converts_it_to_webp():
    buffer = BytesIO()
    first = Image.new("RGB", (640, 480), color="orange")
    # A real MPO has more than one embedded frame; a single-frame save reads back as plain JPEG.
    first.save(buffer, format="MPO", save_all=True, append_images=[Image.new("RGB", (64, 48), "red")])
    assert Image.open(BytesIO(buffer.getvalue())).format == "MPO"

    result = process_upload(FakeFileStorage(buffer.getvalue(), filename="IMG_0002.JPG"))

    assert result.original_content_type == "image/webp"
    assert Image.open(BytesIO(result.original_bytes)).format == "WEBP"
    assert (result.width, result.height) == (640, 480)


def test_process_upload_rejects_absurd_dimensions_before_decoding(monkeypatch):
    from app.gallery import media_processing

    monkeypatch.setattr(media_processing, "MAX_PIXELS", 1000)

    with pytest.raises(MediaValidationError, match="dimensions"):
        process_upload(FakeFileStorage(_jpeg_bytes(100, 100)))


def test_process_upload_downsizes_a_large_photo_and_respects_exif_rotation():
    image = Image.new("RGB", (4000, 3000), color="blue")
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90° clockwise when displayed -> portrait
    buffer = BytesIO()
    image.save(buffer, format="JPEG", exif=exif)

    result = process_upload(FakeFileStorage(buffer.getvalue()))

    assert max(result.width, result.height) <= 2000
    assert result.height > result.width
