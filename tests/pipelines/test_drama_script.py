from pipelines.ai_drama.script import (DramaScene, Spoken, attach_images, find_music, parse_episode,
                                       script_problems)


def rt(text):
    return [{"plain_text": text, "annotations": {}}]


def h2(text):
    return {"type": "heading_2", "heading_2": {"rich_text": rt(text)}}


def para(text):
    return {"type": "paragraph", "paragraph": {"rich_text": rt(text)}}


NAMES = {"내레이션", "시어머니", "아들"}
BLOCKS = [
    {"type": "callout", "callout": {"rich_text": rt("메모")}},
    h2("장면 1 · 저녁 식탁 #음악 잔잔"),
    para("그날 저녁, 시어머니는 말없이 상을 차렸다.\n시어머니(서운하게): 너희 이번 주말에 올 거니?\n\n아들: 회사 일이 좀… [쉼 0.5]"),
    h2("장면 2 · 다음 날"),
    para("시간이 흘러: 봄이 왔다."),
    h2("장면 3 #음악 슬픔"),
    para("끝."),
]


def test_parse_scenes_speakers_and_music_carry():
    scenes, problems = parse_episode(BLOCKS, NAMES)
    assert problems == []
    assert scenes[0] == DramaScene(1, "장면 1 · 저녁 식탁", "잔잔", [
        Spoken("내레이션", "", "그날 저녁, 시어머니는 말없이 상을 차렸다."),
        Spoken("시어머니", "서운하게", "너희 이번 주말에 올 거니?"),
        Spoken("아들", "", "회사 일이 좀… [쉼 0.5]"),
    ])
    assert (scenes[1].title, scenes[1].music, scenes[1].lines) == (
        "장면 2 · 다음 날", "잔잔", [Spoken("내레이션", "", "시간이 흘러: 봄이 왔다.")])
    assert (scenes[2].title, scenes[2].music) == ("장면 3", "슬픔")


def test_unknown_name_and_lines_before_scene():
    scenes, problems = parse_episode([para("앞줄"), h2("장면"), para("며느리: 어머니"), para("결론: 끝")], NAMES)
    assert problems == ["장면 제목 전에 대사 — 첫 줄은 ## 장면 제목", "장면 1: 인물 '며느리' 바이블에 없음",
                        "장면 1: 인물 '결론' 바이블에 없음"]


def test_attach_images_by_number_with_sources(tmp_path):
    for name in ("01.png", "3.jpg", "09.png", "메모.txt", "ep.mp4"):
        (tmp_path / name).write_bytes(b"x")
    (tmp_path / "출처.txt").write_text("AI:Gemini\n03: https://pexels.com/1\n", encoding="utf-8")
    scenes = [DramaScene(n, "t", None, []) for n in (1, 2, 3)]
    assert attach_images(scenes, tmp_path) == ["09.png: 9번 장면 없음"]
    assert (scenes[0].image.name, scenes[0].image_source) == ("01.png", "AI:Gemini")
    assert scenes[1].image is None
    assert (scenes[2].image.name, scenes[2].image_source) == ("3.jpg", "https://pexels.com/1")
    assert attach_images(scenes, tmp_path / "없음") == []


def test_find_music(tmp_path):
    (tmp_path / "잔잔.mp3").write_bytes(b"x")
    (tmp_path / "슬픔.m4a").write_bytes(b"x")
    (tmp_path / "출처.txt").write_text("잔잔: YouTube 오디오 보관함\n", encoding="utf-8")
    music, problems = find_music({"잔잔", "슬픔", "긴장"}, tmp_path)
    assert music == {"잔잔": tmp_path / "잔잔.mp3", "슬픔": tmp_path / "슬픔.m4a"}
    assert problems == ["음악 '긴장' 파일 없음 — 긴장.mp3", "음악 '슬픔' 출처 없음 — 출처.txt 에 적기"]


def test_script_problems(tmp_path):
    ok = DramaScene(1, "a", None, [Spoken("내레이션", "", "좋은 하루")], tmp_path / "01.png", "AI")
    assert script_problems([ok]) == []
    bad = [
        DramaScene(1, "a", None, []),
        DramaScene(2, "b", None, [Spoken("아들", "", "최고 {3M 쓰리엠}")], tmp_path / "02.png", ""),
    ]
    assert script_problems(bad) == [
        "장면 1: 대사 없음",
        "장면 1: 그림 없음 — 01.png",
        "장면 2: 02.png 출처 없음 — 출처.txt 에 적기",
        "장면 2: 읽는 법 {글자|읽기} 형식 오류",
        "장면 2: 금지어 최고",
    ]
    assert script_problems([]) == ["장면 없음 — 본문에 ## 장면 제목과 대사"]
