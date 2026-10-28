# YouTube 쇼츠 × 쿠팡 파트너스 정리

> 2026-10-28 조사·논의 정리. 웹 자료는 블로그·요약이 많아 **실행 전 YouTube 스튜디오·쿠팡 파트너스 화면에서 재확인**할 것.
> 관련: [PLAN.md](PLAN.md) Step 3·4 · 근거 노트 `../gomgom/정리/` 05·09·11·12

## 1. 쿠팡 파트너스 가입 — 채널 등록

- YouTube 먼저 만들 필요 **없음**. 운영 중인 **Threads 프로필 주소**를 등록 (12번 노트 STEP 1-4 "운영 중인 스레드 URL 입력")
  - 예: `https://www.threads.com/@계정아이디` → 브라우저에서 프로필 열고 주소창 그대로 복사
  - "웹사이트 / 모바일 앱" 둘 중 하나만 쓰면 됨. SNS 페이지·유튜브 채널 주소도 웹사이트로 인정
- 사업자등록 없으면 **개인**으로 가입
- 나중에 추가 등록할 것: YouTube 채널 주소, 상품 모음 페이지(프로필 링크용) 주소 — **링크를 게시하는 곳은 전부 등록**
- 최종 승인: 누적 판매 일정 금액(블로그상 15만 원이라는 설명 多, 미확인) 후 심사, **등록 채널에 링크가 게시된 화면 스크린샷** 요구한다는 설명 있음 → 최종 승인 전엔 수익이 지급 안 될 수 있음

## 2. 쇼츠에 쿠팡을 붙이는 두 가지 방법

| | ① 쿠팡 파트너스 링크 | ② 유튜브 쇼핑 제휴 프로그램 (상품 태그) |
|---|---|---|
| 쇼츠에서 | 설명란·댓글 링크 **클릭 안 됨** → 채널 프로필 링크(링크 모음 페이지)로 유도 | 쇼츠 위에 **누를 수 있는 상품 스티커** |
| 자격 | 채널 크기 무관, 지금 가능 | **YPP 가입 필수** + 구독자 500명 (2026-03-30 발표) |
| 수수료 | 쿠팡 파트너스 기준 (블로그상 3%) | 블로그상 6.7% (2024년 자료, 상품별 상이 가능 — 확인 필요) |
| 정산 | 쿠팡 파트너스 | YouTube → 애드센스 |
| 대가성 문구 | 링크 옆에 직접 표시 | 자동 표시 |
| 실적 | 쿠팡 파트너스 사이트 | YouTube 스튜디오 |

### ② 유튜브 쇼핑 제휴 상세
- 한국 시작 2024-06, 쿠팡이 첫 제휴사. 현재 쿠팡·올리브영·컬리·오늘의집·알리익스프레스 등 10곳
- 구독자 기준 변화: 1만(2024-06) → 5천(2025 하반기) → 1천(2026 초) → **500(2026-03-30 발표)**. "1만 명"이라고 쓴 글은 옛날 정보
- YPP 확장 기준(블로그 설명, 공식 페이지엔 숫자 없음): 구독자 500 + 최근 90일 공개 영상 3개 + (12개월 시청 3,000시간 **또는** 90일 쇼츠 조회 300만)
- 제외: 음악 채널, 아동용 채널
- 공식 안내: **영상·쇼츠에 등장하는 제품**을 태그. 관련 없는 태그 반복 시 프로그램 이용 정지 가능. 태그는 검토 후 노출
- YouTube 외부에서 제휴 링크 공유, 자동 리디렉션, 쿠키 스터핑 → 정지 사유
- 태그는 스튜디오에서 사람이 붙이는 방식으로 보임 (**API 자동화 가능 여부 미확인**)

## 3. 우리 쇼츠 방향 (논의 결과, 확정 전)

### 영상은 자동 제작 (촬영 없음) — "정보형 쇼츠"
- Threads에서 반응 좋은 주제 → AI 대본 → 정보 카드/일러스트 + AI 음성 + 큰 자막 → ffmpeg 9:16 합성 → **비공개 업로드** → 사람이 공개
- **금지:** AI로 만든 실사풍 **제품 사용·작동 장면** (허위·과장 광고, 09번 노트 원칙). 팁·고르는 기준만 말하고 써본 척 X
- 실사처럼 보이는 AI 이미지 → 업로드 시 AI 생성 콘텐츠 표시
- 회사 PC: ffmpeg 는 PyPI `imageio-ffmpeg` 로 우회

### 타깃: 50~60대 (제안 — 노트에 근거 없음, 운영하며 검증)
- 채널 약속(안): "50~60대가 매일 하는 집안일·외출에서 몸이 덜 힘들게 해 주는 물건과 고르는 기준"
- Threads(좁은 집 살림)와 **채널 분리**
- 사는 사람 두 부류: 본인용 / 30~40대 자녀의 **부모님 선물용** → 내년 2월 설 시즌 대비 11~12월에 영상 쌓기
- 상품군: 덜 숙이기(긴 손잡이 청소도구), 미끄럼 방지·센서등, 손힘 덜 쓰는 주방도구, 큰 글씨 시계, 텃밭·걷기 소품
- 피할 것: 건강기능식품·의료기기·효능 주장("관절에 좋다"), 보험·금융
- 형식: 큰 자막·높은 대비, 차분한 음성, 한 영상 한 메시지, 30~45초, 줄임말 X

### 링크 동선 — 단계별
| 단계 | 방법 |
|---|---|
| 지금 ~ 구독자 500 + YPP 승인 | 채널 프로필에 **상품 모음 페이지**(Netlify, 대가성 문구 포함) + "제품 링크는 프로필에" 안내 |
| YPP 승인 후 | 잘 팔리는 상품만 **직접 촬영 장면 포함** 쇼츠로 → 쿠팡 상품 태그 |

### 위험
- **YPP 심사:** 재사용·대량생산형 콘텐츠는 수익화 거절 가능 → 매 편 주제·구성·화면 다르게, 주 2~3편, 직접 촬영 영상 일부 섞기 권장
- **상품 태그 = 영상에 등장한 제품:** 정보 카드에 상품 이미지만으로 충분한지 불확실 → 태그용 영상은 실물 촬영
- 쿠팡 API 상품 이미지를 영상에 써도 되는지 약관 확인 전엔 사용 X

## 4. 정할 것 / 할 일

- [x] 쿠팡 파트너스 가입 (개인) + Threads 주소 등록
- [x] 쿠팡 링크 1개 만들어 Threads 링크 글 시험 ([TODO-manual.md](TODO-manual.md) 3번)
- [ ] 쇼츠 음성: Google TTS(무료 한도) vs Typecast(유료, 자연스러움)
- [ ] 쇼츠 화면: 정보 카드만 vs AI 일러스트 섞기
- [ ] 샘플 영상 1개 로컬 제작 → 보고 결정
- [ ] YouTube 쇼핑 채널 개설 → 쿠팡 파트너스에 채널 주소 추가 등록
- [ ] 상품 모음 페이지(Netlify) → 쿠팡 파트너스에 주소 추가 등록
- [ ] PLAN.md Step 4 개정 (촬영 → 자동 정보형, 타깃 50~60대, 설명란 링크 → 프로필 상품 모음 페이지)

## 5. 쇼츠 음성 — 무료 자동화 조사 (2026-10-28)

| 후보 | 비용 | 공식 상업 이용 | 자동화 | 비고 |
|---|---|---|---|---|
| **edge-tts** (PyPI) | 무료, 키 없음 | **불분명** (Edge 읽어주기 서비스 비공식 호출, SLA 없음) | 쉬움. 단어별 타이밍 제공 → 자막 싱크 | 회사 PC에서 동작 확인. 한국어 3종 (SunHi 여, InJoon 남, Hyunsu 남) |
| **Google Cloud TTS** | 매달 무료: Standard·WaveNet 4M자, Neural2·Chirp 3 HD 1M자 (블로그·요약 기준, 공식 페이지 재확인) | O (정식 API) | 서비스 계정 키 → GitHub Secret. SSML mark 로 타이밍 | **결제 카드 등록 필요** (무료 한도 안이면 0원). 쇼츠 1편 ≈ 250자 → 무료 한도로 충분 |
| Gemini TTS (무료 등급) | 무료 | 무료 등급은 입력이 학습에 쓰일 수 있음 | 하루 15회 내외 (프리뷰, 수시 변경) | 타이밍 정보 없음 → 자막 싱크 별도 |
| MeloTTS-Korean (로컬) | 무료, MIT | O | torch 등 무거움 | 품질 낮은 편, 2024 이후 업데이트 미확인 |
| Supertonic | 무료, OpenRAIL-M | 조건부 | — | 개발사 해산(2026-07), 지원 종료 |

- **결정 (2026-10-28): Google Cloud TTS API** (공식·Windows/Mac/Actions 동일). 구현 `channels/tts/` — `uv run python -m channels.tts "대본"` → `out/tts/sample.mp3` + `.srt` (단어마다 SSML mark → 시각), `--list-voices`
- 키: `.env` 의 `GOOGLE_TTS_API_KEY` (API 키를 Text-to-Speech API 로만 제한), 목소리 `TTS_VOICE`, 속도 `TTS_RATE=1.1`
- 업로드 시 "변경·합성 콘텐츠" 표시 기준 확인 (AI 음성 자체는 해당 아닐 수 있음)

## 출처
- [Google Cloud TTS 가격](https://cloud.google.com/text-to-speech/pricing) · [CostBench 무료 플랜](https://costbench.com/software/ai-voice-tools/google-cloud-text-to-speech/free-plan/)
- [edge-tts PyPI](https://pypi.org/project/edge-tts) · [wikidocs – edge-tts 약관·SLA 지적](https://wikidocs.net/blog/@jaehong/9554/)
- [Gemini API 가격](https://ai.google.dev/gemini-api/docs/pricing) · [MeloTTS-Korean](https://huggingface.co/myshell-ai/MeloTTS-Korean) · [Supertonic 3](https://huggingface.co/LeeAeron/supertonic-3)
- [YouTube 고객센터 – 쇼핑 제휴 프로그램 개요 및 자격요건](https://support.google.com/youtube/answer/13376398)
- [YouTube Creators – Shopping](https://www.youtube.com/creators/partner-program/shopping/)
- [Seoul Economic Daily – 구독자 500명으로 완화 (2026-03-30)](https://en.sedaily.com/technology/2026/03/30/youtube-lowers-shopping-affiliate-threshold-to-500)
- [Social Media Today – Shopping Affiliate 확대](https://www.socialmediatoday.com/news/youtube-expands-shopping-affiliate-program-access/815754/)
- [wplaybook – 쿠팡 상품 유튜브 쇼핑 연동](https://wplaybook.com/en/must-read-coupang-products-now-usable-for-youtube-shopping-integration-wow/)
- [viralpulse – 쇼핑 제휴 500명 가이드](https://viralpulse.net/blog/youtube-shopping-affiliate-guide)
- [min-inter – 쇼핑 쇼츠 500명](https://min-inter.co.kr/wiki/youtube-shopping-shorts-500-subscribers-affiliate-tag/)
- [min-inter – 쇼츠 제품 스티커](https://min-inter.co.kr/wiki/youtube-shorts-shopping-product-sticker-2026/)
- [lilys.ai – 쇼츠 댓글·설명 링크가 안 눌리는 이유](https://lilys.ai/ko/notes/youtube-shopping-shorts-20251128/coupang-partners-links-youtube-shorts-explained)
- [lilys.ai – 파트너스 링크 vs 쇼핑 태그 비교](https://lilys.ai/ko/notes/youtube-shopping-shorts-20251128/youtube-coupang-affiliate-money-2-ways)
- [namsieon – 유튜브 쇼핑으로 쿠팡 태그](https://namsieon.com/6375)
