"""시리즈 맥락 — 세계관·금지 규칙·인물 표·지난 회차 요약. 기획·대본·검수 프롬프트에 그대로 넣는다."""
from __future__ import annotations

from dataclasses import dataclass, field

from pipelines.ai_story.doc import NARRATOR, plain

MALE_HINTS = ("남성", "남자", "아들", "아버지", "할아버지", "남편", "형", "오빠", "삼촌", "사위", "시아버지")
VOICE_FEMALE, VOICE_MALE = "ko-KR-Neural2-A", "ko-KR-Neural2-C"


@dataclass
class Series:
    id: str
    world: str = ""
    rules: str = ""
    table_id: str = ""
    header: list[str] = field(default_factory=list)
    cast: list[dict[str, str]] = field(default_factory=list)  # 인물 표 한 줄 = {머리글: 값}
    episodes: list[str] = field(default_factory=list)  # 지난 회차 요약

    @property
    def names(self) -> set[str]:
        return {c.get("인물", "") for c in self.cast if c.get("인물")} | {NARRATOR}

    def cast_text(self) -> str:
        out = []
        for c in self.cast:
            if c.get("인물") and c["인물"] != NARRATOR:
                parts = [c.get("나이·성격", ""), ("외형: " + c["그림 설명"]) if c.get("그림 설명") else ""]
                out.append(f"- {c['인물']}: " + " / ".join(p for p in parts if p))
        return "\n".join(out) or "(없음)"

    def episodes_text(self) -> str:
        return "\n".join(f"{i}. {s}" for i, s in enumerate(self.episodes, 1)) or "(첫 회차)"

    def new_rows(self, characters: list[tuple[str, str]]) -> list[list[str]]:
        """기획안 '이번 회차 인물' 중 바이블에 없는 사람 → 인물 표 줄 (머리글 순서)."""
        rows = []
        for name, desc in characters:
            if name in self.names:
                continue
            voice = VOICE_MALE if any(h in name + desc for h in MALE_HINTS) else VOICE_FEMALE
            values = {"인물": name, "목소리": voice, "나이·성격": desc}
            rows.append([values.get(h, "") for h in self.header])
            self.cast.append(values)
        return rows


def _sections(blocks: list[dict]) -> dict[str, str]:
    """## 제목 아래 문단·목록 글자."""
    out: dict[str, list[str]] = {}
    current = None
    for b in blocks:
        kind = b.get("type", "")
        text = plain(b).strip()
        if kind.startswith("heading_"):
            current = text
            out[current] = []
        elif current and text and kind in ("paragraph", "bulleted_list_item", "numbered_list_item", "quote", "callout"):
            out[current].append(("- " if kind.endswith("list_item") else "") + text)
    return {k: "\n".join(v) for k, v in out.items()}


def load_series(store, series_id: str, exclude_page: str = "") -> Series:
    blocks = store.page_blocks(series_id)
    sections = _sections(blocks)
    s = Series(series_id,
               world=next((v for k, v in sections.items() if k.startswith("세계관")), ""),
               rules=next((v for k, v in sections.items() if k.startswith("금지")), ""))
    table = next((t for t in store.tables(series_id) if t.rows and "인물" in t.rows[0]), None)
    if table:
        s.table_id, s.header = table.id, table.rows[0]
        s.cast = [dict(zip(s.header, row)) for row in table.rows[1:] if row and row[0]]
    s.episodes = [p.summary for p in store.series_episodes(series_id) if p.summary and p.page_id != exclude_page]
    return s
