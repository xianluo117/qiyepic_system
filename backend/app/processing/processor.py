from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps


class OutputSizeLimitError(ValueError):
    """所有候选编码均超过处理图大小上限。"""


@dataclass(frozen=True, slots=True)
class ImageProcessResult:
    original_width: int
    original_height: int
    cropped_width: int
    cropped_height: int
    output_width: int
    output_height: int
    output_file_size: int
    compression_setting: str
    enlarged: bool
    reduced_for_size_limit: bool


class ImageProcessor:
    """执行先居中裁剪、后判断是否放大的处理流程。"""

    _MAX_RESIZE_SCALE = 2
    _MAX_OUTPUT_SIZE_BYTES = 2 * 1024 * 1024
    _LOSSY_QUALITIES = (95, 90)
    _PNG_COMPRESSION_LEVELS = (9, 8)
    _SHARPEN_RADIUS = 1.2
    _SHARPEN_PERCENT = 110
    _SHARPEN_THRESHOLD = 3

    def process(
        self,
        source_path: Path,
        target_path: Path,
        ratio_width: int,
        ratio_height: int,
        min_short_side_px: int,
    ) -> ImageProcessResult:
        if ratio_width <= 0 or ratio_height <= 0:
            raise ValueError("目标比例必须大于 0")
        if min_short_side_px <= 0:
            raise ValueError("最小短边必须大于 0")

        with Image.open(source_path) as opened:
            image = ImageOps.exif_transpose(opened)
            original_width, original_height = image.size
            cropped = self._center_crop(image, ratio_width, ratio_height)
            cropped_width, cropped_height = cropped.size

            short_side = min(cropped_width, cropped_height)
            enlarged = short_side < min_short_side_px
            reduced_for_size_limit = False
            output = cropped

            if enlarged:
                scale = min_short_side_px / short_side
                output_width = max(1, round(cropped_width * scale))
                output_height = max(1, round(cropped_height * scale))
                output = self._progressive_resize(cropped, output_width, output_height)
                output = self._sharpen_enlarged_image(output)

            target_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                output_file_size, compression_setting = self._save(
                    output,
                    target_path,
                    opened.format,
                )
            except OutputSizeLimitError:
                output_short_side = min(output.size)
                if output_short_side <= min_short_side_px:
                    raise
                scale = min_short_side_px / output_short_side
                output_width = max(1, round(output.width * scale))
                output_height = max(1, round(output.height * scale))
                output = output.resize(
                    (output_width, output_height),
                    Image.Resampling.LANCZOS,
                )
                reduced_for_size_limit = True
                output_file_size, compression_setting = self._save(
                    output,
                    target_path,
                    opened.format,
                )

            output_width, output_height = output.size

        return ImageProcessResult(
            original_width=original_width,
            original_height=original_height,
            cropped_width=cropped_width,
            cropped_height=cropped_height,
            output_width=output_width,
            output_height=output_height,
            output_file_size=output_file_size,
            compression_setting=compression_setting,
            enlarged=enlarged,
            reduced_for_size_limit=reduced_for_size_limit,
        )

    @staticmethod
    def _center_crop(image: Image.Image, ratio_width: int, ratio_height: int) -> Image.Image:
        width, height = image.size
        target_ratio = ratio_width / ratio_height

        crop_width = width
        crop_height = round(width / target_ratio)

        if crop_height > height:
            crop_height = height
            crop_width = round(height * target_ratio)

        left = max(0, (width - crop_width) // 2)
        top = max(0, (height - crop_height) // 2)
        right = left + crop_width
        bottom = top + crop_height
        return image.crop((left, top, right, bottom))

    @classmethod
    def _progressive_resize(
        cls,
        image: Image.Image,
        target_width: int,
        target_height: int,
    ) -> Image.Image:
        """分阶段使用 Lanczos 放大，避免一次大倍率插值造成明显软化。"""
        output = image

        while (
            target_width > output.width * cls._MAX_RESIZE_SCALE
            or target_height > output.height * cls._MAX_RESIZE_SCALE
        ):
            next_width = min(target_width, output.width * cls._MAX_RESIZE_SCALE)
            next_height = min(target_height, output.height * cls._MAX_RESIZE_SCALE)
            output = output.resize(
                (next_width, next_height),
                Image.Resampling.LANCZOS,
            )

        if output.size != (target_width, target_height):
            output = output.resize(
                (target_width, target_height),
                Image.Resampling.LANCZOS,
            )

        return output

    @classmethod
    def _sharpen_enlarged_image(cls, image: Image.Image) -> Image.Image:
        """对放大结果执行轻度反遮罩锐化，并避免直接锐化透明通道。"""
        alpha = image.getchannel("A") if "A" in image.getbands() else None
        base_mode = "L" if image.mode in {"L", "LA"} else "RGB"
        output = image.convert(base_mode).filter(
            ImageFilter.UnsharpMask(
                radius=cls._SHARPEN_RADIUS,
                percent=cls._SHARPEN_PERCENT,
                threshold=cls._SHARPEN_THRESHOLD,
            ),
        )

        if alpha is not None:
            output.putalpha(alpha)

        return output

    @classmethod
    def _save(
        cls,
        image: Image.Image,
        target_path: Path,
        source_format: str | None,
    ) -> tuple[int, str]:
        image_format = (source_format or target_path.suffix.lstrip(".")).upper()
        candidates: list[tuple[dict[str, int | bool], str]]

        if image_format in {"JPG", "JPEG"}:
            image_format = "JPEG"
            if image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")
            candidates = [
                (
                    {"quality": quality, "optimize": True, "subsampling": 0},
                    f"quality={quality}",
                )
                for quality in cls._LOSSY_QUALITIES
            ]
        elif image_format == "WEBP":
            candidates = [
                (
                    {"quality": quality, "method": 6},
                    f"quality={quality}",
                )
                for quality in cls._LOSSY_QUALITIES
            ]
        elif image_format == "PNG":
            candidates = [
                (
                    {"optimize": True, "compress_level": level},
                    f"compress_level={level}",
                )
                for level in cls._PNG_COMPRESSION_LEVELS
            ]
        else:
            raise ValueError(f"不支持的输出格式: {image_format}")

        temporary = target_path.with_name(f".{target_path.name}.processing")
        target_path.unlink(missing_ok=True)
        try:
            for save_options, compression_setting in candidates:
                temporary.unlink(missing_ok=True)
                image.save(temporary, format=image_format, **save_options)
                output_file_size = temporary.stat().st_size
                if output_file_size <= cls._MAX_OUTPUT_SIZE_BYTES:
                    temporary.replace(target_path)
                    return output_file_size, compression_setting

            raise OutputSizeLimitError(
                "处理图压缩后仍超过 2 MiB；"
                f"格式={image_format}，最后大小={output_file_size} 字节"
            )
        except Exception:
            temporary.unlink(missing_ok=True)
            target_path.unlink(missing_ok=True)
            raise
