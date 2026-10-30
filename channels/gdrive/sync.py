"""Drive 폴더 ↔ 로컬 폴더. 렌더 자료를 받고(pull) 결과를 올린다(upload_outputs)."""
from __future__ import annotations

from pathlib import Path

from channels.gdrive.client import FOLDER_MIME, DriveClient, file_url

OUTPUT_EXT = (".mp4", ".srt")  # 결과 파일 — 자료로 받지 않는다


def folder_path(drive: DriveClient, root_id: str, *names: str) -> str:
    folder = root_id
    for name in names:
        folder = drive.ensure_folder(folder, name)
    return folder


def pull(drive: DriveClient, folder_id: str, dest: Path) -> list[str]:
    """폴더 바로 아래 파일을 dest 로. 같은 크기의 파일이 이미 있으면 건너뛴다."""
    got = []
    for f in drive.list(folder_id):
        if f.mime == FOLDER_MIME or Path(f.name).suffix.lower() in OUTPUT_EXT:
            continue
        local = dest / f.name
        if local.is_file() and local.stat().st_size == f.size:
            continue
        drive.download(f.id, local)
        got.append(f.name)
    return got


def upload_outputs(drive: DriveClient, folder_id: str, paths: list[Path]) -> str:
    """있는 파일만 올리고 첫 파일(mp4)의 링크."""
    links = [file_url(drive.upload(p, folder_id)) for p in paths if p.is_file()]
    return links[0]
