from channels.gdrive.cloud import Cloud
from channels.gdrive.client import DriveFile
from core.config import DriveSettings

SETTINGS = DriveSettings("cid", "sec", "ref", "ROOT")


class FakeDrive:
    def __init__(self):
        self.folders, self.uploaded = [], []

    def ensure_folder(self, parent, name):
        self.folders.append((parent, name))
        return f"{parent}/{name}"

    def list(self, folder_id):
        return [DriveFile("1", "01.png", "image/png", 1)]

    def download(self, file_id, dest):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"x")

    def upload(self, path, folder_id):
        self.uploaded.append((path.name, folder_id))
        return "F"


def test_folder_cached_and_upload_into_it(tmp_path):
    drive = FakeDrive()
    cloud = Cloud(SETTINGS, "롱폼", drive=drive)
    assert cloud.fetch("YT-1", tmp_path / "a") == ["01.png"]
    (tmp_path / "ep.mp4").write_bytes(b"v")
    assert cloud.upload("YT-1", [tmp_path / "ep.mp4", tmp_path / "ep.srt"]) == "https://drive.google.com/file/d/F/view"
    assert drive.folders == [("ROOT", "롱폼"), ("ROOT/롱폼", "YT-1")]  # 두 번째는 캐시
    assert drive.uploaded == [("ep.mp4", "ROOT/롱폼/YT-1")]


def test_fetch_shared(tmp_path):
    drive = FakeDrive()
    assert Cloud(SETTINGS, "롱폼", drive=drive).fetch_shared("음악", tmp_path) == ["01.png"]
    assert drive.folders == [("ROOT", "음악")]
