from pathlib import Path
from unittest.mock import call, patch

from PIL import Image, ImageDraw

from app.processing.processor import ImageProcessor, OutputSizeLimitError


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
    target = tmp_path / "processed.jpg"
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
    target = tmp_path / "processed.jpg"
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
        assert processed.format == "JPEG"
        assert processed.size == (240, 240)
        assert processed.tobytes() != resized_only.tobytes()


def test_image_is_not_sharpened_without_enlarging(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    target = tmp_path / "processed.jpg"
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
        assert processed.format == "JPEG"
        assert processed.mode == "RGB"
        assert processed.size == original.size


def test_transparent_png_is_flattened_to_white_jpeg(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    target = tmp_path / "processed.jpg"
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
        assert processed.format == "JPEG"
        assert processed.mode == "RGB"
        background = processed.getpixel((10, 10))
        foreground = processed.getpixel((100, 100))
        assert all(channel >= 245 for channel in background)
        assert foreground[0] >= 245
        assert foreground[1] <= 10
        assert foreground[2] <= 10


def test_semtransparent_pixel_is_composited_with_white() -> None:
    image = Image.new("RGBA", (1, 1), color=(255, 0, 0, 128))

    flattened = ImageProcessor._flatten_to_rgb(image)

    assert flattened.mode == "RGB"
    red, green, blue = flattened.getpixel((0, 0))
    assert red == 255
    assert 126 <= green <= 128
    assert 126 <= blue <= 128


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
        file_size, setting = processor._save(image, target)

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


def test_webp_source_is_written_as_jpeg(tmp_path: Path) -> None:
    source = tmp_path / "source.webp"
    target = tmp_path / "processed.jpg"
    Image.new("RGB", (100, 100), color=(30, 80, 130)).save(source, format="WEBP")

    ImageProcessor().process(
        source_path=source,
        target_path=target,
        ratio_width=1,
        ratio_height=1,
        min_short_side_px=100,
    )

    with Image.open(target) as processed:
        assert processed.format == "JPEG"
        assert processed.mode == "RGB"


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
            processor._save(image, target)
        except ValueError as exc:
            assert "处理图压缩后仍超过 2 MiB" in str(exc)
        else:
            raise AssertionError("所有压缩候选超限时应处理失败")

    assert not target.exists()
    assert not temporary.exists()


def test_process_reduces_to_minimum_short_side_after_size_limit(tmp_path: Path) -> None:
    source = tmp_path / "source.jpg"
    target = tmp_path / "processed.jpg"
    Image.new("RGB", (2000, 3000), color="white").save(source, format="JPEG")
    processor = ImageProcessor()
    save_calls: list[tuple[int, int]] = []

    def fake_save(image: Image.Image, _: Path) -> tuple[int, str]:
        save_calls.append(image.size)
        if len(save_calls) == 1:
            raise OutputSizeLimitError("too large")
        return 100, "quality=95"

    with patch.object(processor, "_save", side_effect=fake_save):
        result = processor.process(
            source_path=source,
            target_path=target,
            ratio_width=2,
            ratio_height=3,
            min_short_side_px=1000,
        )

    assert save_calls == [(2000, 3000), (1000, 1500)]
    assert result.output_width == 1000
    assert result.output_height == 1500
    assert result.reduced_for_size_limit is True


def test_process_does_not_reduce_below_minimum_short_side(tmp_path: Path) -> None:
    source = tmp_path / "source.jpg"
    target = tmp_path / "processed.jpg"
    Image.new("RGB", (1000, 1500), color="white").save(source, format="JPEG")
    processor = ImageProcessor()

    with patch.object(
        processor,
        "_save",
        side_effect=OutputSizeLimitError("too large"),
    ) as save:
        try:
            processor.process(
                source_path=source,
                target_path=target,
                ratio_width=2,
                ratio_height=3,
                min_short_side_px=1000,
            )
        except OutputSizeLimitError:
            pass
        else:
            raise AssertionError("达到最小短边后仍超限时应处理失败")

    save.assert_called_once()
