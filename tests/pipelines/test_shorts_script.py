from channels.video.frames import Span
from pipelines.shopping_shorts.script import Cut, attach_folder, parse_cuts, script_problems


def rt(*parts):
    """rt("가", ("강조", True)) → Notion rich_text 배열."""
    out = []
    for p in parts:
        text, bold = (p, False) if isinstance(p, str) else p
        out.append({"plain_text": text, "annotations": {"bold": bold}})
    return out


def h2(text):
    return {"type": "heading_2", "heading_2": {"rich_text": rt(text)}}


def para(*parts):
    return {"type": "paragraph", "paragraph": {"rich_text": rt(*parts)}}


def quote(*parts):
    return {"type": "quote", "quote": {"rich_text": rt(*parts)}}


def image(url, caption="AI:ChatGPT", hosted=True):
    body = {"type": "file", "file": {"url": url}} if hosted else {"type": "external", "external": {"url": url}}
    return {"type": "image", "image": {**body, "caption": rt(caption) if caption else []}}


def code(text):
    return {"type": "code", "code": {"rich_text": rt(text)}}


BLANK = para()

BLOCKS = [
    {"type": "callout", "callout": {"rich_text": rt("작업 순서")}},
    h2("메모"),
    code("이미지 프롬프트 ..."),
    image("https://s3/1.png"),
    quote("가스레인지 모서리 ", ("기름때", True)),
    para("가스레인지 모서리, 닦기 불편하셨죠?"),
    BLANK,
    quote("이럴 땐 ", ("얇은 솔", True)),
    para("이럴 땐 {3M|쓰리엠} 같은 얇은 솔을 써 보세요. #남\n틈에 대고 문질러요. #4초"),
]


def test_parse_cuts_image_caption_lines_and_tags():
    assert parse_cuts(BLOCKS) == [
        Cut(1, [Span("가스레인지 모서리 ", False), Span("기름때", True)], ["가스레인지 모서리, 닦기 불편하셨죠?"],
            image_url="https://s3/1.png", image_source="AI:ChatGPT"),
        Cut(2, [Span("이럴 땐 ", False), Span("얇은 솔", True)],
            ["이럴 땐 {3M|쓰리엠} 같은 얇은 솔을 써 보세요.", "틈에 대고 문질러요."], voice="남", seconds=4.0),
    ]


def test_image_starts_new_cut_and_quote_after_lines_starts_new_cut():
    cuts = parse_cuts([
        para("하나"), image("https://x/2.jpg", "https://pexels.com/1", hosted=False), para("둘"),
        quote("셋 문구"), para("셋"),
    ])
    assert [(c.number, c.lines, c.image_url, c.caption_text) for c in cuts] == [
        (1, ["하나"], None, ""), (2, ["둘"], "https://x/2.jpg", ""), (3, ["셋"], None, "셋 문구"),
    ]
    assert cuts[1].image_source == "https://pexels.com/1"


def test_blank_lines_separate_cuts_and_repeat_blanks_are_ignored():
    cuts = parse_cuts([BLANK, para("하나"), BLANK, BLANK, para("둘"), para("둘 다음 줄")])
    assert [c.lines for c in cuts] == [["하나"], ["둘", "둘 다음 줄"]]


def test_kind_and_narration():
    cut = Cut(1, lines=["가", "나"])
    assert (cut.kind, cut.narration) == ("카드", "가 나")
    assert Cut(1, image_url="u").kind == "이미지"


def test_attach_folder_by_number_with_sources(tmp_path):
    for name in ("01.png", "03.jpg", "04.mp4", "09.png", "메모.txt"):
        (tmp_path / name).write_bytes(b"x")
    (tmp_path / "출처.txt").write_text("AI:ChatGPT\n03: https://pexels.com/9\n", encoding="utf-8")
    cuts = [Cut(1, lines=["a"], image_url="https://s3/n.png", image_source="notion"), Cut(2, lines=["b"]),
            Cut(3, lines=["c"]), Cut(4, lines=["d"])]
    problems = attach_folder(cuts, tmp_path)
    assert cuts[0].image_path is None and cuts[0].image_source == "notion"  # Notion 이미지가 먼저
    assert cuts[1].image_path is None
    assert (cuts[2].image_path.name, cuts[2].image_source) == ("03.jpg", "https://pexels.com/9")
    assert problems == ["04.mp4: 영상 컷은 아직 지원 안 함", "09.png: 9번 컷 없음"]


def test_attach_folder_default_source_and_missing_folder(tmp_path):
    (tmp_path / "1.png").write_bytes(b"x")
    (tmp_path / "출처.txt").write_text("AI:Gemini\n", encoding="utf-8")
    cuts = [Cut(1, lines=["a"])]
    assert attach_folder(cuts, tmp_path) == []
    assert (cuts[0].kind, cuts[0].image_source) == ("이미지", "AI:Gemini")
    assert attach_folder(cuts, tmp_path / "없음") == []


def test_valid_script_has_no_problems():
    assert script_problems(parse_cuts(BLOCKS), disclosure="쿠팡 파트너스 활동") == []


def test_problems_listed(tmp_path):
    cuts = parse_cuts([
        image("https://s3/1.png", caption=""), quote("주방 필수템"),
        BLANK, para("최고예요 {3M 쓰리엠}"),
        BLANK, quote("가" * 31), para("넷"),
    ])
    cuts.append(Cut(4, lines=["다섯"], image_path=tmp_path / "04.png"))
    assert script_problems(cuts, disclosure="") == [
        "컷 1: 대사 없음",
        "컷 1: 이미지 캡션에 출처 없음",
        "컷 1: 금지어 필수",
        "컷 2: 읽는 법 {글자|읽기} 형식 오류",
        "컷 2: 금지어 최고",
        "컷 3: 화면 문구 30자 초과 (31자)",
        "컷 4: 04.png 출처 없음 — 출처.txt 에 적기",
        "대가성문구 비어 있음",
    ]


def test_no_cuts_is_a_problem():
    assert script_problems([], disclosure="x") == ["컷 없음 — 본문에 대사를 쓰고, 컷 사이는 빈 줄"]
