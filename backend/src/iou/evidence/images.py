"""Decode and normalize evidence for safe private viewing; not forensic originals."""

import hashlib
from dataclasses import dataclass
from io import BytesIO

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError

from iou.evidence.models import MAX_BYTES, MAX_PIXELS


class LimitedOutput(BytesIO):
    def write(self, data):
        if self.tell() + len(data) > MAX_BYTES:
            raise HTTPException(413, "Normalized image exceeds 5 MiB; resize it before uploading.")
        return super().write(data)


@dataclass(frozen=True)
class NormalizedImage:
    data: bytes
    original_sha256: str
    sha256: str
    width: int
    height: int


def normalize(data: bytes, content_type: str) -> NormalizedImage:
    if not data or len(data) > MAX_BYTES:
        raise HTTPException(413, "Images must contain between 1 byte and 5 MiB.")
    formats = {"image/jpeg": "JPEG", "image/png": "PNG"}
    if content_type not in formats:
        raise HTTPException(422, "Only JPEG and PNG images are supported.")
    try:
        with Image.open(BytesIO(data)) as probe:
            if probe.format != formats[content_type] or getattr(probe, "n_frames", 1) != 1:
                raise HTTPException(
                    422, "Image content must match its declared type and be static."
                )
            width, height = probe.size
            if width > 8000 or height > 8000 or width * height > MAX_PIXELS:
                raise HTTPException(
                    413, "Images must be at most 16 megapixels and 8000 pixels per side."
                )
            probe.verify()
        with Image.open(BytesIO(data)) as decoded:
            decoded.load()  # Reject truncated/corrupt data before sending anything to storage.
            with ImageOps.exif_transpose(decoded) as oriented:
                mode = (
                    "RGBA"
                    if content_type == "image/png"
                    and ("A" in oriented.getbands() or "transparency" in oriented.info)
                    else "RGB"
                )
                # New image, not just new filename: no EXIF, text, ICC, or trailing data.
                with (
                    oriented.convert(mode) as pixels,
                    Image.new(mode, pixels.size) as clean,
                    LimitedOutput() as output,
                ):
                    clean.paste(pixels)
                    clean.save(
                        output,
                        format=formats[content_type],
                        **({"quality": 90} if content_type == "image/jpeg" else {}),
                    )
                    normalized = output.getvalue()
                    width, height = clean.size
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, SyntaxError):
        raise HTTPException(422, "Image is invalid, corrupt, or unsupported.") from None
    return NormalizedImage(
        normalized,
        hashlib.sha256(data).hexdigest(),
        hashlib.sha256(normalized).hexdigest(),
        width,
        height,
    )
