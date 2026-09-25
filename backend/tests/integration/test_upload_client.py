"""本地上传客户端的失败、超时及成功结果测试。"""

import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest


@pytest.mark.parametrize("outcome,expected", [("success", 0), ("rejected", 1), ("timeout", 1)])
def test_upload_client(monkeypatch, tmp_path, capsys, outcome, expected):
    path = Path(__file__).resolve().parents[3] / "tools" / "image_upload.py"
    spec = importlib.util.spec_from_file_location("upload_client", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    image = tmp_path / "image.png"
    image.write_bytes(b"fake-image-for-transport-test")
    monkeypatch.setenv("QIYE_IMAGE_BASE_URL", "https://image.invalid")
    monkeypatch.setenv("QIYE_IMAGE_TOKEN", "qimg_test-secret")
    monkeypatch.setattr(sys, "argv", [str(path), str(image), "--sku", "A", "--ratio-width", "1",
                                     "--ratio-height", "1", "--min-short-side-px", "10"])

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def post(self, url, **kwargs):
            assert kwargs["files"]["files"][1].read() == b"fake-image-for-transport-test"
            if outcome == "timeout":
                raise httpx.ReadTimeout("secret must not appear: qimg_test-secret")
            return httpx.Response(200, request=httpx.Request("POST", url), json={
                "results": [{"success": outcome == "success"}],
            })

    monkeypatch.setattr(module.httpx, "Client", Client)
    assert module.main() == expected
    output = capsys.readouterr().out
    assert "qimg_test-secret" not in output
    result = json.loads(output)["results"][0]
    if outcome == "timeout":
        assert result["delivery_unknown"] is True
