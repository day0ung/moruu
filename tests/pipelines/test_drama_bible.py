from pipelines.ai_drama.bible import Character, parse_bible

HEAD = ["인물", "나이·성격", "목소리", "높낮이", "빠르기", "자막색"]


def test_columns_by_header_defaults_and_auto_colors():
    cast, problems = parse_bible([[HEAD,
                                   ["내레이션", "", "ko-KR-Neural2-A", "", "0.95", ""],
                                   ["시어머니", "68세", "ko-KR-Neural2-A", "-4", "", ""],
                                   ["아들", "", "ko-KR-Neural2-C", "", "", "#7fd3ff"],
                                   ["며느리", "", "ko-KR-Neural2-B", "2", "1.1", "분홍"],
                                   ["", "", "", "", "", ""]]], default_rate=1.0)
    assert problems == []
    assert cast == {
        "내레이션": Character("내레이션", "ko-KR-Neural2-A", 0.0, 0.95, "#FFFFFF"),
        "시어머니": Character("시어머니", "ko-KR-Neural2-A", -4.0, 1.0, "#FFD400"),
        "아들": Character("아들", "ko-KR-Neural2-C", 0.0, 1.0, "#7FD3FF"),
        "며느리": Character("며느리", "ko-KR-Neural2-B", 2.0, 1.1, "#FF9EC4"),
    }


def test_auto_colors_skip_used_ones():
    cast, _ = parse_bible([[["인물", "목소리", "자막색"], ["내레이션", "V", ""], ["갑", "V", "노랑"], ["을", "V", ""]]], 1.0)
    assert cast["을"].color == "#7FD3FF"


def test_problems():
    cast, problems = parse_bible([[["인물", "목소리", "높낮이", "빠르기", "자막색"],
                                   ["아들", "", "30", "abc", "검정"]]], 1.0)
    assert problems == [
        "바이블: 아들 목소리 없음",
        "바이블: 아들 높낮이 -20~20 아님 (30)",
        "바이블: 아들 빠르기 0.25~4.0 아님 (abc)",
        "바이블: 아들 자막색 모름 (검정) — 흰색·노랑·하늘·연두·분홍·주황·보라 또는 #RRGGBB",
        "바이블: 내레이션 줄 없음",
    ]


def test_no_table():
    assert parse_bible([[["글자", "읽기"]]], 1.0) == ({}, ["바이블 표 없음 — 머리글에 인물·목소리 칸"])
