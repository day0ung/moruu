# 오픈소스 참고 저장소 조사 (대본 Agent 파이프라인 중심)

- 조사일: 2026-10-30
- 목적: `docs/ai-agent-plan.md` 의 Planner → Writer → Reviewer → Image Prompt 파이프라인을 만들 때 **배울 점·빌릴 아이디어** 찾기. 렌더러는 이미 있으므로 영상 쪽은 참고만.
- 확인 방법: 각 저장소의 GitHub 페이지와 GitHub REST API(`api.github.com/repos/...`)를 2026-10-30에 직접 조회했다. 코드를 내려받거나 실행하지 않았다.
- 표기
  - **최근 업데이트** = API의 `pushed_at`(어느 브랜치든 마지막 push). ✅ = 2026-07-30 이후(최근 3개월 안), ⚠️ = 그보다 오래됨
  - **★** = 2026-10-30 기준 스타 수 (포크는 아래 "부가 확인" 표)
  - 페이지에서 확인하지 못한 값은 **미확인**
- 공통 결과: 조사한 저장소 중 **README에 Notion 또는 Google Drive 연동이 적힌 곳은 하나도 없었다.** 이 부분은 moruu가 직접 만든다.

---

## [1] 롱폼 / 스토리텔링 자동화 (장편 대본 일관성)

| 저장소(링크) | 최근 업데이트 | ★ | 언어 | 라이선스 | 영상까지? | 유료 API | moruu에 쓸 점 |
|---|---|---|---|---|---|---|---|
| [leenbj/novel-creator-skill](https://github.com/leenbj/novel-creator-skill) | 2026-03-10 ⚠️ | 701 | Python(스크립트) + 스킬 문서 | README에는 "MIT", API·루트 LICENSE 파일은 미확인 | 아니오 (원고만) | Claude Code·Codex·Gemini CLI 등 에이전트 CLI 사용 (구독/API) | 장마다 `novel_plan.md`·`novel_state.md` 같은 **기억 파일**을 읽고 쓰고, 5단계 **품질 게이트**(기억 갱신→일관성→문체→교정→게이트)를 통과해야 다음 장으로 넘어간다. 검토 최대 3회, 쓰는 모델과 검토하는 모델을 다르게 둔다 |
| [datacrystals/AIStoryWriter](https://github.com/datacrystals/AIStoryWriter) | 2025-11-24 ⚠️ | 259 | Python | AGPL-3.0 | 아니오 | 기본은 Ollama(로컬, 무료). Gemini·OpenRouter도 선택 가능 | **단계마다 모델을 따로 지정**(전체 개요 / 장 개요 / 장 본문 / 수정). `Writer/` 안이 `OutlineGenerator`·`LLMEditor`·`Scrubber`·`Chapter/`·`Scene/` 으로 나뉘어 있어 Agent를 나눌 때 참고할 만하다 |
| [YILING0013/AI_NovelGenerator](https://github.com/YILING0013/AI_NovelGenerator) | 2026-10-16 ✅ | 6,363 | Python (+ Next.js 프론트) | AGPL-3.0 | 아니오 | 사용자가 정한 LLM 엔드포인트 (특정 회사로 고정 안 됨) | 권 → 아크 → 장면 → 장 계획 → 본문 순서로 내려가고, 장마다 인물·관계·아이템·세계관 규칙이 바뀐 기록을 남긴 뒤 "장 검사" 워크플로를 돈다. 지금은 MongoDB·Docker를 쓰는 무거운 앱으로 바뀌어서 구조만 참고 |
| [MaoXiaoYuZ/Long-Novel-GPT](https://github.com/MaoXiaoYuZ/Long-Novel-GPT) | 2025-11-05 ⚠️ | 1,251 | Python | 없음 (`license: null`) | 아니오 | OpenAI 호환 API, 문심(ERNIE)·豆包(Doubao), 로컬 모델 | 개요 → 장 → 본문 순서로 내려가고, 쓰는 동안 관련 본문과 줄거리 요약을 검색(RAG)해 고친 뒤 **요약을 다시 갱신**한다. 앞 장 요약을 넘겨주는 방식에 바로 참고 |
| [facebookresearch/doc-storygen-v2](https://github.com/facebookresearch/doc-storygen-v2) | 2026-05-13 ⚠️ | 94 | Python | README에는 Apache 2.0, API 값은 NOASSERTION | 아니오 | vLLM(로컬)이 기본이고 OpenAI도 가능 | DOC 논문(ACL 2023) 코드의 개정판. **Premise → Plan → Story** 3단계를 JSON으로 저장해서 **사람이 Plan을 고친 다음** 이어서 쓸 수 있다. Notion DRAFT 검토 흐름과 같은 생각 |
| [yangkevin2/doc-story-generation](https://github.com/yangkevin2/doc-story-generation) | 미확인 | 161 | Python | MIT | 아니오 | OpenAI GPT-3, OPT-175B(Alpa) | 위 저장소의 원본(연구용). 지금은 쓰기 어렵고, 개요를 여러 층으로 나누고 재순위(reranker)를 매긴다는 **개념**만 참고 |
| [stanford-oval/storm](https://github.com/stanford-oval/storm) | 2025-09-30 ⚠️ | 31,749 | Python | MIT | 아니오 (위키형 글) | LLM은 litellm 경유로 아무거나. 검색 API(You.com·Bing·Tavily 등, DuckDuckGo·SearXNG도 가능) | 조사 → 개요 → 본문 → 다듬기(중복 제거) 4단계의 대표 구현. "개요를 먼저 만들고 쓴다"와 "마지막에 중복을 지운다"는 Reviewer의 반복 문장 검수와 맞는다 |
| [THUDM/LongWriter](https://github.com/THUDM/LongWriter) | 2025-06-24 ⚠️ | 1,879 | Python | Apache-2.0 | 아니오 | 미확인 (API 키를 설정 파일에 넣음) | `agentwrite/` 가 `plan.py` → `write.py` 2단계로 긴 글을 만든다. 8,000~10,000자 분량을 맞출 때 **계획 단계에서 단락별 분량을 먼저 정하는** 방식의 근거 (단락별 글자 수 배분은 논문 기준이고 README로는 미확인) |

## [2] AI Agent 콘텐츠 제작 (Agent 구조·모델 교체·캐릭터 일관성)

| 저장소(링크) | 최근 업데이트 | ★ | 언어 | 라이선스 | 영상까지? | 유료 API | moruu에 쓸 점 |
|---|---|---|---|---|---|---|---|
| [BerriAI/litellm](https://github.com/BerriAI/litellm) | 2026-10-30 ✅ | 62,333 | Python | API 값 NOASSERTION (본체는 MIT로 알려져 있고 enterprise 폴더만 별도. 직접 확인 필요) | 해당 없음 (LLM 호출 라이브러리) | 없음 (호출하는 회사의 요금만) | `services/ai_client.py` 하나로 Gemini·OpenAI·Ollama 등을 **모델 이름만 바꿔** 호출. 직접 만들 거라면 인터페이스 설계만 참고 |
| [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph) | 2026-10-29 ✅ | 44,130 | Python | MIT | 해당 없음 (프레임워크) | 없음 | 상태 그래프 + 조건 분기로 Reviewer → Writer 되돌림(최대 3회)을 표현하고, **체크포인트**로 실패한 단계부터 다시 돌린다. 의존성이 부담되면 패턴만 빌려 순수 Python으로 |
| [crewAIInc/crewAI](https://github.com/crewAIInc/crewAI) | 2026-10-29 ✅ | 60,272 | Python | MIT | 해당 없음 (프레임워크) | 없음 | 역할(role)·목표(goal)·과업(task) 단위로 Agent를 정의하는 방식. `prompts/*.txt` 와 Agent 클래스를 나눌 때 참고 |
| [HKUDS/ViMax](https://github.com/HKUDS/ViMax) | 2026-09-30 ✅ | 12,801 | Python | MIT | 예 (Idea2Video·Script2Video·Novel2Video) | 채팅 LLM(OpenRouter 예시), Google 이미지 API, Google Veo 영상 API (요금은 README에 없음) | Novel2Video의 **인물 추적·장면 계획**, 참조 이미지·첫 프레임을 맞춘 일관성 관리. Image Prompt Agent의 "인물 설정표(character bible)" 설계에 참고. uv 기반이라 구조가 비슷하다 |
| [ArcReel/ArcReel](https://github.com/ArcReel/ArcReel) | 2026-10-29 ✅ | 5,905 | Python | AGPL-3.0 (+ NOTICE 추가 조건) | 예 (최종 합성 또는 剪映 초안) | 텍스트·이미지·영상·TTS 공급자를 설정에서 고름. 정확한 회사와 요금은 미확인 (생성 전후 비용 추적 기능 있음) | 소설·대본 → 인물·장면·소품 **에셋을 먼저 만들고**, 그 이미지를 이후 스토리보드의 참조로 재사용한다. 단계마다 사람이 확인하고 개별 재생성·롤백할 수 있는 구조 |

## [3] 영상 생성·렌더링 (참고만, 이미 렌더러 있음)

| 저장소(링크) | 최근 업데이트 | ★ | 언어 | 라이선스 | 영상까지? | 유료 API | moruu에 쓸 점 |
|---|---|---|---|---|---|---|---|
| [harry0703/MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) | 2026-10-30 ✅ | 136,341 | Python | MIT | 예 (9:16·16:9·1:1, YouTube Shorts 업로드 기능 있다고 적힘) | LLM 여러 곳 선택(Gemini·OpenAI·DeepSeek·Ollama 등). TTS는 Edge TTS(키 없음) 외 ElevenLabs 등. 소재는 Pexels·Pixabay | 자막 시간을 **TTS 타임스탬프로 맞추는 방식**과 faster-whisper 방식을 둘 다 제공. `uv sync` 와 CLI(`cli.py`)가 있어 구조 비교에 좋다 |
| [RayVentura/ShortGPT](https://github.com/RayVentura/ShortGPT) | 2025-02-10 ⚠️ | 8,089 | Python | MIT | 예 (쇼츠, 긴 영상 엔진, 번역 더빙) | OpenAI, ElevenLabs, Pexels, Bing Image (Edge TTS 선택 가능) | LLM이 다루기 쉬운 **편집 마크업(JSON 블록)** 개념. 스스로 "Experimental"이라 부르고 갱신이 멈춤 |
| [alecm20/story-flicks](https://github.com/alecm20/story-flicks) | 2025-03-12 ⚠️ | 2,538 | Python (+ 프론트) | 없음 (`license: null`) | 예 (이야기 → 구간별 이미지 → 음성·자막 → 영상) | 텍스트: OpenAI·Aliyun·DeepSeek·SiliconFlow·Ollama / 이미지: DALL·E 3·Flux | "구간 1개 = 이미지 1장" 구조. 인물 일관성 처리는 README에 없음 → 우리가 보완해야 하는 지점 확인용 |
| [Zulko/moviepy](https://github.com/Zulko/moviepy) | 2026-08-26 ✅ | 15,055 | Python | MIT | 라이브러리 | 없음 | ffmpeg 직접 호출 대신 쓸 수 있는 Python 편집 API. 지금 렌더러를 바꿀 필요는 없음 |
| [remotion-dev/remotion](https://github.com/remotion-dev/remotion) | 2026-10-29 ✅ | 68,941 | TypeScript | 자체 라이선스 (API 값 NOASSERTION. 일정 규모 이상 회사는 유료 라이선스로 알려져 있으니 확인 필요) | 라이브러리 (React로 영상) | 없음 (라이선스 비용은 별도) | 템플릿형 화면(자막 카드·인트로)을 코드로 만드는 방식. Node 스택이라 moruu에는 참고만 |

## [4] GitHub Actions 자동화

| 저장소(링크) | 최근 업데이트 | ★ | 언어 | 라이선스 | 영상까지? | 유료 API | moruu에 쓸 점 |
|---|---|---|---|---|---|---|---|
| [ChaitanyaEswarRajeshJakki/gemini-youtube-automation](https://github.com/ChaitanyaEswarRajeshJakki/gemini-youtube-automation) | 2026-10-29 ✅ | 371 | Python | README에는 MIT, API 값은 없음 (`null`) | 예 (16:9 + 9:16 렌더, YouTube 자동 업로드) | Gemini API(Gemini 2.5 Flash), gTTS, Pexels, YouTube Data API | **매일 Actions cron**으로 실행하고, 진행 상태(`content_plan.json`)를 **레포에 다시 커밋**한다. Secrets 4개만으로 돌아가는 구성. moruu는 상태를 Notion에 두니 "실패 후 이어하기" 설계만 참고 (자동 공개 업로드는 moruu 규칙과 맞지 않음) |
| [google-github-actions/run-gemini-cli](https://github.com/google-github-actions/run-gemini-cli) | 2026-08-21 ✅ | 2,113 | TypeScript | Apache-2.0 | 아니오 | Gemini API 또는 Vertex (무료 한도는 가입할 때 확인) | Actions 안에서 Gemini를 부르는 공식 Action. 우리는 Python에서 직접 호출하겠지만 **Secrets·권한 설정 예시**로 참고 |
| [actions/ai-inference](https://github.com/actions/ai-inference) | 2026-10-29 ✅ | 521 | TypeScript | MIT | 아니오 | 지금 README 기준으로 **Copilot CLI 전용**(Copilot 토큰 필요). 소개 문구는 아직 "GitHub Models"라고 되어 있어 서로 안 맞음 | `.prompt.yml` 로 프롬프트를 파일로 관리하고 `{{변수}}` 를 넣는 형식. `prompts/` 폴더 형식을 정할 때 참고. Copilot 구독이 필요하면 비용 목표와 맞지 않음 |

### 부가 확인 항목 (포크·설치 안내·Actions·Notion/Drive)

| 저장소 | 포크 | README 설치 안내 | GitHub Actions | Notion / Drive |
|---|---|---|---|---|
| novel-creator-skill | 130 | 있음 (설치 스크립트 + 수동 복사) | 미확인 | 없음 |
| AIStoryWriter | 65 | 있음 (경로가 실제 폴더와 조금 다름) | 워크플로 미확인 | 없음 |
| AI_NovelGenerator | 1,101 | 있음 (Python 3.13, Node 24, Docker, MongoDB) | `.github/` 에 CONTRIBUTING만 보임, 워크플로 미확인 | 없음 |
| Long-Novel-GPT | 206 | 있음 (Docker) | 미확인 | 없음 |
| doc-storygen-v2 | 17 | 있음 (vLLM 패치 필요) | 미확인 | 없음 |
| doc-story-generation | 23 | 있음 | 미확인 | 없음 |
| storm | 2,997 | 있음 (`pip install knowledge-storm`) | 미확인 | 없음 |
| LongWriter | 186 | 있음 | 미확인 | 없음 |
| litellm | 12,833 | 있음 | 미확인 | 없음 |
| langgraph | 7,588 | 있음 | 미확인 | 없음 |
| crewAI | 8,952 | 있음 | 미확인 | 없음 |
| ViMax | 1,938 | 있음 (`uv sync`) | 미확인 | 없음 |
| ArcReel | 1,175 | 있음 (Docker Compose) | 테스트 워크플로만 (배지) | 없음 |
| MoneyPrinterTurbo | 21,702 | 있음 (pip·Docker·uv·Windows 패키지) | `.github` 있음, 내용 미확인 | 없음 |
| ShortGPT | 1,169 | 있음 (Colab·Docker) | 미확인 | 없음 |
| story-flicks | 448 | 있음 (conda·Docker) | 미확인 | 없음 |
| moviepy | 2,131 | 있음 | 미확인 | 없음 |
| remotion | 5,639 | 있음 | 미확인 | 없음 |
| gemini-youtube-automation | 193 | 있음 (Secrets 4개) | **있음 (매일 07:00 UTC)** | 없음 |
| run-gemini-cli | 289 | 있음 | 그 자체가 Action | 없음 |
| ai-inference | 72 | 있음 (예시 워크플로) | 그 자체가 Action | 없음 |

### 제외한 것 (이유)

- `FujiwaraChoki/MoneyPrinterV2` (★32,253, AGPL-3.0): 콜드 아웃리치·제휴 마케팅·트위터 봇이 섞여 있고 README에 업로드 방식이 적혀 있지 않음. moruu 규칙(대가성 표기, 탐지 회피 금지)과 방향이 다르다.
- `linyqh/NarratoAI` (★11,621, MIT): 기존 영상에 해설을 붙여 편집하는 도구라서 창작 대본 파이프라인과 맞지 않음.
- `EnVision-Research/VideoMemory` (★14), `Rohan5commit/finance-video-agent` (★0): 아직 너무 작음.
- `naqashafzal/AI-Content-Studio` (★885): 지금은 클리핑·해설 쪽으로 바뀌었고, 자동 업로드인지 README끼리 말이 다름.

---

## TOP 5 추천과 이유 (대본 Agent 파이프라인 기준)

1. **leenbj/novel-creator-skill**: 계획서의 Reviewer와 거의 같은 설계다. "기억 파일(계획·현재 상태)을 읽고 → 쓰고 → 일관성·문체·교정 게이트를 통과해야 다음 장"이라는 흐름, 검토 최대 3회, 쓰는 모델과 검토 모델을 나누는 방식을 그대로 빌릴 수 있다. moruu에서는 `story_state`(인물 이름·나이·관계, 깔아 둔 복선, 장별 요약)를 JSON으로 두고 매 장 끝에 갱신하면 된다. LICENSE 파일을 확인하지 못했으니 **아이디어만** 쓴다.
2. **facebookresearch/doc-storygen-v2**: Premise → Plan → Story 를 **JSON 파일로 끊어서 사람이 중간에 고칠 수 있게** 했다. "Planner 결과를 Notion DRAFT로 먼저 올리고, 사람이 손본 기획으로 Writer를 돌리는" 2단계 운영(Actions 실행 시간도 나뉜다)의 근거로 좋다.
3. **datacrystals/AIStoryWriter**: 전체 개요 / 장 개요 / 장 본문 / 수정에 **서로 다른 모델**을 쓴다. 비싼 모델은 Planner·Reviewer에만, 장 본문은 Gemini Flash 같은 싼 모델로 쓰는 식의 비용 절감 설계에 바로 쓸 수 있다. AGPL이라 코드는 가져오지 않는다.
4. **BerriAI/litellm** (+ 필요하면 LangGraph): "모델 교체 가능" 요구를 가장 적은 코드로 해결한다. Gemini 무료 한도 → OpenAI → Ollama 로 모델 이름만 바꿔 호출. 의존성을 줄이려면 `ai_client.py` 에 `complete(messages, model)` 인터페이스만 두고 Gemini·OpenAI 어댑터 두 개만 직접 짜도 된다. Reviewer 되돌림(최대 3회)과 실패 지점부터 다시 돌리기는 LangGraph의 상태 그래프·체크포인트 패턴을 참고한다.
5. **HKUDS/ViMax** (MIT): Novel2Video의 인물 추적·장면 계획, 참조 이미지 기반 일관성 관리. Image Prompt Agent에서 **인물 설정표(나이·얼굴·머리·옷·자주 나오는 장소)를 한 번 정하고 장면마다 그대로 붙이는** 방식의 근거. MIT라 코드 일부를 빌리는 것도 가능(저작권 고지 유지).

> 덧붙임: 분량(8,000~10,000자)을 맞출 때는 LongWriter처럼 **계획 단계에서 장별 목표 글자 수를 정하고** Writer가 그 숫자를 받게 하는 것이 효과적이다. STORM의 "마지막 다듬기에서 중복 제거" 단계는 Reviewer의 반복 문장 검사로 옮길 수 있다.

---

## 주의

### 라이선스
- **AGPL-3.0** (AIStoryWriter, AI_NovelGenerator, ArcReel, MoneyPrinterV2): 코드를 복사해 넣으면 moruu 전체가 AGPL 의무를 질 수 있다(네트워크 서비스로 제공해도 해당). **구조·프롬프트 아이디어만 참고하고 코드는 옮기지 않는다.**
- **라이선스 없음** (Long-Novel-GPT, story-flicks, gemini-youtube-automation은 API 값 기준, novel-creator-skill은 LICENSE 파일 미확인): 법적으로는 "모든 권리 보유"로 본다. 코드 복사 금지, 아이디어만.
- **MIT / Apache-2.0** (storm, ViMax, langgraph, crewAI, MoneyPrinterTurbo, ShortGPT, moviepy, LongWriter, doc-story-generation 등): 빌려 써도 되지만 저작권·라이선스 고지를 남긴다. Apache-2.0은 NOTICE 파일과 변경 사항 표시도 지킨다.
- **Remotion**: 회사 규모에 따라 유료 라이선스가 필요한 자체 라이선스로 알려져 있다. 쓸 일이 생기면 그때 조건을 확인한다.
- **LiteLLM**: API가 NOASSERTION이라고 표시한다. `enterprise/` 폴더 조건이 따로 있을 수 있으니 쓰기 전에 LICENSE를 확인한다.
- MoneyPrinterTurbo README는 **번들 BGM이 YouTube 영상에서 왔다**고 적고 있다. 남의 저장소에 든 음원·이미지를 그대로 쓰지 않는다.

### 서비스 약관(ToS)
- **Edge TTS·gTTS**는 공식 유료 API가 아니라 브라우저·번역기 기능을 그대로 부르는 비공식 방식이다. 약관상 상업 이용이 애매하다. moruu는 지금처럼 Google Cloud TTS(공식 API)를 유지한다.
- 무료 LLM 한도(Gemini 무료 등)는 **무료 한도 입력이 모델 개선에 쓰일 수 있다**는 약관이 붙는 경우가 있다. 개인정보가 들어간 사연 원문은 넣지 않는다. 한도와 조건은 실제 가입할 때 확인한다 (계획서 8장과 같음).
- 브라우저 자동화로 업로드하거나 프록시로 우회하는 저장소(예: faceless-channel 토픽의 일부)는 참고하지 않는다. CLAUDE.md의 "탐지 회피 설계 금지", "YouTube는 비공개 업로드 → 사람이 공개"를 지킨다.

### YouTube "진정성 없는 콘텐츠(inauthentic content)" 정책
- YouTube 파트너 프로그램은 **대량으로 찍어 내거나 반복적인 콘텐츠**를 수익 창출에서 뺀다 (2025년 7월에 기존 "반복적인 콘텐츠" 항목 이름을 바꾸고 범위를 더 분명히 함). 같은 틀에 이름만 바꾼 사연을 매일 올리는 방식은 이 정책에 직접 걸린다.
  - 대응: Reviewer에 **"이전 회차와 소재·전개가 겹치는지" 검사**를 넣고, 사람이 대본을 실제로 고치는 단계(APPROVED)를 형식으로만 두지 않는다. 업로드 횟수를 늘리는 것보다 회차마다 차이를 두는 쪽으로 설계한다.
- **사실처럼 보이는 합성·변형 콘텐츠는 공개 표시(라벨) 대상**이 될 수 있다. AI로 만든 창작 사연을 "실화"라고 소개하지 않는다. 설명란에 **"창작/각색된 이야기이며 AI 도구로 제작"** 같은 문구를 넣는다 (CLAUDE.md의 "써보지 않은 경험을 1인칭으로 쓰지 않는다"와 같은 취지).
- 실제 인물·사건을 소재로 쓰면 명예훼손·초상권 위험이 있다. Planner 프롬프트에 "실존 인물·실명·특정 가능한 정보 금지"를 넣는다.
- 정책 문구와 세부 기준은 바뀔 수 있으니 공개 전에 YouTube 고객센터의 최신 수익 창출 정책을 다시 확인한다.

---

## 원래 검색 링크 (GitHub 저장소 검색)

- [youtube long form automation](https://github.com/search?q=youtube+long+form+automation&type=repositories)
- [AI storytelling pipeline](https://github.com/search?q=AI+storytelling+pipeline&type=repositories)
- [AI story generator](https://github.com/search?q=AI+story+generator&type=repositories)
- [youtube storytelling automation](https://github.com/search?q=youtube+storytelling+automation&type=repositories)
- [long form video generator](https://github.com/search?q=long+form+video+generator&type=repositories)
- [multi agent content generation](https://github.com/search?q=multi+agent+content+generation&type=repositories)
- [AI script writer agent](https://github.com/search?q=AI+script+writer+agent&type=repositories)
- [autonomous content creation](https://github.com/search?q=autonomous+content+creation&type=repositories)
- [langgraph content generation](https://github.com/search?q=langgraph+content+generation&type=repositories)
- [AI video automation](https://github.com/search?q=AI+video+automation&type=repositories)
- [remotion AI video](https://github.com/search?q=remotion+AI+video&type=repositories)
- [moviepy automation](https://github.com/search?q=moviepy+automation&type=repositories)
- [text to video pipeline](https://github.com/search?q=text+to+video+pipeline&type=repositories)
- [github actions AI automation](https://github.com/search?q=github+actions+AI+automation&type=repositories)
- [AI drama generator](https://github.com/search?q=AI+drama+generator&type=repositories)
- [multi agent video production](https://github.com/search?q=multi+agent+video+production&type=repositories)
- [Python YouTube automation](https://github.com/search?q=Python+YouTube+automation&type=repositories)
- 참고 토픽: [faceless-channel](https://github.com/topics/faceless-channel), [youtube-automation (Python)](https://github.com/topics/youtube-automation?l=python&o=desc&s=stars)
