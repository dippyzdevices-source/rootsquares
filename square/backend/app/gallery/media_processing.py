from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

# Lets Pillow open iPhone HEIC/HEIF photos; they are converted to WebP like everything else.
register_heif_opener()

MAX_FILE_SIZE = 10 * 1024 * 1024
# "image/mpo" is Pillow's name for Multi-Picture-Object files — a JPEG with extra embedded
# frames that many phones (iPhones, Samsung) write for some photos. Pillow decodes the first
# frame as a normal JPEG, so it's accepted and converted to WebP like any other photo.
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heif", "image/heic", "image/mpo"}
THUMBNAIL_SIZE = (400, 400)
# Stored originals are re-encoded to WebP so every upload stays small (REQ-002).
MAX_STORED_BYTES = 700 * 1024
MAX_LONG_EDGE = 2000
# Reject absurd dimensions before decoding (a 48MP iPhone Pro photo is ~48M pixels).
MAX_PIXELS = 60_000_000
# Tried in order until the encoded image fits MAX_STORED_BYTES: (long edge, WebP quality).
_COMPRESSION_STEPS = [(MAX_LONG_EDGE, 80), (MAX_LONG_EDGE, 70), (1600, 65), (1400, 55), (1200, 50)]


class MediaValidationError(Exception):
    pass


@dataclass
class ProcessedImage:
    width: int
    height: int
    original_bytes: bytes
    original_content_type: str
    thumbnail_bytes: bytes


def load_reduced(data: bytes) -> tuple[Image.Image, str]:
    """Decode an upload with as little memory as possible and return it already EXIF-rotated,
    RGB/RGBA and no larger than MAX_LONG_EDGE, plus its MIME type.

    Memory matters here: the host has 512MB shared by several workers, and a raw 12-48MP phone
    photo decodes to 36-145MB. So the format/size are checked before any pixels are decoded, JPEG
    is decoded at reduced scale (`draft`), and every later step works on the shrunken image."""
    try:
        image = Image.open(BytesIO(data))
    except Exception as exc:
        raise MediaValidationError("Not a valid image file.") from exc

    content_type = Image.MIME.get(image.format or "")
    if content_type not in ALLOWED_MIME_TYPES:
        raise MediaValidationError(f"Unsupported image format: {image.format}")
    if image.width * image.height > MAX_PIXELS:
        raise MediaValidationError("Image dimensions are too large.")

    try:
        image.draft("RGB", (MAX_LONG_EDGE, MAX_LONG_EDGE))  # JPEG/MPO only; no-op otherwise
        image.load()
    except Exception as exc:
        raise MediaValidationError("Not a valid image file.") from exc

    ImageOps.exif_transpose(image, in_place=True)
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA" if "transparency" in image.info or image.mode in ("LA", "PA") else "RGB")
    image.thumbnail((MAX_LONG_EDGE, MAX_LONG_EDGE))
    return image, content_type


def compress_to_webp(image: Image.Image) -> tuple[bytes, tuple[int, int]]:
    """Re-encode an already-reduced image (see `load_reduced`) as WebP, stepping size/quality
    down until it fits MAX_STORED_BYTES. Returns (bytes, (width, height)); raises
    MediaValidationError if even the smallest step is too big."""
    for long_edge, quality in _COMPRESSION_STEPS:
        if max(image.size) > long_edge:
            candidate = image.copy()
            candidate.thumbnail((long_edge, long_edge))
        else:
            candidate = image
        buffer = BytesIO()
        candidate.save(buffer, format="WEBP", quality=quality, method=4)
        if buffer.tell() <= MAX_STORED_BYTES:
            return buffer.getvalue(), candidate.size
    raise MediaValidationError("Image is too large even after compression. Try a smaller image.")


def process_upload(file_storage) -> ProcessedImage:
    data = file_storage.read()
    if len(data) > MAX_FILE_SIZE:
        raise MediaValidationError("File exceeds the 10MB size limit.")

    image, _ = load_reduced(data)
    del data

    stored_bytes, (width, height) = compress_to_webp(image)

    thumbnail = image.convert("RGB")
    thumbnail.thumbnail(THUMBNAIL_SIZE)
    thumbnail_buffer = BytesIO()
    thumbnail.save(thumbnail_buffer, format="JPEG", quality=80)

    return ProcessedImage(
        width=width,
        height=height,
        original_bytes=stored_bytes,
        original_content_type="image/webp",
        thumbnail_bytes=thumbnail_buffer.getvalue(),
    )
