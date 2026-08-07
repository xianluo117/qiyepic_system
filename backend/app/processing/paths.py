from pathlib import Path


def get_processed_filename(original_filename: str) -> str:
    """将任意原文件名转换为统一的 JPG 处理图文件名。"""
    return f"{Path(original_filename).stem}.jpg"


def get_versioned_processed_filename(
    original_filename: str,
    image_id: int,
    version_number: int,
) -> str:
    """生成不会被后续重新处理覆盖的版本文件名。"""
    stem = Path(original_filename).stem
    return f"{stem}.image-{image_id}.v{version_number}.jpg"
