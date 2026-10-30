import json
from urllib.parse import parse_qs

import httpx
import pytest

from channels.gdrive.client import FOLDER_MIME, DriveClient, DriveError, DriveFile, file_url, folder_url

SECRET, REFRESH = "client-secret-xyz", "refresh-token-abc"


class Api:
    """경로·메서드별 응답 목록. 보낸 요청은 self.sent."""

    def __init__(self, routes):
        self.routes, self.sent = routes, []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.sent.append(req)
        if req.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "AT", "expires_in": 3600})
        key = (req.method, req.url.path)
        return self.routes[key].pop(0)(req) if callable(self.routes[key][0]) else self.routes[key].pop(0)


def make(routes):
    api = Api(routes)
    return DriveClient("cid", SECRET, REFRESH, http=httpx.Client(transport=httpx.MockTransport(api))), api


def test_refreshes_once_and_sends_bearer():
    drive, api = make({("GET", "/drive/v3/files"): [httpx.Response(200, json={"files": []})] * 2})
    drive.child("P", "a")
    drive.child("P", "b")
    token_calls = [r for r in api.sent if r.url.host == "oauth2.googleapis.com"]
    assert len(token_calls) == 1
    form = parse_qs(token_calls[0].content.decode())
    assert form["grant_type"] == ["refresh_token"] and form["refresh_token"] == [REFRESH]
    assert api.sent[-1].headers["Authorization"] == "Bearer AT"


def test_child_query_escapes_quote():
    drive, api = make({("GET", "/drive/v3/files"): [
        httpx.Response(200, json={"files": [{"id": "X", "name": "할머니's", "mimeType": FOLDER_MIME}]})]})
    assert drive.child("P", "할머니's") == DriveFile("X", "할머니's", FOLDER_MIME, None)
    q = api.sent[-1].url.params["q"]
    assert q == r"'P' in parents and name = '할머니\'s' and trashed = false"


def test_ensure_folder_creates_when_missing():
    drive, api = make({
        ("GET", "/drive/v3/files"): [httpx.Response(200, json={"files": []})],
        ("POST", "/drive/v3/files"): [httpx.Response(200, json={"id": "NEW"})],
    })
    assert drive.ensure_folder("P", "롱폼") == "NEW"
    assert json.loads(api.sent[-1].content) == {"name": "롱폼", "mimeType": FOLDER_MIME, "parents": ["P"]}


def test_list_paginates_and_parses_size():
    drive, api = make({("GET", "/drive/v3/files"): [
        httpx.Response(200, json={"files": [{"id": "1", "name": "01.png", "mimeType": "image/png", "size": "3"}],
                                  "nextPageToken": "N"}),
        httpx.Response(200, json={"files": [{"id": "2", "name": "sub", "mimeType": FOLDER_MIME}]}),
    ]})
    assert drive.list("F") == [DriveFile("1", "01.png", "image/png", 3), DriveFile("2", "sub", FOLDER_MIME, None)]
    assert api.sent[-1].url.params["pageToken"] == "N"


def test_download(tmp_path):
    drive, api = make({("GET", "/drive/v3/files/F"): [httpx.Response(200, content=b"PNG")]})
    drive.download("F", tmp_path / "a" / "01.png")
    assert (tmp_path / "a" / "01.png").read_bytes() == b"PNG"
    assert api.sent[-1].url.params["alt"] == "media"


def test_upload_new_in_chunks(tmp_path):
    f = tmp_path / "ep.mp4"
    f.write_bytes(b"0123456789")
    ranges = []

    def put(req):
        ranges.append(req.headers["Content-Range"])
        return httpx.Response(200, json={"id": "NEW"}) if ranges[-1].startswith("bytes 8-") else httpx.Response(308)

    drive, api = make({
        ("GET", "/drive/v3/files"): [httpx.Response(200, json={"files": []})],
        ("POST", "/upload/drive/v3/files"): [httpx.Response(200, headers={"Location": "https://up.load/session1"})],
        ("PUT", "/session1"): [put, put, put],
    })
    assert drive.upload(f, "P", chunk=4) == "NEW"
    assert ranges == ["bytes 0-3/10", "bytes 4-7/10", "bytes 8-9/10"]
    start = next(r for r in api.sent if r.url.path == "/upload/drive/v3/files")
    assert start.url.params["uploadType"] == "resumable"
    assert json.loads(start.content) == {"name": "ep.mp4", "parents": ["P"]}


def test_upload_same_name_makes_new_version(tmp_path):
    f = tmp_path / "ep.mp4"
    f.write_bytes(b"01")
    drive, api = make({
        ("GET", "/drive/v3/files"): [httpx.Response(200, json={"files": [{"id": "OLD", "name": "ep.mp4"}]})],
        ("PATCH", "/upload/drive/v3/files/OLD"): [httpx.Response(200, headers={"Location": "https://up.load/s2"})],
        ("PUT", "/s2"): [httpx.Response(200, json={"id": "OLD"})],
    })
    assert drive.upload(f, "P") == "OLD"


def test_errors_carry_status_and_message_only():
    drive, _ = make({("GET", "/drive/v3/files"): [httpx.Response(403, json={"error": {"message": "insufficient"}})]})
    with pytest.raises(DriveError) as e:
        drive.child("P", "x")
    assert str(e.value) == "[403] insufficient"


def test_refresh_failure():
    def handler(req):
        return httpx.Response(400, json={"error": "invalid_grant"})

    drive = DriveClient("cid", SECRET, REFRESH, http=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(DriveError) as e:
        drive.child("P", "x")
    assert str(e.value) == "[400] invalid_grant" and REFRESH not in str(e.value) and SECRET not in str(e.value)


def test_links():
    assert file_url("F") == "https://drive.google.com/file/d/F/view"
    assert folder_url("D") == "https://drive.google.com/drive/folders/D"
