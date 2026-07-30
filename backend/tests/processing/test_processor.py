from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from app.processing.processor import ImageProcessor


def test_center_crop_then_enlarge(tmp_path: Path) -> None:
    source = tmp_path / "source.jpg"
    target = tmp_path / "processed.jpg"
    Image.new("RGB", (1200, 1200), color="white").save(source, format="JPEG")

    result = ImageProcessor().process(
        source_path=source,
        target_path=target,
        ratio_width=3,
        ratio_height=4,
        min_short_side_px=1200,
    )

    assert result.cropped_width == 900
    assert result.cropped_height == 1200
    assert result.enlarged is True
    assert result.output_width == 1200
    assert result.output_height == 1600

    with Image.open(target) as processed:
        assert processed.size == (1200, 1600)


def test_no_enlarge_when_cropped_short_side_is_enough(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    target = tmp_path / "processed.png"
    Image.new("RGB", (2000, 2000), color="white").save(source, format="PNG")

    result = ImageProcessor().process(
        source_path=source,
        target_path=target,
        ratio_width=3,
        ratio_height=4,
        min_short_side_px=1200,
    )

    assert result.cropped_width == 1500
    assert result.cropped_height == 2000
    assert result.enlarged is False
    assert result.output_width == 1500
    assert result.output_height == 2000


def test_large_enlarge_uses_progressive_lanczos_steps() -> None:
    processor = ImageProcessor()
    source = Image.new("RGB", (100, 150), color="white")
    resize_sizes: list[tuple[int, int]] = []
    original_resize = Image.Image.resize

    def tracked_resize(
        image: Image.Image,
        size: tuple[int, int],
        resample: Image.Resampling | None = None,
        box: tuple[float, float, float, float] | None = None,
        reducing_gap: float | None = None,
    ) -> Image.Image:
        resize_sizes.append(size)
        return original_resize(image, size, resample, box, reducing_gap)

    with patch.object(Image.Image, "resize", tracked_resize):
        output = processor._progressive_resize(source, 500, 750)

    assert resize_sizes == [(200, 300), (400, 600), (500, 750)]
    assert output.size == (500, 750)


def test_enlarged_image_is_sharpened(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    target = tmp_path / "processed.png"
    image = Image.new("RGB", (120, 120), color="white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((30, 30, 89, 89), fill="black")
    image.save(source, format="PNG")

    processor = ImageProcessor()
    original_sharpen = processor._sharpen_enlarged_image
    with patch.object(
        processor,
        "_sharpen_enlarged_image",
        wraps=original_sharpen,
    ) as sharpen:
        result = processor.process(
            source_path=source,
            target_path=target,
            ratio_width=1,
            ratio_height=1,
            min_short_side_px=240,
        )

    assert result.enlarged is True
    sharpen.assert_called_once()

    resized_only = processor._progressive_resize(image, 240, 240)
    with Image.open(target) as processed:
        assert processed.size == (240, 240)
        assert processed.tobytes() != resized_only.tobytes()


def test_image_is_not_sharpened_without_enlarging(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    target = tmp_path / "processed.png"
    Image.new("RGB", (200, 200), color=(30, 80, 130)).save(source, format="PNG")

    processor = ImageProcessor()
    with patch.object(processor, "_sharpen_enlarged_image") as sharpen:
        result = processor.process(
            source_path=source,
            target_path=target,
            ratio_width=1,
            ratio_height=1,
            min_short_side_px=200,
        )

    assert result.enlarged is False
    sharpen.assert_not_called()

    with Image.open(source) as original, Image.open(target) as processed:
        assert processed.size == original.size
        assert processed.tobytes() == original.tobytes()


def test_transparent_png_keeps_alpha_when_enlarged(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    target = tmp_path / "processed.png"
    image = Image.new("RGBA", (100, 100), color=(255, 0, 0, 0))
    image.paste((255, 0, 0, 255), (25, 25, 75, 75))
    image.save(source, format="PNG")

    result = ImageProcessor().process(
        source_path=source,
        target_path=target,
        ratio_width=1,
        ratio_height=1,
        min_short_side_px=200,
    )

    assert result.output_width == 200
    assert result.output_height == 200
    with Image.open(target) as processed:
        assert processed.mode == "RGBA"
        assert processed.getpixel((0, 0))[3] == 0
        assert processed.getpixel((100, 100))[3] == 255
