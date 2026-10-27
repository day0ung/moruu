"""로깅 — 키·토큰 마스킹. 파이프라인은 항상 "moruu" 로거 하나를 받아 쓴다."""
from __future__ import annotations

import logging
from collections.abc import Iterable


class MaskSecrets(logging.Filter):
    def __init__(self, secrets: Iterable[str]):
        super().__init__()
        self._secrets = [s for s in secrets if s and len(s) >= 8]

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for s in self._secrets:
            msg = msg.replace(s, "***")
        record.msg, record.args = msg, ()
        return True


def setup_logging(secrets: Iterable[str]) -> logging.Logger:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # httpx 는 INFO 에서 요청 URL(토큰 쿼리 포함)을 찍는다
    logging.getLogger("httpx").setLevel(logging.WARNING)
    log = logging.getLogger("moruu")
    log.setLevel(logging.INFO)
    for f in [f for f in log.filters if isinstance(f, MaskSecrets)]:
        log.removeFilter(f)
    log.addFilter(MaskSecrets(secrets))
    return log
