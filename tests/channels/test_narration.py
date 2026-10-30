from channels.tts.google import Part
from channels.tts.narration import Line, problems, to_lines


def test_plain_line_is_one_line_one_part():
    assert to_lines("닦기 불편하셨죠?", {}, 14) == [Line("닦기 불편하셨죠?", (Part("닦기 불편하셨죠?"),))]


def test_reading_shown_vs_spoken_keeps_attached_josa():
    [line] = to_lines("{3M|쓰리엠}을 써 보세요", {}, 14)
    assert line.shown == "3M을 써 보세요"
    assert line.parts == (Part("쓰리엠을 써 보세요"),)


def test_reading_followed_by_space():
    [line] = to_lines("{3M|쓰리엠} 같은 솔", {}, 14)
    assert (line.shown, line.parts) == ("3M 같은 솔", (Part("쓰리엠 같은 솔"),))


def test_lexicon_applies_outside_braces_longest_first():
    lex = {"3M": "쓰리엠", "M": "엠"}
    [line] = to_lines("3M과 {M|미디엄} 사이즈", lex, 20)
    assert line.shown == "3M과 M 사이즈"
    assert line.parts == (Part("쓰리엠과 미디엄 사이즈"),)


def test_pause_splits_parts_and_is_hidden():
    [line] = to_lines("닦기 불편하셨죠? [쉼 0.5] 오늘은", {}, 30)
    assert line.shown == "닦기 불편하셨죠? 오늘은"
    assert line.parts == (Part("닦기 불편하셨죠?", 0.5), Part("오늘은"))


def test_pause_at_line_end():
    [line] = to_lines("끝 [쉼 1]", {}, 14)
    assert line.parts == (Part("끝", 1.0),)


def test_long_line_splits_once_near_middle_prefers_comma():
    lines = to_lines("가스레인지 모서리, 닦기 정말 불편하셨죠?", {}, 14)
    assert [x.shown for x in lines] == ["가스레인지 모서리,", "닦기 정말 불편하셨죠?"]


def test_long_line_splits_until_short_and_never_inside_reading():
    lines = to_lines("이럴 땐 끝이 얇은 {3M|쓰리엠}표 실리콘 틈새솔을 써 보세요", {}, 10)
    assert all(len(x.shown) <= 10 for x in lines)
    assert any("3M표" in x.shown for x in lines)
    assert " ".join(p.text for x in lines for p in x.parts) == "이럴 땐 끝이 얇은 쓰리엠표 실리콘 틈새솔을 써 보세요"


def test_unsplittable_long_word_stays():
    assert [x.shown for x in to_lines("가" * 20, {}, 14)] == ["가" * 20]


def test_problems_bad_braces_and_pause():
    assert problems("정상 {3M|쓰리엠} [쉼 0.5]") == []
    assert problems("{3M 쓰리엠}") == ["읽는 법 {글자|읽기} 형식 오류"]
    assert problems("닫는 괄호 없음 {3M|쓰리엠") == ["읽는 법 {글자|읽기} 형식 오류"]
    assert problems("[쉼 a]") == ["쉼 [쉼 0.5] 형식 오류"]


def test_split_avoids_one_char_words_like_bound_nouns():
    lines = to_lines("솔 끝을 틈에 대고 여러 번 문질러 주면 돼요.", {}, 16)
    assert [x.shown for x in lines] == ["솔 끝을 틈에 대고", "여러 번 문질러 주면 돼요."]
