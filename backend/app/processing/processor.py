from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps


@dataclass(frozen=True, slots=True)
class ImageProcessResult:
    original_width: int
    original_height: int
    cropped_width: int
    cropped_height: int
    output_width: int
    output_height: int
    enlarged: bool


class ImageProcessor:
    """执行先居中裁剪、后判断是否放大的处理流程。"""

    _MAX_RESIZE_SCALE = 2
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
            output = cropped

            if enlarged:
                scale = min_short_side_px / short_side
                output_width = max(1, round(cropped_width * scale))
                output_height = max(1, round(cropped_height * scale))
                output = self._progressive_resize(cropped, output_width, output_height)
                output = self._sharpen_enlarged_image(output)

            output_width, output_height = output.size
            target_path.parent.mkdir(parents=True, exist_ok=True)
            self._save(output, target_path, opened.format)

        return ImageProcessResult(
            original_width=original_width,
            original_height=original_height,
            cropped_width=cropped_width,
            cropped_height=cropped_height,
            output_width=output_width,
            output_height=output_height,
            enlarged=enlarged,
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

    @staticmethod
    def _save(image: Image.Image, target_path: Path, source_format: str | None) -> None:
        image_format = (source_format or target_path.suffix.lstrip(".")).upper()
        save_options: dict[str, int | bool] = {}

        if image_format in {"JPG", "JPEG"}:
            image_format = "JPEG"
            if image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")
            save_options = {"quality": 95, "optimize": True, "subsampling": 0}
        elif image_format == "WEBP":
            save_options = {"quality": 95, "method": 6}
        elif image_format != "PNG":
            raise ValueError(f"不支持的输出格式: {image_format}")

        temporary = target_path.with_name(f".{target_path.name}.processing")
        try:
            image.save(temporary, format=image_format, **save_options)
            temporary.replace(target_path)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
