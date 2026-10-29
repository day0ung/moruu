from channels.video.frames import Span
from pipelines.shopping_shorts.script import Scene, parse_scenes, script_problems


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


def image(url, caption="AI:ChatGPT", hosted=True):
    body = {"type": "file", "file": {"url": url}} if hosted else {"type": "external", "external": {"url": url}}
    return {"type": "image", "image": {**body, "caption": rt(caption) if caption else []}}


def code(text):
    return {"type": "code", "code": {"rich_text": rt(text)}}


BLOCKS = [
    {"type": "callout", "callout": {"rich_text": rt("작업 순서")}},
    h2("0. 공통 스타일 (처음 한 번)"),
    code("지금부터 ..."),
    {"type": "divider", "divider": {}},
    h2("장면 1 · 이미지"),
    para("후킹 (0~3초)"),
    code("장면 1: 가스레인지 ..."),
    image("https://s3/1.png"),
    para("⬇ 장면 1 그림을 여기에 올리기"),
    para("화면: 가스레인지 모서리 ", ("기름때", True)),
    para("내레이션: 가스레인지 모서리, 닦기 불편하셨죠?"),
    h2("장면 2 · 카드"),
    para("화면: 틈에 대고 ", ("여러 번", True)),
    para("내레이션: 솔 끝을 틈에 대고 문질러요."),
]


def test_parse_scenes_reads_kind_caption_narration_image():
    scenes = parse_scenes(BLOCKS)
    assert scenes == [
        Scene(1, "이미지", [Span("가스레인지 모서리 ", False), Span("기름때", True)],
              "가스레인지 모서리, 닦기 불편하셨죠?", "https://s3/1.png", "AI:ChatGPT"),
        Scene(2, "카드", [Span("틈에 대고 ", False), Span("여러 번", True)], "솔 끝을 틈에 대고 문질러요."),
    ]


def test_external_image_and_non_scene_heading_ends_scene():
    scenes = parse_scenes([
        h2("장면 1 · 이미지"), image("https://pexels/x.jpg", "https://pexels.com/photo/1", hosted=False),
        para("내레이션: 하나"), h2("메모"), para("내레이션: 무시"),
    ])
    assert scenes[0].image_url == "https://pexels/x.jpg"
    assert scenes[0].image_source == "https://pexels.com/photo/1"
    assert scenes[0].narration == "하나"


def test_valid_script_has_no_problems():
    assert script_problems(parse_scenes(BLOCKS), disclosure="쿠팡 파트너스 활동") == []


def test_problems_listed():
    scenes = parse_scenes([
        h2("장면 1 · 이미지"), image("https://s3/1.png", caption=""), para("화면: 주방 필수템"),
        h2("장면 2 · 이미지"), para("내레이션: 최고예요"),
        h2("장면 3 · AI영상"), para("내레이션: 셋"),
        h2("장면 4 · 카드"), para("화면: " + "가" * 31), para("내레이션: 넷"),
    ])
    problems = script_problems(scenes, disclosure="")
    assert problems == [
        "장면 1: 내레이션 없음",
        "장면 1: 이미지 캡션에 출처 없음",
        "장면 1: 금지어 필수",
        "장면 2: 이미지 없음",
        "장면 2: 금지어 최고",
        "장면 3: AI영상 은 아직 지원 안 함",
        "장면 4: 화면 문구 30자 초과 (31자)",
        "대가성문구 비어 있음",
    ]


def test_no_scenes_is_a_problem():
    assert script_problems([], disclosure="x") == ["장면 없음 — '## 장면 N · 카드|이미지' 제목 확인"]
