import os
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps

_THUMBNAIL_MAX_SIDE = 360
_THUMBNAIL_QUALITY = 82


class ThumbnailService:
    """按图片记录 ID 生成并缓存图库缩略图。"""

    def __init__(self, image_root: Path) -> None:
        self.cache_root = (image_root / ".thumbnails").resolve()
        self.cache_root.mkdir(parents=True, exist_ok=True)

    def get_or_create(self, image_id: int, source_path: Path) -> Path:
        target = self.get_path(image_id)
        if target.is_file():
            return target

        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(
            f".{target.name}.{os.getpid()}.{uuid4().hex}.generating"
        )
        try:
            with Image.open(source_path) as opened:
                image = ImageOps.exif_transpose(opened)
                image = self._flatten_to_rgb(image)
                image.thumbnail(
                    (_THUMBNAIL_MAX_SIDE, _THUMBNAIL_MAX_SIDE),
                    Image.Resampling.LANCZOS,
                )
                image.save(
                    temporary,
                    format="JPEG",
                    quality=_THUMBNAIL_QUALITY,
                    optimize=True,
                    progressive=True,
                )
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)

        return target

    def delete(self, image_id: int) -> None:
        self.get_path(image_id).unlink(missing_ok=True)

    def get_path(self, image_id: int) -> Path:
        if image_id <= 0:
            raise ValueError("图片 ID 必须为正整数")
        return self.cache_root / f"{image_id}.jpg"

    @staticmethod
    def _flatten_to_rgb(image: Image.Image) -> Image.Image:
        if image.mode == "RGB":
            return image.copy()
        if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
            rgba = image.convert("RGBA")
            background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            return Image.alpha_composite(background, rgba).convert("RGB")
        return image.convert("RGB")
