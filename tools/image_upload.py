"""Agent 本地上传工具：读取本地文件，通过图床 API 传输二进制。"""

import argparse
import json
import os
import sys
from pathlib import Path

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description="上传本地图片到图床，输出 JSON 响应")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--sku", required=True)
    parser.add_argument("--ratio-width", type=int, required=True)
    parser.add_argument("--ratio-height", type=int, required=True)
    parser.add_argument("--min-short-side-px", type=int, required=True)
    args = parser.parse_args()
    base_url = os.environ.get("QIYE_IMAGE_BASE_URL", "").rstrip("/")
    token = os.environ.get("QIYE_IMAGE_TOKEN", "")
    if not base_url.startswith("https://") or not token.startswith("qimg_"):
        parser.error("请设置 HTTPS 的 QIYE_IMAGE_BASE_URL 和 QIYE_IMAGE_TOKEN")
    if (
        not args.sku.strip()
        or not 1 <= args.ratio_width <= 1000
        or not 1 <= args.ratio_height <= 1000
        or not 1 <= args.min_short_side_px <= 20000
    ):
        parser.error("货号及处理参数必须有效")
    for path in args.files:
        if not path.is_file() or path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            parser.error(f"文件不存在或格式不支持: {path}")
        if path.stat().st_size > 30 * 1024 * 1024:
            parser.error(f"文件超过默认 30 MB 上限: {path}")
    # 一张图一个请求：遇到网络断连时可按文件追查，避免整批结果不确定。
    results = []
    for path in args.files:
        try:
            with path.open("rb") as stream, httpx.Client(timeout=120, follow_redirects=False) as client:
                response = client.post(
                    base_url + "/api/images/upload",
                    headers={"Authorization": "Bearer " + token},
                    data={"sku": args.sku, "ratio_width": args.ratio_width,
                          "ratio_height": args.ratio_height,
                          "min_short_side_px": args.min_short_side_px},
                    files={"files": (path.name, stream)},
                )
            response.raise_for_status()
            payload = response.json()
            entries = payload.get("results") if isinstance(payload, dict) else None
            if not isinstance(entries, list) or not entries:
                raise ValueError("服务器未返回逐文件结果")
            accepted = all(isinstance(item, dict) and item.get("success") is True
                           for item in entries)
            result = {"file": str(path), "response": payload, "accepted": accepted}
            if not accepted:
                result["error"] = "服务器拒绝了图片，请查看逐文件结果"
            results.append(result)
        except httpx.HTTPStatusError as exc:
            results.append({"file": str(path), "error": "HTTP 请求失败",
                            "status": exc.response.status_code,
                            "delivery_unknown": exc.response.status_code >= 500})
        except (httpx.RequestError, ValueError):
            results.append({"file": str(path), "error": "传输或响应异常，请查询后再决定是否重传",
                            "delivery_unknown": True})
        except OSError:
            results.append({"file": str(path), "error": "本地文件读取失败",
                            "delivery_unknown": True})
    print(json.dumps({"results": results}, ensure_ascii=False))
    return 0 if all("error" not in item for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
