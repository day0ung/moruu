# 시니어 사연 드라마 — 감정 TTS 비교 (2026-10-30)

대상: 롱폼 사연·드라마 (내레이터 + 등장인물 2~5명, 편당 10~30분, 월 ~12편).
기준 사용량: 20분 1편 ≈ 15,000자 × 12편 ≈ **월 180,000자** (≈ 240분 음성, 약 750자/분).
현재: Google Cloud TTS `ko-KR-Neural2` + SSML `<mark>` 로 자막 싱크 (감정 조절 거의 없음).
쇼츠용 무료 TTS 조사(edge-tts, MeloTTS 등)는 [youtube-shorts-coupang.md](youtube-shorts-coupang.md) 5장 참고 — 여기서는 반복하지 않는다.

## 1. 비교표

| 항목 | **Typecast API** | **ElevenLabs** | **Google Gemini TTS** | Google Chirp 3 HD | Naver CLOVA Voice / Dubbing |
|---|---|---|---|---|---|
| 한국어 감정 조절 | 프리셋 7종 (normal·happy·sad·angry·whisper·toneup·tonedown) + 강도 0.0~2.0, **Smart 모드**(앞뒤 문장으로 감정 추론) — ssfm-v30/v31 | v4·v3 **오디오 태그** (`[sad]` `[whispers]` `[sighs]` `[crying]` 등, 영어 태그) · 대화 전용 API | 자연어 **스타일 프롬프트** ("떨리는 목소리로") + 태그 (`[sigh]` `[whispering]` 등, 일부 프리뷰) | 감정 파라미터 없음. 속도·쉼(`[pause]`)만 | Premium: 감정 0~3(중립·슬픔·기쁨·분노) + 강도 0~2, 일부 화자(vara·vmikyung 등)만 |
| 노년 목소리 | 있음 — 공식 "시니어 AI 음성" 페이지, API 목소리 목록에 나이 필터 (값 이름은 문서마다 다름: `elder`/`senior` → 호출해 확인) | 보이스 라이브러리에 grandma·grandpa 류 있음. **한국어 원어민 노년 목소리는 미확인** (Voice Design으로 생성 가능성도 미확인) | 기본 목소리 고정, 나이는 프롬프트로 연기 — 효과 **미확인** | 나이 구분 없음 | 화자 목록 공식 확인 못 함 (**미확인**) |
| 상업 이용 (수익화 유튜브) | 유료 플랜 O, **출처 표기 불필요**. 무료 플랜은 상업 불가·출처 표기 필수 | 유료 플랜 O (무료는 비상업만). 출처 표기 요구 없음 | 정식 API 유료 O. Gemini API **무료 등급은 입력이 제품 개선에 쓰임** | 정식 API O | **CLOVA Voice API: 파일 저장·편집·재사용 불가 → 영상 제작에 못 씀.** CLOVA Dubbing Premium(웹)은 상업 O, Standard는 비영리만 |
| 월 18만 자 비용 | API **Lite $15/월** (20만 크레딧, 1자=1크레딧, 초과 $0.09/1천자) | 종량 v4·v3 **$0.08/1천자 → ≈ $14.4**. 또는 Creator $22/월 (v2·v3 27.5만 자) | **Gemini 3.8 Flash TTS ≈ $3~4/월** (출력 $9/1M 토큰, 25토큰/초 → 240분 ≈ 36만 토큰; 2027-01-01부터 단가 2배). 3.1 Flash ≈ $7 | 매달 1M자 무료 → **≈ $0** (초과 $30/1M자) | Voice Premium 기본료·단가 공식 페이지에서 **미확인**. Dubbing Premium 단가 **미확인** (월 180,000자·150건까지 무료 구간 표기는 있음) |
| API | REST + 공식 SDK (Python 등) | REST + SDK. TTS 요청당 v4 1만 자 / v3 5천 자, 대화 API는 2천 자 권장 | Gemini API / Cloud TTS. 한 요청 다중 화자 **최대 2명** | Cloud TTS REST | Voice: REST(2,000자/요청). Dubbing: 웹 빌더, 생성 API **미확인** |
| 자막용 타이밍 | **O — `/v1/text-to-speech/with-timestamps` 단어 단위** (SDK `to_srt()`) | **O — 글자 단위** (`/with-timestamps`, 대화 API도 화자 구간 + 글자 타이밍) | **X** (문서에 없음) | X (`<mark>` 미지원, 지원 태그 목록에 없음) | X (음성 바이너리만) |
| 제한·주의 | AI 합성 표시(워터마크·메타데이터) 제거 금지, 동의 없는 목소리 복제 금지 (API 약관 2026-09-01) | 금지 용도 정책 준수, 목소리 복제 동의 필요 | 3.8은 프리뷰·Gemini API 쪽 모델, 마크업 태그 프리뷰. 감정 형용사 태그는 소리 내 읽힐 수 있음 | SSML·쉼 태그 프리뷰 | 재판매 금지, 실시간 호출 전제 |

Supertone: API 페이지(supertone.ai/api)가 antinodeaudio.com 회원 전용 페이지로 넘어가 요금·약관·API **미확인**. 후보에서 제외.

## 2. 제공자별 메모

- **Typecast (네오사피엔스, 한국)** — 한국어 캐릭터 목소리가 가장 많고 노년 목소리가 공식적으로 있다. 감정 프리셋 + 강도로 "대사마다 감정 지정"이 그대로 코드화된다. Smart 모드는 `previous_text`/`next_text` 를 넘기면 문맥으로 감정을 고르므로 대본 줄 단위 합성과 잘 맞는다. 단어 타임스탬프 API(2026-04)로 지금의 `<mark>` 방식 대체 가능. 2026-10-28 `ssfm-v31` 출시(안정성 개선). Smart 모드와 타임스탬프를 같이 쓸 수 있는지는 **미확인**. 웹 요금제(원화, 베이직 ₩9,900~비즈니스 ₩99,000)와 API 요금제는 별개 — 자동화는 API 요금제.
- **ElevenLabs** — 감정 표현 폭은 가장 넓다(울음·한숨·속삭임 태그, v4가 태그를 더 잘 따름). 대화 API가 화자 10명까지 한 번에 만들고 화자 구간·글자 타이밍을 주므로 드라마 장면 단위 합성에 맞다. 다만 태그가 영어라 한국어 대본에 섞어 써야 하고, 한국어 노년 목소리 품질은 직접 들어봐야 한다. 감정 지시문이 소리로 읽힐 수 있어 검수 필요.
- **Google Gemini TTS** — 가장 싸고 프롬프트로 "서운한 듯 낮게" 같은 지시가 된다. 하지만 타이밍 정보가 없고 한 요청 2명까지라, 줄마다 따로 합성 → 오디오 길이로 자막 시각 계산하는 방식이 필요하다. 3.8 모델은 프리뷰, 2027년부터 가격 2배. 같은 GCP 계정이라 붙이기는 쉽다.
- **Chirp 3 HD** — 지금 Neural2보다 자연스럽고 무료 한도 안이지만 감정 조절이 없고 `<mark>`도 안 된다. 내레이터 전용 후보 정도.
- **CLOVA** — Voice API는 약관상 생성 파일 저장·편집·재사용 불가라 유튜브 영상 제작 파이프라인에 쓸 수 없다. Dubbing Premium은 상업 이용 가능하지만 웹 빌더 중심이라 자동화와 맞지 않는다. **제외.**

## 3. 유튜브 쪽 규칙 (공통)

- **AI 표시:** 실존 인물이 말한 것처럼 만들거나, 실제로 일어나지 않은 **사실적인** 장면을 만들면 "변경·합성 콘텐츠" 표시 대상. 가상 인물의 AI 내레이션 자체는 예시에 없음 → 사실처럼 보이는 실화 사연 연출이면 표시하는 쪽이 안전. Typecast 약관도 AI 합성 사실을 숨기는 것을 금지.
- **수익화(YPP) 위험이 더 크다:** "진정성 없는 콘텐츠(inauthentic content)" 정책에 **"같은 상황·같은 결말의 비슷한 줄거리 템플릿에 인물을 넣은 영상"** 이 명시돼 있다. 사연 드라마는 정확히 이 위험군 → 편마다 갈등·결말·구성이 달라야 함. TTS 선택보다 중요.
- **목소리 복제:** 모든 업체가 본인 동의 없는 복제를 금지. 실존 인물(연예인 등) 흉내 금지.

## 4. 추천

**1순위: Typecast API (Lite $15/월)**
- 한국어 원어민 목소리 + 공식 노년 목소리 → 시어머니·아들·며느리 배역을 바로 캐스팅 가능.
- 감정 프리셋·강도가 숫자 파라미터라 대본 형식(줄마다 `감정` 필드)으로 옮기기 쉽고, 단어 타임스탬프로 지금 자막 싱크 구조를 유지할 수 있다.
- 월 18만 자가 Lite 20만 크레딧 안에 들어가고, 유료면 출처 표기 없이 상업 이용 가능.

**대안: ElevenLabs (종량 ≈ $15/월 또는 Creator $22/월)**
- Typecast 감정 폭이 부족하다고 느껴질 때. 울음·한숨 같은 연기가 필요한 장면에 강하고 글자 타이밍도 준다.
- 한국어 노년 목소리 품질은 미확인이라 시험 후 결정.

**비용 최저 대안: Gemini TTS** — 자막 타이밍을 줄 단위 합성 + 오디오 길이로 직접 계산할 각오가 되면.

**결정 전 할 일:** 같은 1분 장면(내레이션 + 시어머니·며느리 말다툼)을 Typecast·ElevenLabs·Gemini 무료 등급으로 만들어 들어보고 고른다 (무료 등급 결과물은 게시용으로 쓰지 않음). 엔진은 `channels/tts/` 에서 "줄 1개 → (오디오, 타이밍)" 인터페이스로 끼워 넣는 구조를 권장 — 타이밍을 안 주는 엔진은 오디오 길이로 대체.

## 출처
- Typecast: [API 요금](https://typecast.ai/pricing/api/) · [원화 요금제](https://typecast.ai/kr/pricing) · [요금 개편 공지](https://typecast.ai/learn/typecast-pricing-update/) · [API 변경 이력(ssfm-v30/v31, 타임스탬프)](https://typecast.ai/docs/changelog?lang=en) · [퀵스타트(감정·타임스탬프)](https://typecast.ai/docs/ko/quickstart?lang=ko) · [API 이용약관](https://help.typecast.ai/en/articles/11872662-typecast-api-terms-of-use) · [출처 표기 가이드](https://typecast.ai/guideline/) · [시니어 음성](https://typecast.ai/voices/senior-ai-voice/) · [Pipecat 문서(emotion_intensity 범위)](https://docs.pipecat.ai/api-reference/server/services/tts/typecast)
- ElevenLabs: [API 요금](https://elevenlabs.io/pricing/api) · [모델](https://elevenlabs.io/docs/overview/models) · [TTS 기능](https://elevenlabs.io/docs/overview/capabilities/text-to-speech) · [TTS with timestamps](https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps) · [Dialogue with timestamps](https://elevenlabs.io/docs/api-reference/text-to-dialogue/convert-with-timestamps) · [v3/v4 프롬프트·오디오 태그](https://elevenlabs.io/docs/best-practices/prompting/eleven-v3) · [이용약관](https://elevenlabs.io/terms-of-use) · [금지 용도](https://elevenlabs.io/use-policy) · [v4 소개](https://elevenlabs.io/v4)
- Google: [Gemini TTS (Cloud)](https://docs.cloud.google.com/text-to-speech/docs/gemini-tts) · [Gemini API 음성 생성](https://ai.google.dev/gemini-api/docs/speech-generation) · [Gemini API 가격](https://ai.google.dev/gemini-api/docs/pricing) · [Chirp 3 HD](https://docs.cloud.google.com/text-to-speech/docs/chirp3-hd) · [Cloud TTS 가격](https://cloud.google.com/text-to-speech/pricing) (페이지 본문 직접 확인 실패, 검색 스니펫 기준)
- Naver: [CLOVA Voice Premium API](https://api.ncloud-docs.com/docs/ai-naver-clovavoice-ttspremium) · [CLOVA Voice 이용 정책](https://guide.ncloud-docs.com/docs/en/clovavoice-policy) · [CLOVA Voice 사양](https://guide.ncloud-docs.com/docs/clovavoice-spec) · [CLOVA Dubbing 요금제](https://guide.ncloud-docs.com/docs/clovadubbing-serviceplan) · [CLOVA Dubbing FAQ](https://guide.ncloud-docs.com/docs/clovadubbing-troubleshoot) · [요금(공공)](https://www.gov-ncloud.com/product/aiService/clovaVoice)
- YouTube: [변경·합성 콘텐츠 표시](https://support.google.com/youtube/answer/14328491) · [YPP 수익 창출 정책(inauthentic content)](https://support.google.com/youtube/answer/1311392)
- Supertone: [API 페이지(리다이렉트됨)](https://www.supertone.ai/en/api)
