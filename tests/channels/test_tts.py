import base64
import json

import httpx
import pytest

from channels.tts.google import BASE, GoogleTTS, Part, TTSError, Word, build_ssml
from channels.tts.srt import to_srt


def make(handler):
    http = httpx.Client(base_url=BASE, transport=httpx.MockTransport(handler))
    return GoogleTTS("SECRET-KEY", http=http)


def test_build_ssml_marks_each_part_and_escapes():
    assert build_ssml([Part("A&B"), Part("<c>")]) == (
        '<speak><mark name="0"/>A&amp;B <mark name="1"/>&lt;c&gt;<mark name="end"/></speak>')


def test_build_ssml_pause_after_part():
    assert build_ssml([Part("가 나", 0.5), Part("다")]) == (
        '<speak><mark name="0"/>가 나<break time="500ms"/> <mark name="1"/>다<mark name="end"/></speak>')


def test_synthesize_parts_times_each_part():
    def handler(req):
        assert "<break" in json.loads(req.content)["input"]["ssml"]
        return httpx.Response(200, json={
            "audioContent": base64.b64encode(b"MP3").decode(),
            "timepoints": [{"markName": "0", "timeSeconds": 0.0}, {"markName": "1", "timeSeconds": 1.4},
                           {"markName": "end", "timeSeconds": 2.0}],
        })

    s = make(handler).synthesize_parts([Part("가스레인지 모서리,", 0.3), Part("닦기")], "ko-KR-Neural2-A")
    assert s.words == [Word("가스레인지 모서리,", 0.0), Word("닦기", 1.4)] and s.end == 2.0


def test_synthesize_parts_rejects_all_empty():
    with pytest.raises(ValueError):
        make(lambda req: httpx.Response(200)).synthesize_parts([Part("", 1.0)], "ko-KR-Neural2-A")


def test_synthesize_request_and_timings():
    seen = {}

    def handler(req):
        seen["path"] = req.url.path
        seen["key_in_url"] = "SECRET-KEY" in str(req.url)
        seen["header"] = req.headers["X-Goog-Api-Key"]
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={
            "audioContent": base64.b64encode(b"MP3").decode(),
            "timepoints": [
                {"markName": "0", "timeSeconds": 0.1},
                {"markName": "1", "timeSeconds": 0.5},
                {"markName": "end", "timeSeconds": 1.2},
            ],
        })

    s = make(handler).synthesize("현관 우산", "ko-KR-Neural2-A", rate=1.1)
    assert seen["path"] == "/v1beta1/text:synthesize"
    assert not seen["key_in_url"] and seen["header"] == "SECRET-KEY"
    assert seen["body"]["voice"] == {"languageCode": "ko-KR", "name": "ko-KR-Neural2-A"}
    assert seen["body"]["audioConfig"]["speakingRate"] == 1.1
    assert seen["body"]["enableTimePointing"] == ["SSML_MARK"]
    assert s.audio == b"MP3"
    assert s.words == [Word("현관", 0.1), Word("우산", 0.5)]
    assert s.end == 1.2


def test_missing_timepoints_gives_no_words():
    def handler(req):
        return httpx.Response(200, json={"audioContent": base64.b64encode(b"x").decode()})

    s = make(handler).synthesize("가 나", "ko-KR-Chirp3-HD-Aoede")
    assert s.words == [] and s.end is None


def test_error_has_status_and_no_key():
    def handler(req):
        return httpx.Response(403, json={"error": {"status": "PERMISSION_DENIED", "message": "API not enabled"}})

    with pytest.raises(TTSError) as e:
        make(handler).synthesize("가", "ko-KR-Neural2-A")
    assert e.value.code == "PERMISSION_DENIED"
    assert "SECRET-KEY" not in str(e.value)


def test_empty_text_rejected():
    with pytest.raises(ValueError):
        make(lambda req: httpx.Response(200)).synthesize("  ", "ko-KR-Neural2-A")


def test_voices_sorted():
    def handler(req):
        assert req.url.params["languageCode"] == "ko-KR"
        return httpx.Response(200, json={"voices": [
            {"name": "ko-KR-Neural2-C", "ssmlGender": "MALE"},
            {"name": "ko-KR-Neural2-A", "ssmlGender": "FEMALE"},
        ]})

    assert make(handler).voices() == [("ko-KR-Neural2-A", "FEMALE"), ("ko-KR-Neural2-C", "MALE")]


def test_srt_groups_words_and_uses_next_start():
    words = [Word("a", 0.0), Word("b", 0.4), Word("c", 0.8), Word("d", 1.25)]
    assert to_srt(words, end=1.9, per=3) == (
        "1\n00:00:00,000 --> 00:00:01,250\na b c\n\n"
        "2\n00:00:01,250 --> 00:00:01,900\nd\n"
    )


def test_srt_without_end_adds_tail():
    assert "00:00:01,000 --> 00:00:01,600" in to_srt([Word("a", 1.0)], end=None)


def test_cues_match_srt_timing():
    from channels.tts.srt import Cue, cues
    words = [Word("a", 0.0), Word("b", 0.4), Word("c", 0.8), Word("d", 1.25)]
    assert cues(words, end=1.9, per=3) == [Cue(0.0, 1.25, "a b c"), Cue(1.25, 1.9, "d")]


def test_line_cues_use_first_part_of_each_line():
    from channels.tts.narration import Line
    from channels.tts.srt import Cue, line_cues
    lines = [Line("가 나", (Part("가", 0.5), Part("나"))), Line("다", (Part("다"),))]
    words = [Word("가", 0.0), Word("나", 0.9), Word("다", 1.6)]
    assert line_cues(lines, words, 2.4) == [Cue(0.0, 1.6, "가 나"), Cue(1.6, 2.4, "다")]


def test_line_cues_without_timings_split_by_length():
    from channels.tts.narration import Line
    from channels.tts.srt import Cue, line_cues
    lines = [Line("가나다", (Part("가나다"),)), Line("라", (Part("라"),))]
    assert line_cues(lines, [], 2.0) == [Cue(0.0, 1.5, "가나다"), Cue(1.5, 2.0, "라")]


def test_synthesize_parts_sends_pitch_only_when_set():
    sent = []

    def handler(req):
        sent.append(json.loads(req.content)["audioConfig"])
        return httpx.Response(200, json={"audioContent": base64.b64encode(b"MP3").decode(), "timepoints": []})

    tts = make(handler)
    tts.synthesize_parts([Part("가")], "ko-KR-Neural2-A")
    tts.synthesize_parts([Part("가")], "ko-KR-Neural2-A", 0.9, -4.0)
    assert sent == [{"audioEncoding": "MP3", "speakingRate": 1.0},
                    {"audioEncoding": "MP3", "speakingRate": 0.9, "pitch": -4.0}]
