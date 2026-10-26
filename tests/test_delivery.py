import hashlib
import io
import json
import runpy
import shutil
import urllib.request
from pathlib import Path

import pytest


@pytest.mark.parametrize("corrupt", [False, True])
def test_pinned_ocr_download_does_not_replace_with_unverified_bytes(tmp_path, monkeypatch, corrupt):
    scripts = tmp_path / "scripts"
    data = tmp_path / "resources/tessdata"
    scripts.mkdir()
    data.mkdir(parents=True)
    script = scripts / "fetch-ocr-data.py"
    shutil.copyfile(Path(__file__).resolve().parents[1] / "scripts/fetch-ocr-data.py", script)
    expected = b"verified synthetic OCR data"
    revision = "87416418657359cb625c412a48b6e1d6d41c29bd"
    (data / "manifest.json").write_text(json.dumps({"revision": revision, "files": {
        "eng.traineddata": {"bytes": len(expected), "sha256": hashlib.sha256(expected).hexdigest()}
    }}), "utf-8")
    destination = data / "eng.traineddata"
    destination.write_bytes(b"previous known data")

    def download(url, timeout):
        assert f"/{revision}/eng.traineddata" in url and "/main/" not in url
        return io.BytesIO(b"corrupt" if corrupt else expected)

    monkeypatch.setattr(urllib.request, "urlopen", download)
    if corrupt:
        with pytest.raises(ValueError, match="integrity check failed"):
            runpy.run_path(str(script))
        assert destination.read_bytes() == b"previous known data"
    else:
        runpy.run_path(str(script))
        assert destination.read_bytes() == expected
