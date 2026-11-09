from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO

from fastapi import HTTPException
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse

from app.storage.base import Storage
from app.storage.local import LocalStorage
from app.storage.fallback import StorageUnavailable


class _ClosingIterator:
    def __init__(self, stream: BinaryIO, chunk_size: int = 1024 * 1024) -> None:
        self.stream = stream
        self.chunk_size = chunk_size

    def __iter__(self) -> Iterator[bytes]:
        try:
            while chunk := self.stream.read(self.chunk_size):
                yield chunk
        finally:
            self.stream.close()


def image_response(
    storage: Storage,
    key: str,
    media_type: str,
    filename: str,
    cache_control: str,
    inline: bool = False,
) -> FileResponse | RedirectResponse | StreamingResponse:
    try:
        if not storage.exists(key):
            raise HTTPException(status_code=404, detail="图片文件不存在")
    except StorageUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="图片文件不存在") from exc

    headers = {"Cache-Control": cache_control}
    if not isinstance(storage, LocalStorage):
        try:
            download_url = storage.get_download_url(
                key, media_type, filename, cache_control, inline,
            )
            if download_url is not None:
                return RedirectResponse(url=download_url, status_code=302, headers=headers)
        except StorageUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    if isinstance(storage, LocalStorage):
        path = storage.get_local_path(key)
        return FileResponse(
            path=path,
            media_type=media_type,
            filename=filename,
            content_disposition_type="inline" if inline else "attachment",
            headers=headers,
        )

    try:
        stream = storage.open(key)
    except StorageUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="图片文件不存在") from exc

    if inline:
        headers["Content-Disposition"] = "inline"
    else:
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return StreamingResponse(
        _ClosingIterator(stream),
        media_type=media_type,
        headers=headers,
    )
