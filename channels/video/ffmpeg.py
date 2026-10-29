"""ffmpeg 합성 — 장면 하나씩 세그먼트 mp4 로 만든 뒤 이어 붙인다.

ffmpeg 는 imageio-ffmpeg 가 내려받은 실행 파일을 쓴다 (회사 PC 에 설치 불필요).
자막은 PNG overlay 로 넣는다 — 이 빌드의 libass 에 기대지 않음.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import imageio_ffmpeg

from channels.video.frames import H, W

FPS = 30
ZOOM = 0.08  # 이미지 장면: 1.0 → 1.08 천천히 확대
_ENCODE = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
           "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"]


class VideoError(Exception):
    pass


@dataclass(frozen=True)
class Overlay:
    png: Path
    start: float | None = None  # None = 장면 내내
    stop: float | None = None


def segment_args(out: Path, background: Path, audio: Path, duration: float,
                 overlays: list[Overlay], zoom: bool) -> list[str]:
    args = ["-y", "-loop", "1", "-framerate", str(FPS), "-t", f"{duration:.3f}", "-i", str(background),
            "-i", str(audio)]
    for o in overlays:
        args += ["-loop", "1", "-framerate", str(FPS), "-t", f"{duration:.3f}", "-i", str(o.png)]

    base = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
    if zoom:
        frames = max(1, round(duration * FPS))
        # 2배로 키운 뒤 zoompan — 원본 크기에서 하면 떨림이 보인다
        base += (f",scale={W * 2}:{H * 2},zoompan=z='1+{ZOOM}*on/{frames}'"
                 f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS}")
    chain = [f"[0:v]{base},setsar=1,format=yuv420p[v0]"]
    for i, o in enumerate(overlays):
        enable = "" if o.start is None else f":enable='between(t,{o.start:.3f},{o.stop:.3f})'"
        chain.append(f"[v{i}][{i + 2}:v]overlay=0:0{enable}[v{i + 1}]")
    chain.append("[1:a]apad[a]")

    return args + ["-filter_complex", ";".join(chain), "-map", f"[v{len(overlays)}]", "-map", "[a]",
                   "-t", f"{duration:.3f}", *_ENCODE, str(out)]


def concat_args(list_file: Path, out: Path) -> list[str]:
    return ["-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", "-movflags", "+faststart", str(out)]


def run(args: list[str]) -> str:
    """ffmpeg 실행. 실패하면 stderr 끝부분을 담아 VideoError."""
    p = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise VideoError("ffmpeg 실패: " + " | ".join(p.stderr.strip().splitlines()[-3:]))
    return p.stderr


def make_segment(out: Path, background: Path, audio: Path, duration: float,
                 overlays: list[Overlay], zoom: bool) -> Path:
    run(segment_args(out, background, audio, duration, overlays, zoom))
    return out


def concat(segments: list[Path], out: Path) -> Path:
    list_file = out.with_suffix(".txt")
    list_file.write_text("".join(f"file '{s.resolve().as_posix()}'\n" for s in segments), encoding="utf-8")
    run(concat_args(list_file, out))
    return out


def media_duration(path: Path) -> float:
    """ffmpeg -i 출력의 Duration 으로 길이(초). ffprobe 가 없어서."""
    p = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-i", str(path)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", p.stderr)
    if not m:
        raise VideoError(f"길이를 알 수 없음: {path.name}")
    h, mnt, s = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(s)
