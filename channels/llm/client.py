"""AI 글쓰기 모델 — OpenAI 호환 /chat/completions 를 httpx 로 직접 부른다 (Gemini·OpenRouter 등).

서비스는 순서대로 시도한다. 한도(429)·서버 오류(5xx, 1번 다시 시도 후)면 다음 서비스로.
역할(plan·write·review·light)마다 모델을 따로 둔다. 그 역할 모델이 없는 서비스는 건너뛴다.
키는 헤더로만 보내고 오류·로그에 넣지 않는다. 프롬프트 내용도 로그에 남기지 않는다.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field

import httpx

log = logging.getLogger("moruu")
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


class LLMError(Exception):
    pass


class LLMQuotaError(LLMError):
    """모든 서비스가 한도·서버 오류 — 나중에 다시."""


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    key: str
    models: dict[str, str] = field(default_factory=dict)  # 역할 → 모델


@dataclass(frozen=True)
class Reply:
    text: str
    provider: str
    model: str
    tokens: int


def extract_json(text: str):
    """응답에서 JSON 하나를 꺼낸다 — ```json 울타리 안, 아니면 처음 나오는 { 또는 [ 부터."""
    for candidate in [m.group(1) for m in _FENCE.finditer(text)] + [text]:
        candidate = candidate.strip()
        try:
            return json.loads(candidate)
        except ValueError:
            pass
        for i, ch in enumerate(candidate):
            if ch in "{[":
                try:
                    return json.JSONDecoder().raw_decode(candidate[i:])[0]
                except ValueError:
                    continue
    raise ValueError("JSON 없음")


def _message(r: httpx.Response) -> str:
    try:
        body = r.json()
    except ValueError:
        body = None
    if isinstance(body, list) and body:  # Gemini 는 [{"error": …}] 로 줄 때가 있다
        body = body[0]
    err = body.get("error") if isinstance(body, dict) else None
    if isinstance(err, dict):
        return str(err.get("message") or err)
    return str(err or r.reason_phrase)


class LLM:
    def __init__(self, providers: list[Provider], http: httpx.Client | None = None, retry_wait: float = 5.0,
                 temperature: float = 0.9):
        self.providers = providers
        self._http = http or httpx.Client(timeout=300)
        self._wait = retry_wait
        self.temperature = temperature

    def _call(self, p: Provider, model: str, messages: list[dict]) -> httpx.Response:
        body = {"model": model, "messages": messages, "temperature": self.temperature}
        return self._http.post(p.base_url.rstrip("/") + "/chat/completions", json=body,
                               headers={"Authorization": f"Bearer {p.key}"})

    def chat(self, messages: list[dict], role: str) -> Reply:
        tried = []
        for p in self.providers:
            model = p.models.get(role)
            if not model or not p.key:
                continue
            for attempt in (0, 1):
                try:
                    r = self._call(p, model, messages)
                except httpx.TransportError as e:
                    r = None
                    reason = type(e).__name__
                if r is not None and not r.is_error:
                    data = r.json()
                    text = data["choices"][0]["message"].get("content") or ""
                    tokens = int((data.get("usage") or {}).get("total_tokens") or 0)
                    log.info("AI %s/%s %s 토큰 %d", p.name, model, role, tokens)
                    return Reply(text, p.name, model, tokens)
                if r is not None:
                    reason = f"{r.status_code} {_message(r)}"
                    if r.status_code == 429:
                        break  # 한도 — 기다려도 안 풀린다고 보고 다음 서비스
                    if r.status_code < 500:
                        raise LLMError(f"{p.name}/{model}: {reason}")
                if attempt == 0:
                    time.sleep(self._wait)
            log.warning("AI %s 실패: %s — 다음 서비스", p.name, reason)
            tried.append(f"{p.name}: {reason}")
        raise LLMQuotaError("모든 AI 서비스 실패 — " + "; ".join(tried) if tried else f"'{role}' 모델이 설정된 서비스 없음")

    def chat_json(self, messages: list[dict], role: str):
        """JSON 응답. 못 꺼내면 한 번 더 요청 (JSON 만 달라고 덧붙여서)."""
        reply = self.chat(messages, role)
        try:
            return extract_json(reply.text)
        except ValueError:
            again = messages + [{"role": "assistant", "content": reply.text},
                                {"role": "user", "content": "형식이 틀렸습니다. 설명 없이 JSON 하나만 다시 주세요."}]
            try:
                return extract_json(self.chat(again, role).text)
            except ValueError as e:
                raise LLMError(f"JSON 응답 아님 ({role})") from e
