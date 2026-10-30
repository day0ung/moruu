# 무료 LLM API 비교 (대본 Agent용)

작성일: 2026-10-30 · 대상: `docs/ai-agent-plan.md`의 Planner / Writer / Reviewer / Image Prompt Agent

> 표기 규칙: 공식 페이지에서 확인한 값만 그대로 적었다. 공식 페이지에서 확인하지 못한 값은 **미확인**, 서드파티 자료에서만 본 값은 "(서드파티, 미확인)"으로 적었다.
> 무료 한도는 자주 바뀐다. 실제 값은 각 콘솔의 한도 화면에서 다시 확인해야 한다.

## 0. 우리 사용량 (기준)

| 항목 | 값 (추정) |
|---|---|
| 회차당 호출 | 20–40회 (기획 1 + 챕터 8 + 검수·수정 최대 3라운드 + 이미지 프롬프트) |
| 회차당 토큰 | 입력 100–200k, 출력 40–60k |
| 빈도 | 주 2–4회 → 하루 최대 1–2회차 정도 몰릴 수 있음 |
| 챕터 1개 출력 | 한글 약 1,200자. 토큰 수는 토크나이저마다 다르며 대략 1–3k 토큰 수준으로 추정 (**미확인**, 실측 필요) |

→ 출력 한도가 8k 토큰 이상이면 챕터 하나는 한 번에 쓸 수 있다. 실제 병목은 **하루 요청 수(RPD)**와 **분당 토큰 수(TPM)**다.

## 1. 비교표

| 항목 | Google Gemini API (무료 등급) | GitHub Models | Groq (Free) | OpenRouter `:free` | Cloudflare Workers AI | Mistral (Free mode) |
|---|---|---|---|---|---|---|
| 현재 상태 | 사용 가능 | **2026-07-30 서비스 종료** | 사용 가능 | 사용 가능 (무료 모델 목록이 자주 바뀜) | 사용 가능 | 사용 가능 |
| 무료로 쓸 만한 최상위 텍스트 모델 | `gemini-3.8-flash`, `gemini-3.6-flash`, `gemini-3.5-flash-lite` 등 (3.1 Pro Preview는 무료 없음) | — | `openai/gpt-oss-120b`, `llama-3.3-70b-versatile`, `qwen/qwen3.8-27b`(preview) | `google/gemma-4-31b-it:free`, `nvidia/nemotron-3-ultra-550b-a55b:free`, `thinkingmachines/inkling:free` 등 | `@cf/openai/gpt-oss-120b`, `@cf/google/gemma-4-26b-a4b-it` 등 (Kimi·GLM·DeepSeek V4는 유료 플랜 필요) | Mistral Small 4 / Medium 3.5 / Large 4 중 무료 제공 범위 **미확인** |
| 컨텍스트 / 최대 출력 | 1,048,576 / 65,536 (3.5 Flash-Lite, 3.6 Flash, 3.8 Flash) | — | gpt-oss-120b 131,072 / 65,536 | 모델별 (예: gemma-4-31b 262,144 / 32,768) | 모델별 (**미확인**) | **미확인** |
| 분당·일일 한도 | 공식 문서에 숫자 없음. AI Studio 화면에서만 확인 가능 (**미확인**). 프로젝트 단위, 태평양시 자정 리셋 | — | gpt-oss-120b: 30 RPM / 1K RPD / **8K TPM** / **200K TPD** (서드파티, 미확인 — 공식 표는 Developer 플랜 기준으로만 추출됨) | 20 RPM, **50 RPD** (크레딧 10 미만 구매) / 1,000 RPD (10 이상 구매) | 하루 **10,000 Neurons** (UTC 0시 리셋), 무료 모델 300 RPM | 공식 숫자 없음, 콘솔에서만 확인 (**미확인**) |
| 우리 사용량 충족 | 숫자 미확인. 플래시급이면 하루 1–2회차는 가능할 것으로 보이나 **실측 필요** | 불가 | **부족**: TPM 8K라 긴 컨텍스트 호출 1회도 막힐 수 있음. TPD 200K ≈ 하루 1회차 | 50 RPD면 하루 1회차 정도. $10 크레딧 구매 시 여유 | gpt-oss-120b 기준 회차당 약 8,200 Neurons → 하루 1회차 가능. gemma-4-26b는 약 2,700 → 하루 3회차 | **미확인** |
| 학습·데이터 이용 | **무료 등급은 "제품 개선에 사용: 예"**, 사람이 검토할 수 있음 | — | 기본적으로 추론 데이터 미보존, ZDR 설정 가능. 학습 여부는 **미확인** | 모델 제공사마다 다름. 계정 설정에서 무료 모델의 "학습하는 제공사" 허용 여부를 따로 설정 | **학습에 사용하지 않음** | **무료 모드는 기본적으로 학습에 사용**, 관리 콘솔 Privacy에서 끌 수 있음 |
| Actions에서 호출 | API 키 → GitHub Secret. OpenAI 호환 엔드포인트 있음 | — | API 키 (OpenAI 호환) | API 키 (OpenAI 호환) | API 토큰 + 계정 ID. OpenAI 호환 `/ai/v1` 있음 | API 키 |
| 생성물 상업 이용 | Google이 생성물 소유권을 주장하지 않음. 다만 같은·비슷한 출력이 남에게도 나올 수 있음. 18세 이상, 업무 목적 | — | 서비스 약관(Groq Services Agreement) 원문 확인 못함 → **미확인** | 모델별 약관을 따름 → 모델마다 확인 필요 | 출력은 고객 소유. 서드파티 모델 라이선스는 별도 | **미확인** |
| 유료 전환 | 3.8 Flash $0.75 / $3.75 (1M 토큰, 입력/출력, 2026-12-31까지) → 2027-01-01부터 $1.50 / $7.50. 3.5 Flash-Lite $0.30 / $2.50 | Microsoft Foundry로 이전 안내 (가격 **미확인**) | Developer 플랜. 토큰 단가 **미확인** | 유료 모델 사용 (모델별 단가) | Workers Paid, 초과분 $0.011 / 1,000 Neurons | Scale 플랜(종량제). 단가 **미확인** |

## 2. 제공사별 메모

### 2-1. Google Gemini API (AI Studio 키)

- **무료 모델**: 가격표에 무료 등급이 있는 모델은 2.5 Pro, 2.5 Flash, 2.5 Flash-Lite, 3 Flash Preview, 3.1 Flash-Lite, 3.5 Flash-Lite, 3.6 Flash, 3.8 Flash. 3.1 Pro Preview와 Gemini 4 Argon은 무료 등급이 없다.
  - 2.5 계열은 "전에 써 본 사용자만 접근 가능"으로 표시돼 있어 새 프로젝트에서는 3.x Flash 계열을 기준으로 잡는 게 맞다.
  - 3.6 Flash 문서는 "이전 세대 모델이며 최신 Flash는 3.8 Flash"라고 안내한다.
- **컨텍스트/출력**: 3.5 Flash-Lite, 3.6 Flash, 3.8 Flash 모두 입력 1,048,576 / 출력 65,536 토큰. 챕터 하나(1,200자)는 물론 전체 대본(9,500자)도 한 번에 쓸 수 있는 크기다.
- **한도**: rate-limits 문서(2026-10-28 갱신)에 무료 등급 RPM/TPM/RPD 숫자가 없고 "AI Studio에서 확인"으로 안내한다 → **미확인**. 한도는 API 키가 아니라 **프로젝트 단위**이고, RPD는 태평양시 자정에 리셋된다. 서드파티 글들은 2.5 Flash 기준 10 RPM / 250 RPD 등 서로 다른 숫자를 적고 있어 믿기 어렵다.
- **데이터**: 가격표의 "Used to improve our products"가 무료 등급은 거의 모두 **Yes**, 유료는 No. 약관상 무료(Unpaid Services) 입력·출력은 Google 제품과 ML 개선에 쓰이며, 계정과 분리한 뒤 사람이 읽고 주석을 달 수 있다. "민감·기밀·개인 정보는 보내지 말 것". 우리 대본은 창작물이라 큰 문제는 아니지만 **미공개 대본이 Google 학습 데이터가 될 수 있다**는 점은 받아들여야 한다.
- **지역**: 지원 지역 목록에 South Korea가 있다. 단, EEA·스위스·영국 사용자에게 서비스를 제공할 때는 유료만 써야 한다 (우리는 해당 없음).
- **상업 이용**: 생성물 소유권을 주장하지 않는다. 다만 같은·비슷한 결과가 다른 사람에게도 생성될 수 있다. 서비스는 업무·사업 목적용, 18세 이상만 쓸 수 있다.
- **Actions**: AI Studio API 키를 Secret에 넣고 호출. OpenAI 호환 base URL `https://generativelanguage.googleapis.com/v1beta/openai/`가 있어 공급자를 바꾸기 쉽다.
- **유료 전환 비용 (회차당 대략, 입력 0.2M + 출력 0.06M 기준)**: 3.8 Flash 약 $0.38 (2027년부터 약 $0.75), 3.5 Flash-Lite 약 $0.21. 주 4회차면 월 $1.5–3 수준 (계산값, 토큰 수는 추정).

### 2-2. GitHub Models

- **2026-07-30에 완전 종료**됐다. 공식 문서: "playground, model catalog, inference API, BYOK는 어떤 고객도 더 이상 쓸 수 없다." 6월에 신규 고객을 막았고, 7월 16·23일 일시 중단(brownout)을 거쳐 종료.
- 따라서 `GITHUB_TOKEN` + `models: read` 방식은 **더 이상 쓸 수 없다**. 공식 안내 대체재는 Microsoft Foundry와 GitHub Copilot. Foundry 무료 한도와 Copilot을 Actions 스크립트에서 LLM API처럼 쓸 수 있는지는 **미확인**.
- `docs/ai-agent-plan.md`나 다른 자료에 GitHub Models가 무료 옵션으로 적혀 있다면 빼야 한다.

### 2-3. Groq

- **모델**: 정식 모델은 `openai/gpt-oss-120b`, `openai/gpt-oss-20b`(131,072 / 65,536), `llama-3.3-70b-versatile`(131,072 / 32,768), `llama-3.1-8b-instant`. Preview는 `qwen/qwen3.8-27b`, `minimaxai/minimax-m2.7` 등. Preview는 "평가용, 운영용 아님".
- **한도**: 공식 rate-limits 페이지에서 Free 탭 값을 추출하지 못했다. 서드파티 자료가 공통으로 gpt-oss-120b 무료 30 RPM / 1K RPD / 8K TPM / 200K TPD라고 적는다 (**미확인**). 공식 페이지에서 확인된 Developer 플랜 기본값도 gpt-oss-120b 30 / 1K / 8K / 200K로 적혀 있어, 실제 값은 콘솔 Limits에서 확인해야 한다.
- **우리 용도와의 맞음**: 8K TPM이면 기획서와 앞 챕터를 붙인 입력 10k 토큰짜리 요청 하나도 분당 한도를 넘을 수 있다. 200K TPD면 하루 1회차가 한계다. **Writer 주력으로는 부족하고**, 짧은 Reviewer 체크나 비상용 정도로만 쓸 만하다.
- **데이터**: 기본적으로 추론 입력·출력을 보존하지 않는다 (장애·악용 조사 목적으로 최대 30일 임시 로그 가능). 모든 고객이 Zero Data Retention을 켤 수 있다. 학습 사용 여부는 공식 문서에서 찾지 못함 → **미확인**.
- **상업 이용·유료 단가**: Groq Services Agreement 원문을 확인하지 못함 → **미확인**.

### 2-4. OpenRouter (`:free` 모델)

- **한도 (공식)**: 무료 모델은 20 RPM. 하루 50회 (누적 크레딧 구매 10 미만) / 1,000회 (10 이상 구매). 크레딧을 사도 분당 한도는 그대로이고 일일 한도만 올라간다.
- **현재 무료 텍스트 모델 (2026-10-30, `/api/v1/models` 조회)**: `google/gemma-4-31b-it:free`, `google/gemma-4-26b-a4b-it:free`(262,144 / 32,768), `nvidia/nemotron-3-ultra-550b-a55b:free`(1,000,000 / 65,536), `nvidia/nemotron-3.5-super-vl:free`, `thinkingmachines/inkling:free`(1,048,576 / 262,144), `dots-studio/dots-3-note-preview:free` 등. 무료 모델은 예고 후 사라지는 경우가 있다 (예: HeyGen 음성 무료 모델 "2026-11-30 종료" 표시).
- **우리 용도와의 맞음**: 50 RPD면 하루 1회차(최대 40회 호출)로 거의 꽉 찬다. $10어치 크레딧을 한 번 사면 1,000 RPD라 여유가 생긴다. 무료 모델 쪽은 공급자 혼잡 때문에 429가 자주 난다는 보고가 있다 (**미확인**).
- **데이터**: 학습 여부는 모델 제공사 정책을 따른다. 계정 설정에 "유료/무료 모델별로 학습하는 제공사로 보낼지" 설정이 따로 있다. 약관상 OpenRouter는 가능한 곳에서는 학습을 거부(opt-out)했다고 하지만 보장하지 않는다.
- **상업 이용**: 출력 소유권은 "각 모델의 Model Terms"를 따른다 → 쓸 모델마다 확인 필요 (예: Gemma 라이선스).
- **장점**: OpenAI 호환 API 하나로 여러 회사 모델을 바꿔 끼울 수 있어 **"바꿔 쓰기 쉬움" 조건에는 가장 잘 맞는다**.

### 2-5. Cloudflare Workers AI

- **무료 할당**: 하루 10,000 Neurons (UTC 0시 리셋). 초과분은 Workers Paid 플랜에서 $0.011 / 1,000 Neurons.
- **회차당 Neurons 계산** (입력 150k + 출력 50k 가정, 공식 단가표 기준):
  - `@cf/openai/gpt-oss-120b` (입력 31,818 / 출력 68,182 per 1M): 약 4,773 + 3,409 = **약 8,200** → 하루 1회차.
  - `@cf/google/gemma-4-26b-a4b-it` (9,091 / 27,273): 약 1,364 + 1,364 = **약 2,700** → 하루 3회차.
  - `@cf/meta/llama-3.3-70b-instruct-fp8-fast` (26,668 / 204,805): 약 14,200 → 무료 초과.
  - `@cf/qwen/qwen3.8-27b` (40,909 / 290,909): 약 20,700 → 무료 초과.
  - Kimi K2.x, GLM-5.x, DeepSeek V4는 유료 플랜이나 선불 크레딧이 필요하다.
- **분당 한도**: 유료 플랜이 필요 없는 모델은 300 RPM.
- **데이터**: 고객 콘텐츠를 **AI 모델 학습에 쓰지 않는다**. 출력은 고객 소유. 서드파티 모델 라이선스는 따로 확인해야 한다.
- **Actions**: API 토큰(Workers AI Read+Edit 권한) + 계정 ID. OpenAI 호환 base URL `https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1`.
- **유료 전환 비용 예시 (계산값)**: gpt-oss-120b 회차당 약 8,200 Neurons ≈ $0.09. 단, Workers Paid 플랜 월 기본료는 이번에 확인하지 않음 → **미확인**.

### 2-6. Mistral (La Plateforme / Mistral Studio, Free mode)

- **한도**: 공식 문서는 "작업공간(workspace) 단위, 등급별로 다름, Admin Console > Limits에서 확인"이라고만 안내한다. 무료 모드는 "가장 낮은 한도, 평가·프로토타입용". 서드파티는 약 1 RPS, 500K TPM, 월 10억 토큰이라고 적는다 (**미확인**).
- **데이터**: 도움말 문서상 무료 모드는 입력·출력을 **학습에 쓸 수 있다**(기본값). Admin Console > Privacy > "Anonymous improvement data" 토글로 끌 수 있다. 종량제(Scale) 사용 데이터는 학습에 쓰지 않는다고 안내한다.
- **모델**: 현재 범용 모델은 Mistral Medium 3.5, Large 4, Large 3, Small 4. 무료 모드에서 쓸 수 있는 모델 범위와 각 컨텍스트 길이는 **미확인**.
- **상업 이용**: **미확인**.

### 2-7. 참고: 그 밖의 선택지

- **Upstage Solar (국산)**: BenchLM 한국어 벤치마크 집계(KMMLU-Pro, CLIcK 등)에서 Solar Open이 1위로 표시된다. 하지만 공식 가격 페이지에서 상시 무료 API 등급을 확인하지 못했다 (선불 크레딧 구조, 프로모션은 자주 바뀜) → 무료 시작 후보로는 **미확인**. 한국어 품질 때문에 나중에 유료 후보로 볼 만하다.
- **Microsoft Foundry**: GitHub Models 대체재로 공식 안내됐지만 무료 한도는 **미확인**.

## 3. 한국어 글쓰기 품질

- **확인된 공개 근거가 없다 → 미확인.** 2026년 한국어 벤치마크(KMMLU, KMMLU-Pro, CLIcK, KoBALT, Horangi)는 대부분 지식·이해력을 재며, **한국어 창작(드라마 대본) 품질을 재는 공개 벤치마크에서 Gemini 3.x Flash, gpt-oss-120b, Gemma 4, Nemotron 점수를 찾지 못했다.**
- BenchLM 한국어 리더보드는 Solar Open, SK텔레콤 A.X, LG K-EXAONE 등 국산 모델만 표시하고 위 무료 모델들은 없다.
- 결론: 벤치마크로 고를 수 없으니 **직접 비교 테스트**가 필요하다. 같은 기획서로 챕터 1개를 후보 2–3개(예: Gemini 3.8 Flash, Gemma 4 31B, gpt-oss-120b)에게 쓰게 한 뒤, 사람이 이름을 가리고 읽어 비교한다. 볼 것: 존댓말·사투리 자연스러움, 시니어 시청자 어휘, 글자 수 지키기, 번역투 여부.

## 4. 추천

조건: 무료로 시작, 공급자 교체 쉬움, 한국어 품질, GitHub Actions에서 실행.

**1순위: Google Gemini API 무료 등급 — `gemini-3.8-flash` (Writer·Planner·Reviewer), 가벼운 일은 `gemini-3.5-flash-lite`**
- 무료 모델 중 정식(Stable) 최신 세대이며 출력 65,536 토큰이라 챕터는 물론 대본 전체도 한 번에 쓸 수 있다.
- 한국 지역 지원, API 키 하나로 Actions에서 바로 호출, OpenAI 호환 엔드포인트가 있다.
- 무료 한도를 넘어도 같은 키로 유료 전환하면 회차당 수백 원 수준이다 (계산값).
- 감수할 점: 무료 등급 입력·출력이 Google 제품 개선에 쓰이고 사람이 볼 수 있다. 무료 한도 숫자는 AI Studio에서 직접 확인해야 한다.

**대체(fallback): OpenRouter — `google/gemma-4-31b-it:free` 등 무료 모델**
- OpenAI 호환 API 하나로 모델을 바꿀 수 있어 교체 구조를 시험하기 좋다.
- 50 RPD가 빠듯하므로, 대체 경로로 자주 쓰게 되면 $10 크레딧을 한 번 사서 1,000 RPD로 올리는 것이 현실적이다.
- 데이터 민감도가 더 중요해지면 **Cloudflare Workers AI**(학습 미사용, 하루 10,000 Neurons, gpt-oss-120b 기준 하루 1회차)를 두 번째 대체로 둔다.

**구현 방향 (교체 쉬움)**
- `core/`에 OpenAI 호환 Chat Completions 클라이언트 하나를 두고, `base_url` / `api_key` / `model`을 설정(.env, Secrets)으로만 바꾼다. 위 1순위·대체 후보 모두 OpenAI 호환 엔드포인트를 공식 제공한다 (Gemini, OpenRouter, Cloudflare, Groq 확인).
- Agent별로 모델을 따로 지정할 수 있게 한다 (예: Writer=3.8 Flash, Image Prompt=Flash-Lite).
- 429(한도 초과) 시 다음 공급자로 넘기는 순서를 설정으로 둔다.

**제외**: GitHub Models(종료). Groq 무료(8K TPM이라 긴 챕터 호출에 부족 — 짧은 검수 보조용으로만). Mistral 무료(한도·상업 이용 미확인, 학습 기본 활성).

## 5. 유의점

- **무료 등급 데이터는 학습에 쓰일 수 있다** (Gemini 무료, Mistral 무료 기본값, OpenRouter 일부 모델). 실존 인물 정보, 개인정보, 키·토큰을 프롬프트에 넣지 않는다.
- **무료 한도 숫자는 대부분 공식 문서에 없고 콘솔에서만 보인다** (Gemini, Groq, Mistral). 첫 실행 전에 콘솔 화면에서 숫자를 확인하고 이 문서를 갱신한다.
- **Gemini 한도는 키가 아니라 프로젝트 단위**다. 키를 여러 개 만들어도 한도는 늘지 않는다 (Groq도 조직 단위). 한도를 피하려고 계정이나 프로젝트를 여러 개 만드는 방식은 쓰지 않는다.
- **생성물은 다른 사람에게도 비슷하게 나올 수 있다** (Gemini 약관). 수익화 채널 대본이라면 사람이 고쳐 쓰는 단계(DRAFT → 사람 검토)를 유지한다.
- **가격·모델은 자주 바뀐다**: Gemini 3.6/3.8 Flash 단가는 2027-01-01에 2배로 오른다. Gemini 2.5 계열은 기존 사용자만 쓸 수 있다. OpenRouter 무료 모델은 예고 후 사라진다. 모델 이름을 코드에 박지 말고 설정으로 뺀다.
- Gemini 약관상 18세 이상, 업무 목적 사용. 유럽(EEA)·스위스·영국 사용자 대상 서비스에는 무료 등급을 쓸 수 없다 (현재 해당 없음).
- 한국어 창작 품질은 **미확인**이다. 공급자를 정하기 전에 챕터 1개 블라인드 비교를 꼭 한다.

## 6. 출처

Google Gemini
- 가격 (무료 등급 여부, "Used to improve our products", 유료 단가): https://ai.google.dev/gemini-api/docs/pricing
- 한도 (2026-10-28 갱신, AI Studio에서 확인 안내, 프로젝트 단위): https://ai.google.dev/gemini-api/docs/rate-limits
- 모델 목록·상태: https://ai.google.dev/gemini-api/docs/models
- 3.8 Flash: https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash
- 3.6 Flash: https://ai.google.dev/gemini-api/docs/models/gemini-3.6-flash
- 3.5 Flash-Lite: https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite
- 지원 지역: https://ai.google.dev/gemini-api/docs/available-regions
- 약관 (2026-04-28 갱신): https://ai.google.dev/gemini-api/terms
- OpenAI 호환: https://ai.google.dev/gemini-api/docs/openai

GitHub Models
- 종료 공지: https://github.blog/changelog/2026-07-30-github-models-is-now-retired/
- 종료 일정 공지: https://github.blog/changelog/2026-07-01-github-models-is-being-fully-retired-on-july-30-2026
- 문서 (종료 안내로 바뀜): https://docs.github.com/en/github-models/use-github-models/prototyping-with-ai-models

Groq
- 한도: https://console.groq.com/docs/rate-limits
- 모델: https://console.groq.com/docs/models
- 데이터 보존: https://console.groq.com/docs/your-data
- 무료 한도 서드파티 자료 (미확인): https://benchlm.ai/md/free-tier/groq.md , https://www.developersdigest.tech/models/free-api/groq

OpenRouter
- 한도: https://openrouter.ai/docs/api/reference/limits
- 공급자 로깅·학습 설정: https://openrouter.ai/docs/guides/privacy/provider-logging
- 약관: https://openrouter.ai/terms
- 모델 목록 API (2026-10-30 조회): https://openrouter.ai/api/v1/models

Cloudflare Workers AI
- 가격·Neurons: https://developers.cloudflare.com/workers-ai/platform/pricing/
- 한도: https://developers.cloudflare.com/workers-ai/platform/limits/
- 데이터 이용: https://developers.cloudflare.com/workers-ai/platform/data-usage/
- REST API 인증: https://developers.cloudflare.com/workers-ai/get-started/rest-api/
- OpenAI 호환: https://developers.cloudflare.com/workers-ai/configuration/open-ai-compatibility/

Mistral
- 학습 데이터 이용: https://help.mistral.ai/en/articles/347617-do-you-use-my-user-data-to-train-your-artificial-intelligence-models
- 학습 거부(opt-out): https://help.mistral.ai/en/articles/455207-can-i-opt-out-of-my-input-or-output-data-being-used-for-training
- 한도·등급: https://docs.mistral.ai/deployment/ai-studio/tier
- 모델: https://docs.mistral.ai/getting-started/models/

한국어 벤치마크·기타
- BenchLM 한국어 벤치마크 리더보드: https://benchlm.ai/leaderboards/korean-benchmarks
- Upstage 가격: https://www.upstage.ai/ko/pricing
