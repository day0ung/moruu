"""렌더 파이프라인용 묶음 — 글마다 Drive 자료 폴더(moruu/{쇼츠|롱폼}/{content_id})에서 받고, 결과를 같은 폴더에 올린다."""
from __future__ import annotations

from pathlib import Path

from channels.gdrive.client import DriveClient
from channels.gdrive.sync import folder_path, pull, upload_outputs
from core.config import DriveSettings


class Cloud:
    def __init__(self, settings: DriveSettings, channel_dir: str, drive: DriveClient | None = None):
        self.drive = drive or DriveClient(settings.client_id, settings.client_secret, settings.refresh_token)
        self.root, self.channel_dir = settings.root_id, channel_dir
        self._folders: dict[str, str] = {}

    def folder(self, content_id: str) -> str:
        if content_id not in self._folders:
            self._folders[content_id] = folder_path(self.drive, self.root, self.channel_dir, content_id)
        return self._folders[content_id]

    def fetch(self, content_id: str, dest: Path) -> list[str]:
        return pull(self.drive, self.folder(content_id), dest)

    def fetch_shared(self, name: str, dest: Path) -> list[str]:
        """moruu/{name} (예: 음악) → dest."""
        return pull(self.drive, folder_path(self.drive, self.root, name), dest)

    def upload(self, content_id: str, paths: list[Path]) -> str:
        return upload_outputs(self.drive, self.folder(content_id), paths)
