from datetime import datetime

from core import schema as S
from core.models import KST, parse_post


def sample_page(**props):
    base = {
        "content_id": {"title": [{"plain_text": "TH-LIVING-20261101-001"}]},
        "채널": {"select": {"name": "Threads"}},
        "역할": {"select": {"name": "수익"}},
        "본문": {"rich_text": [{"plain_text": "좁은 집 "}, {"plain_text": "수납 팁"}]},
        "링크": {"url": "https://link.coupang.com/a/abc"},
        "대가성문구": {"rich_text": [{"plain_text": "쿠팡 파트너스 활동의 일환으로 수수료를 제공받습니다."}]},
        "status": {"select": {"name": "APPROVED"}},
        "예약시각": {"date": {"start": "2026-11-01T08:00:00.000+09:00"}},
        "게시시각": {"date": None},
        "게시ID": {"rich_text": []},
        "수집_24h": {"checkbox": True},
        "수집_72h": {"checkbox": False},
        "수집_7d": {"checkbox": False},
    }
    base.update(props)
    return {"id": "page-1", "properties": base}


def test_parse_post_reads_properties():
    p = parse_post(sample_page())
    assert p.page_id == "page-1"
    assert p.content_id == "TH-LIVING-20261101-001"
    assert p.role == "수익"
    assert p.text == "좁은 집 수납 팁"
    assert p.link == "https://link.coupang.com/a/abc"
    assert p.scheduled_at == datetime(2026, 11, 1, 8, 0, tzinfo=KST)
    assert p.posted_at is None
    assert p.media_id is None
    assert p.collected == frozenset({24})


def test_date_without_time_is_kst():
    p = parse_post(sample_page(**{"예약시각": {"date": {"start": "2026-11-01"}}}))
    assert p.scheduled_at.tzinfo == KST


def test_empty_link_is_none():
    assert parse_post(sample_page(**{"링크": {"url": None}})).link is None


def test_builders_shape():
    assert S.select("POSTED") == {"select": {"name": "POSTED"}}
    assert S.rich("x") == {"rich_text": [{"text": {"content": "x"}}]}
    assert S.checkbox(True) == {"checkbox": True}


def test_voice_defaults_empty_and_reads_select():
    assert parse_post(sample_page()).voice == ""
    assert parse_post(sample_page(**{"목소리": {"select": {"name": "남"}}})).voice == "남"


def test_series_relation_first_id():
    page = sample_page(**{"시리즈": {"relation": [{"id": "series-1"}, {"id": "series-2"}]}})
    assert parse_post(page).series == "series-1"
    assert parse_post(sample_page()).series == ""


def test_channel_and_media_folder():
    p = parse_post(sample_page(**{"채널": {"select": {"name": "YT-롱폼"}}, "자료 폴더": {"url": "https://d/f"}}))
    assert (p.channel, p.media_folder) == ("YT-롱폼", "https://d/f")
    assert parse_post(sample_page(**{"자료 폴더": {"url": None}})).media_folder == ""


def test_episode_summary():
    p = parse_post(sample_page(**{"회차 요약": {"rich_text": [{"plain_text": "갈등: 상속"}]}}))
    assert p.summary == "갈등: 상속"
