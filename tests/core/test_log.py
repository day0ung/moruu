import logging

from core.log import setup_logging


def test_secrets_are_masked(caplog):
    log = setup_logging(["SECRET-TOKEN-123"])
    with caplog.at_level(logging.INFO, logger="moruu"):
        log.info("url ?access_token=%s", "SECRET-TOKEN-123")
    assert "SECRET-TOKEN-123" not in caplog.text
    assert "access_token=***" in caplog.text


def test_httpx_request_logs_are_silenced():
    setup_logging([])
    assert logging.getLogger("httpx").level == logging.WARNING
