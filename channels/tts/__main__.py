"""python -m channels.tts "대본" [--out out/tts/sample] [--voice ...] [--rate 1.1] | --list-voices"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from channels.tts.google import GoogleTTS, TTSError
from channels.tts.srt import to_srt
from core.log import setup_logging

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VOICE = "ko-KR-Neural2-A"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tts")
    ap.add_argument("text", nargs="?", help="대본 (띄어쓰기 단위로 자막 시각을 잡음)")
    ap.add_argument("--out", default="out/tts/sample", help="확장자 없이 — .mp3/.srt 가 붙음")
    ap.add_argument("--voice")
    ap.add_argument("--rate", type=float)
    ap.add_argument("--list-voices", action="store_true", help="쓸 수 있는 한국어 목소리 목록")
    args = ap.parse_args(argv)

    load_dotenv(ROOT / ".env")
    key = os.environ.get("GOOGLE_TTS_API_KEY", "")
    if not key:
        print("환경변수 없음: GOOGLE_TTS_API_KEY", file=sys.stderr)
        return 1
    log = setup_logging([key])
    tts = GoogleTTS(key)

    try:
        if args.list_voices:
            for name, gender in tts.voices():
                print(name, gender)
            return 0
        if not args.text:
            ap.error("대본이 필요합니다")
        voice = args.voice or os.environ.get("TTS_VOICE") or DEFAULT_VOICE
        rate = args.rate or float(os.environ.get("TTS_RATE") or 1.0)
        speech = tts.synthesize(args.text, voice, rate)
    except TTSError as e:
        log.error("Google TTS 오류: %s", e)
        return 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".mp3").write_bytes(speech.audio)
    if speech.words:
        out.with_suffix(".srt").write_text(to_srt(speech.words, speech.end), encoding="utf-8")
    else:
        log.warning("이 목소리는 단어 시각을 주지 않음 — 자막(.srt) 생략: %s", voice)
    log.info("저장: %s (%s, 속도 %s)", out.with_suffix(".mp3"), voice, rate)
    return 0


if __name__ == "__main__":
    sys.exit(main())
