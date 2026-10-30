from pipelines.ai_story import agents
from pipelines.ai_story.agents import Chapter, write_reviewed
from pipelines.ai_story.context import Series
from pipelines.ai_story.doc import PlanText

SERIES = Series("s1", world="소도시", cast=[{"인물": "내레이션"}, {"인물": "아들", "나이·성격": "30대"}])
PLAN = PlanText("기획 전문")
CH = Chapter(1, 8, "저녁", "사건")


def scenes(text="가" * 300, speaker="내레이션"):
    return {"scenes": [{"title": f"s{i}", "music": "", "lines": [{"speaker": speaker, "text": text}]} for i in range(3)]}


class FakeLLM:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def chat_json(self, messages, role):
        self.calls.append((role, messages[-1]["content"]))
        return self.replies.pop(0)


def test_prompt_fills_values_and_marks_empty():
    msgs = agents.prompt("summary", plan="기획", script="")
    assert msgs[0]["role"] == "system" and "창작" in msgs[0]["content"]
    assert "기획" in msgs[1]["content"] and "(없음)" in msgs[1]["content"] and "$plan" not in msgs[1]["content"]


def test_all_prompts_have_no_leftover_variables():
    values = dict.fromkeys(["count", "world", "rules", "cast", "episodes", "topic", "minutes", "chapters", "number",
                            "total", "title", "beats", "plan", "previous", "feedback", "target", "speakers", "music",
                            "script", "scenes"], "x")
    for name in ("plan", "write", "review", "image", "summary"):
        assert "$" not in agents.prompt(name, **values)[1]["content"], name


def test_write_reviewed_passes_first_time():
    llm = FakeLLM([scenes(), {"verdict": "PASS", "notes": []}])
    out, note = write_reviewed(llm, SERIES, PLAN, CH, "", target=900, music=["잔잔"])
    assert len(out) == 3 and note == "챕터 1: PASS (수정 0회)"
    assert [r for r, _ in llm.calls] == ["write", "review"]


def test_mechanical_problem_skips_review_and_feeds_back():
    llm = FakeLLM([scenes(speaker="며느리"), scenes(), {"verdict": "REVISION", "notes": ["장면 2 개연성"]},
                   scenes(), {"verdict": "PASS"}])
    out, note = write_reviewed(llm, SERIES, PLAN, CH, "", target=900, music=[])
    assert note == "챕터 1: PASS (수정 2회)"
    roles = [r for r, _ in llm.calls]
    assert roles == ["write", "write", "review", "write", "review"]
    assert "며느리" in llm.calls[1][1] and "장면 2 개연성" in llm.calls[3][1]  # 지적이 다음 작성 프롬프트에


def test_gives_up_after_three_revisions():
    llm = FakeLLM([scenes(speaker="며느리")] * 4)
    out, note = write_reviewed(llm, SERIES, PLAN, CH, "", target=900, music=[])
    assert note.startswith("⚠ 챕터 1: 검수 미통과 (수정 3회)") and len(llm.calls) == 4


def test_plan_filters_and_limits():
    llm = FakeLLM([{"plans": [{"titles": ["a"], "chapters": [{"title": "c"}]}, {"titles": ["no chapters"]},
                              {"chapters": [{"title": "d"}]}, {"chapters": [{"title": "e"}]}, "junk"]}])
    plans = agents.plan(llm, SERIES, "상속", count=3)
    assert [p["chapters"][0]["title"] for p in plans] == ["c", "d", "e"]
    assert "상속" in llm.calls[0][1] and "아들" in llm.calls[0][1]


def test_image_prompts_pads_to_scene_count():
    llm = FakeLLM([{"prompts": ["하나"]}])
    assert agents.image_prompts(llm, SERIES, scenes()["scenes"]) == ["하나", "", ""]
    assert llm.calls[0][0] == "light"


def test_summarize():
    assert agents.summarize(FakeLLM([{"summary": " 갈등: x "}]), PLAN, "대본") == "갈등: x"
