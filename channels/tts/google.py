"""Google Cloud Text-to-Speech (v1beta1) — 음성 mp3 + 단어별 시작 시각.

단어마다 SSML <mark> 를 넣고 enableTimePointing 으로 시각을 받는다 (자막 싱크용).
키는 헤더(X-Goog-Api-Key)로만 보낸다 — URL 에 남지 않게.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from xml.sax.saxutils import escape

import httpx

BASE = "https://texttospeech.googleapis.com"
END_MARK = "end"


class TTSError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Word:
    text: str
    start: float  # 초


@dataclass(frozen=True)
class Speech:
    audio: bytes  # mp3
    words: list[Word]
    end: float | None  # 마지막 단어가 끝난 시각 (모르면 None)


def build_ssml(words: list[str]) -> str:
    body = " ".join(f'<mark name="{i}"/>{escape(w)}' for i, w in enumerate(words))
    return f'<speak>{body}<mark name="{END_MARK}"/></speak>'


def _raise_for_error(r: httpx.Response) -> None:
    if not r.is_error:
        return
    try:
        err = r.json().get("error") or {}
    except (ValueError, AttributeError):
        err = {}
    raise TTSError(str(err.get("status") or r.status_code), str(err.get("message") or r.reason_phrase))


class GoogleTTS:
    def __init__(self, api_key: str, http: httpx.Client | None = None):
        self._http = http or httpx.Client(base_url=BASE, timeout=60)
        self._headers = {"X-Goog-Api-Key": api_key}

    def synthesize(self, text: str, voice: str, rate: float = 1.0) -> Speech:
        words = text.split()
        if not words:
            raise ValueError("빈 대본")
        body = {
            "input": {"ssml": build_ssml(words)},
            "voice": {"languageCode": "-".join(voice.split("-")[:2]), "name": voice},
            "audioConfig": {"audioEncoding": "MP3", "speakingRate": rate},
            "enableTimePointing": ["SSML_MARK"],
        }
        r = self._http.post("/v1beta1/text:synthesize", json=body, headers=self._headers)
        _raise_for_error(r)
        data = r.json()
        marks = {t["markName"]: float(t.get("timeSeconds", 0)) for t in data.get("timepoints", [])}
        timed = [Word(w, marks[str(i)]) for i, w in enumerate(words) if str(i) in marks]
        return Speech(
            audio=base64.b64decode(data["audioContent"]),
            words=timed if len(timed) == len(words) else [],
            end=marks.get(END_MARK),
        )

    def voices(self, language: str = "ko-KR") -> list[tuple[str, str]]:
        r = self._http.get("/v1/voices", params={"languageCode": language}, headers=self._headers)
        _raise_for_error(r)
        return sorted((v["name"], v.get("ssmlGender", "")) for v in r.json().get("voices", []))
