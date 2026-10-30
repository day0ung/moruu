from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from channels.gdrive import get_token
from channels.gdrive.client import FOLDER_MIME, DriveError, DriveFile
from channels.gdrive.sync import folder_path, pull, upload_outputs


class FakeDrive:
    def __init__(self, files=()):
        self.files, self.downloaded, self.uploaded, self.folders = list(files), [], [], []

    def list(self, folder_id):
        return self.files

    def download(self, file_id, dest):
        self.downloaded.append(file_id)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"new")

    def upload(self, path, folder_id):
        self.uploaded.append((path.name, folder_id))
        return f"id-{path.name}"

    def ensure_folder(self, parent, name):
        self.folders.append((parent, name))
        return f"{parent}/{name}"


def test_pull_skips_folders_outputs_and_same_size(tmp_path):
    (tmp_path / "02.png").write_bytes(b"abc")
    drive = FakeDrive([DriveFile("1", "01.png", "image/png", 3), DriveFile("2", "02.png", "image/png", 3),
                       DriveFile("3", "sub", FOLDER_MIME, None), DriveFile("4", "YT-1.mp4", "video/mp4", 9),
                       DriveFile("5", "YT-1.srt", "text/plain", 9), DriveFile("6", "출처.txt", "text/plain", 5)])
    assert pull(drive, "F", tmp_path) == ["01.png", "출처.txt"]
    assert drive.downloaded == ["1", "6"]


def test_upload_outputs_skips_missing_and_returns_first_link(tmp_path):
    (tmp_path / "YT-1.mp4").write_bytes(b"v")
    drive = FakeDrive()
    link = upload_outputs(drive, "F", [tmp_path / "YT-1.mp4", tmp_path / "YT-1.srt"])
    assert link == "https://drive.google.com/file/d/id-YT-1.mp4/view"
    assert drive.uploaded == [("YT-1.mp4", "F")]


def test_folder_path_creates_in_order():
    drive = FakeDrive()
    assert folder_path(drive, "R", "롱폼", "YT-1") == "R/롱폼/YT-1"
    assert drive.folders == [("R", "롱폼"), ("R/롱폼", "YT-1")]


def test_auth_url_offline_consent_pkce():
    q = parse_qs(urlparse(get_token.auth_url("cid", "http://127.0.0.1:5555/", "CHAL")).query)
    assert q["access_type"] == ["offline"] and q["prompt"] == ["consent"]
    assert q["scope"] == ["https://www.googleapis.com/auth/drive"]
    assert q["code_challenge"] == ["CHAL"] and q["code_challenge_method"] == ["S256"]
    assert q["redirect_uri"] == ["http://127.0.0.1:5555/"] and q["response_type"] == ["code"]


def test_exchange_returns_refresh_token():
    sent = []

    def handler(req):
        sent.append(parse_qs(req.content.decode()))
        return httpx.Response(200, json={"access_token": "A", "refresh_token": "R"})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    assert get_token.exchange(http, "cid", "sec", "CODE", "http://127.0.0.1:1/", "VER") == "R"
    assert sent[0]["grant_type"] == ["authorization_code"] and sent[0]["code_verifier"] == ["VER"]


def test_exchange_without_refresh_token_is_error():
    http = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json={"access_token": "A"})))
    with pytest.raises(DriveError):
        get_token.exchange(http, "cid", "sec", "CODE", "http://127.0.0.1:1/", "VER")
