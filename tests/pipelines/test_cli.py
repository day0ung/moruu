import pipelines.threads_post.__main__ as cli
from core.config import REQUIRED


def test_dry_run_without_config_exits_1_and_never_calls_network(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "ROOT", tmp_path)  # 실제 .env 로드 방지
    for key in REQUIRED:
        monkeypatch.delenv(key, raising=False)

    assert cli.main(["--dry-run"]) == 1
    assert "환경변수 없음" in capsys.readouterr().err
