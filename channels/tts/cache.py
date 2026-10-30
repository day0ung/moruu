"""TTS 결과를 줄 단위로 저장해 두고 같은 입력이면 다시 부르지 않는다 (.cache/tts/{sha256}.mp3 + .json)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Protocol

from channels.tts.google import Part, Speech, Word


class PartsTTS(Protocol):
    def synthesize_parts(self, parts: list[Part], voice: str, rate: float = 1.0, pitch: float = 0.0) -> Speech: ...


class CachedTTS:
    def __init__(self, inner: PartsTTS, folder: Path, provider: str = "google"):
        self.inner, self.folder, self.provider = inner, folder, provider

    def _key(self, parts: list[Part], voice: str, rate: float, pitch: float) -> str:
        raw = json.dumps([self.provider, voice, rate, pitch, [[p.text, p.pause_after] for p in parts]],
                         ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()

    def synthesize_parts(self, parts: list[Part], voice: str, rate: float = 1.0, pitch: float = 0.0) -> Speech:
        key = self._key(parts, voice, rate, pitch)
        mp3, meta = self.folder / f"{key}.mp3", self.folder / f"{key}.json"
        if mp3.is_file() and meta.is_file():
            data = json.loads(meta.read_text(encoding="utf-8"))
            return Speech(mp3.read_bytes(), [Word(t, s) for t, s in data["words"]], data["end"])
        speech = self.inner.synthesize_parts(parts, voice, rate, pitch)
        self.folder.mkdir(parents=True, exist_ok=True)
        mp3.write_bytes(speech.audio)
        # json 을 마지막에 쓴다 — 중간에 끊기면 캐시로 안 친다
        meta.write_text(json.dumps({"words": [[w.text, w.start] for w in speech.words], "end": speech.end},
                                   ensure_ascii=False), encoding="utf-8")
        return speech
