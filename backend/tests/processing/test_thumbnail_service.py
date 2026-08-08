from pathlib import Path

from PIL import Image

from app.services.thumbnail_service import ThumbnailService


def test_thumbnail_is_small_white_background_jpeg_and_reuses_cache(
    tmp_path: Path,
) -> None:
    source = tmp_path / "transparent.png"
    Image.new("RGBA", (1200, 600), (255, 0, 0, 0)).save(source)
    service = ThumbnailService(tmp_path)

    first = service.get_or_create(27, source)
    first_bytes = first.read_bytes()

    Image.new("RGB", (800, 800), (0, 0, 0)).save(source)
    second = service.get_or_create(27, source)

    assert second == first
    assert second.read_bytes() == first_bytes
    with Image.open(first) as thumbnail:
        assert thumbnail.format == "JPEG"
        assert thumbnail.size == (360, 180)
        assert thumbnail.mode == "RGB"
        red, green, blue = thumbnail.getpixel((180, 90))
        assert red >= 245
        assert green >= 245
        assert blue >= 245


def test_thumbnail_delete_removes_cached_file(tmp_path: Path) -> None:
    source = tmp_path / "source.jpg"
    Image.new("RGB", (800, 600), (10, 20, 30)).save(source)
    service = ThumbnailService(tmp_path)
    thumbnail = service.get_or_create(3, source)

    service.delete(3)

    assert not thumbnail.exists()
