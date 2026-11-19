"""Yuborilgan rasmni AI qabul qiladigan formatga keltirish."""

import io

from PIL import Image

from app.utils.images import guess_image_type, to_supported_image


def picture(fmt: str) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), (10, 120, 200)).save(buffer, format=fmt)
    return buffer.getvalue()


def test_jpeg_and_png_pass_through_unchanged():
    jpeg = picture("JPEG")
    assert to_supported_image(jpeg, "image/jpeg") == (jpeg, "image/jpeg")
    png = picture("PNG")
    assert to_supported_image(png, "image/png") == (png, "image/png")


def test_other_formats_are_converted_to_jpeg():
    data, media_type = to_supported_image(picture("BMP"), "image/bmp")
    assert media_type == "image/jpeg"
    assert Image.open(io.BytesIO(data)).format == "JPEG"


def test_unknown_type_is_detected_from_the_bytes():
    data, media_type = to_supported_image(picture("PNG"), None)
    assert media_type == "image/jpeg"
    assert Image.open(io.BytesIO(data)).size == (8, 8)


def test_unreadable_file_gives_none():
    assert to_supported_image(b"not an image at all", "image/heic") is None


def test_guess_image_type_uses_mime_then_file_name():
    assert guess_image_type("image/png", "a.bin") == "image/png"
    assert guess_image_type(None, "IMG_0012.PNG") == "image/png"
    assert guess_image_type(None, "IMG_0012.HEIC") == "image/heic"
    assert guess_image_type(None, "chek.pdf") is None
    assert guess_image_type("application/pdf", "chek.png") is None
    assert guess_image_type(None, None) is None
