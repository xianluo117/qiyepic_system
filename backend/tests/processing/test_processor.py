from pathlib import Path
from unittest.mock import call, patch

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


def test_jpeg_retries_quality_90_when_quality_95_exceeds_limit(tmp_path: Path) -> None:
    target = tmp_path / "processed.jpg"
    image = Image.new("RGB", (100, 100), color="white")
    processor = ImageProcessor()

    def fake_save(path: Path, **options: object) -> None:
        size = 101 if options["quality"] == 95 else 99
        Path(path).write_bytes(b"x" * size)

    with (
        patch.object(ImageProcessor, "_MAX_OUTPUT_SIZE_BYTES", 100),
        patch.object(image, "save", side_effect=fake_save) as save,
    ):
        file_size, setting = processor._save(image, target, "JPEG")

    assert file_size == 99
    assert setting == "quality=90"
    assert target.stat().st_size == 99
    assert save.call_args_list == [
        call(
            target.with_name(".processed.jpg.processing"),
            format="JPEG",
            quality=95,
            optimize=True,
            subsampling=0,
        ),
        call(
            target.with_name(".processed.jpg.processing"),
            format="JPEG",
            quality=90,
            optimize=True,
            subsampling=0,
        ),
    ]


def test_webp_uses_quality_95_when_output_is_within_limit(tmp_path: Path) -> None:
    target = tmp_path / "processed.webp"
    image = Image.new("RGB", (100, 100), color="white")
    processor = ImageProcessor()

    def fake_save(path: Path, **_: object) -> None:
        Path(path).write_bytes(b"x" * 99)

    with (
        patch.object(ImageProcessor, "_MAX_OUTPUT_SIZE_BYTES", 100),
        patch.object(image, "save", side_effect=fake_save) as save,
    ):
        file_size, setting = processor._save(image, target, "WEBP")

    assert file_size == 99
    assert setting == "quality=95"
    save.assert_called_once_with(
        target.with_name(".processed.webp.processing"),
        format="WEBP",
        quality=95,
        method=6,
    )


def test_png_retries_compression_level_8_after_level_9(tmp_path: Path) -> None:
    target = tmp_path / "processed.png"
    image = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
    processor = ImageProcessor()

    def fake_save(path: Path, **options: object) -> None:
        size = 101 if options["compress_level"] == 9 else 99
        Path(path).write_bytes(b"x" * size)

    with (
        patch.object(ImageProcessor, "_MAX_OUTPUT_SIZE_BYTES", 100),
        patch.object(image, "save", side_effect=fake_save) as save,
    ):
        file_size, setting = processor._save(image, target, "PNG")

    assert file_size == 99
    assert setting == "compress_level=8"
    assert image.mode == "RGBA"
    assert save.call_args_list == [
        call(
            target.with_name(".processed.png.processing"),
            format="PNG",
            optimize=True,
            compress_level=9,
        ),
        call(
            target.with_name(".processed.png.processing"),
            format="PNG",
            optimize=True,
            compress_level=8,
        ),
    ]


def test_save_fails_and_cleans_files_when_all_candidates_exceed_limit(
    tmp_path: Path,
) -> None:
    target = tmp_path / "processed.jpg"
    temporary = target.with_name(".processed.jpg.processing")
    target.write_bytes(b"old-output")
    image = Image.new("RGB", (100, 100), color="white")
    processor = ImageProcessor()

    def fake_save(path: Path, **_: object) -> None:
        Path(path).write_bytes(b"x" * 101)

    with (
        patch.object(ImageProcessor, "_MAX_OUTPUT_SIZE_BYTES", 100),
        patch.object(image, "save", side_effect=fake_save),
    ):
        try:
            processor._save(image, target, "JPEG")
        except ValueError as exc:
            assert "处理图压缩后仍超过 2 MiB" in str(exc)
        else:
            raise AssertionError("所有压缩候选超限时应处理失败")

    assert not target.exists()
    assert not temporary.exists()
