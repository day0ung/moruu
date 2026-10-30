"""렌더할 영상 한 편의 설계도 — 장면마다 그림·음악·줄 음성·자막과 시각. JSON 으로 저장해 검토·재사용한다.

장면 안의 시각(Clip.start, Subtitle.start/stop)은 장면 시작 기준. 전체 시각은 장면 길이를 차례로 더한다.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from channels.tts.srt import Cue, cues_to_srt


@dataclass(frozen=True)
class Clip:
    audio: Path
    start: float


@dataclass(frozen=True)
class Subtitle:
    text: str
    color: str  # #RRGGBB
    start: float
    stop: float


@dataclass(frozen=True)
class Scene:
    number: int
    title: str
    image: Path
    music: Path | None
    duration: float
    clips: tuple[Clip, ...]
    subtitles: tuple[Subtitle, ...]


@dataclass(frozen=True)
class Timeline:
    width: int
    height: int
    scenes: tuple[Scene, ...]

    @property
    def size(self) -> tuple[int, int]:
        return self.width, self.height

    def starts(self) -> list[float]:
        out, t = [], 0.0
        for s in self.scenes:
            out.append(t)
            t += s.duration
        return out

    @property
    def total(self) -> float:
        return sum(s.duration for s in self.scenes)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=1, default=lambda p: Path(p).as_posix())

    @classmethod
    def from_json(cls, text: str) -> Timeline:
        d = json.loads(text)
        return cls(d["width"], d["height"], tuple(
            Scene(s["number"], s["title"], Path(s["image"]), Path(s["music"]) if s["music"] else None,
                  s["duration"], tuple(Clip(Path(c["audio"]), c["start"]) for c in s["clips"]),
                  tuple(Subtitle(**x) for x in s["subtitles"]))
            for s in d["scenes"]))

    def to_srt(self) -> str:
        cues = [Cue(t + x.start, t + x.stop, x.text) for t, s in zip(self.starts(), self.scenes) for x in s.subtitles]
        return cues_to_srt(cues)
