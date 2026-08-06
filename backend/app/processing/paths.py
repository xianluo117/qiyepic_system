from pathlib import Path


def get_processed_filename(original_filename: str) -> str:
    """将任意原文件名转换为统一的 JPG 处理图文件名。"""
    return f"{Path(original_filename).stem}.jpg"
