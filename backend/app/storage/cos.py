from pathlib import Path
from typing import BinaryIO

from app.storage.base import Storage


class CosStorage(Storage):
    """腾讯云 COS 私有对象存储实现。"""

    def __init__(self, secret_id: str, secret_key: str, region: str, bucket: str) -> None:
        from qcloud_cos import CosConfig, CosS3Client

        self.bucket = bucket
        self.client = CosS3Client(
            CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key),
        )

    def save(self, key: str, source: BinaryIO) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=source)

    def open(self, key: str, mode: str = "rb") -> BinaryIO:
        if mode != "rb":
            raise ValueError("COS 仅支持以 rb 模式读取")
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].get_raw_stream()

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            if getattr(exc, "status_code", None) == 404:
                return False
            raise
        return True

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def get_size(self, key: str) -> int:
        return int(self.client.head_object(Bucket=self.bucket, Key=key)["Content-Length"])

    def download_to_path(self, key: str, target: Path) -> Path:
        target.parent.mkdir(parents=True, exist_ok=True)
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        response["Body"].get_stream_to_file(str(target))
        return target

    def upload_from_path(self, key: str, source: Path, content_type: str = "") -> None:
        kwargs = {"Bucket": self.bucket, "Key": key, "LocalFilePath": str(source)}
        if content_type:
            kwargs["ContentType"] = content_type
        self.client.upload_file(**kwargs)

