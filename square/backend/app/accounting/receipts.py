from app.gallery.media_processing import MediaValidationError, compress_to_webp, load_reduced

# Images are re-encoded to WebP (<= 700KB, see media_processing); a PDF can't be recompressed
# here, so it gets its own, larger cap.
MAX_UPLOAD_SIZE = 10 * 1024 * 1024
MAX_PDF_SIZE = 2 * 1024 * 1024
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heif", "image/heic", "application/pdf"}


class ReceiptValidationError(Exception):
    pass


def validate_receipt(file_storage) -> tuple[bytes, str]:
    data = file_storage.read()
    if len(data) > MAX_UPLOAD_SIZE:
        raise ReceiptValidationError("File exceeds the 10MB size limit.")

    content_type = file_storage.mimetype
    if content_type not in ALLOWED_MIME_TYPES:
        raise ReceiptValidationError("Unsupported file type. Use a JPEG, PNG, WEBP, HEIC, or PDF.")

    if content_type == "application/pdf":
        if len(data) > MAX_PDF_SIZE:
            raise ReceiptValidationError("PDF exceeds the 2MB size limit.")
        return data, content_type

    try:
        image, _ = load_reduced(data)
        return compress_to_webp(image)[0], "image/webp"
    except MediaValidationError as exc:
        raise ReceiptValidationError(str(exc)) from exc
