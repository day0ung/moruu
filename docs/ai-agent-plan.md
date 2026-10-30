# moruu AI 콘텐츠 제작 Agent 구축 계획서

- 문서 버전: v1.0
- 목적: 30분 분량의 시니어 롱폼 콘텐츠 자동 제작
- 실행 환경: GitHub Actions
- 개발 언어: Python
- 운영 방식: 클라우드 자동 실행
- 비용 목표: 대본 생성 및 관리 단계 무료 운영 우선

---

## 1. 프로젝트 목표

개인 PC나 Mac에 의존하지 않고 GitHub Actions를 통해 AI 콘텐츠 제작 Agent를 자동 실행하는 환경을 구축한다.

사용자는 콘텐츠 제작을 요청하고, AI Agent는 기획부터 대본 작성, 검수, 이미지 프롬프트 생성까지 수행한다.

완성된 콘텐츠는 Notion에 DRAFT 상태로 등록하고, 사람이 검토한 후 APPROVED 상태로 변경하면 영상 렌더링 파이프라인이 실행된다.

### 핵심 목표

1. 30분 분량의 시니어 롱폼 대본 자동 생성
2. 콘텐츠 기획 및 대본 작성 자동화
3. AI 대본 품질 검수
4. 장면별 이미지 프롬프트 자동 생성
5. Notion 및 Google Drive 연동
6. GitHub Actions 기반 무인 실행
7. Telegram 작업 결과 알림

---

## 2. 전체 시스템 아키텍처

```text
[사용자]
    |
    | 콘텐츠 제작 요청
    v
[GitHub Actions]
    |
    v
[AI 콘텐츠 제작 Pipeline]
    |
    +-- 1. Planner Agent
    |      소재 발굴
    |      제목 및 썸네일 기획
    |      시놉시스 생성
    |
    +-- 2. Writer Agent
    |      8개 챕터 구성
    |      30분 분량 대본 작성
    |
    +-- 3. Reviewer Agent
    |      개연성 검수
    |      인물 일관성 검수
    |      반복 문장 검수
    |      분량 검수
    |
    +-- 4. Image Prompt Agent
    |      장면 분할
    |      이미지 프롬프트 생성
    |      등장인물 일관성 관리
    |
    v
[Notion]
    |
    | DRAFT 등록
    v
[사람 검토 및 APPROVED]
    |
    v
[Google Drive 자료 폴더]
    |
    | 이미지 및 출처 업로드
    v
[GitHub Actions 렌더링]
    |
    v
[영상 완성]
    |
    +-- Google Drive 저장
    |
    +-- Telegram 알림
    |
    v
[사람 검토]
    |
    v
[YouTube 업로드]
```

---

## 3. 개발 환경 및 기술 스택

| 구분 | 기술 | 역할 |
|---|---|---|
| 실행 환경 | GitHub Actions | 클라우드 작업 실행 |
| 개발 언어 | Python | Agent 및 Pipeline 개발 |
| AI 모델 | 외부 AI API | 대본 및 프롬프트 생성 |
| Agent 구조 | Python 기반 역할별 Agent | 작업 분리 및 관리 |
| 데이터 관리 | Notion API | 콘텐츠 상태 관리 |
| 파일 저장 | Google Drive API | 이미지 및 영상 저장 |
| 알림 | Telegram Bot API | 작업 결과 알림 |
| 영상 렌더링 | 기존 Python Pipeline | 영상 생성 |
| 버전 관리 | GitHub | 소스 및 Workflow 관리 |

### AI 모델 운영 전략

AI 모델은 특정 서비스에 종속되지 않도록 API 호출 부분을 분리한다.

초기에는 무료 사용량이 제공되는 모델을 우선 검토한다.

후보:
- Google Gemini API
- OpenAI API
- Ollama 기반 로컬 모델

Ollama는 로컬 PC에서 실행하는 방식이므로 GitHub Actions에서 사용하려면 별도의 실행 환경 구성이 필요하다.

기본 운영은 외부 AI API를 사용하는 방식으로 설계한다.

---

## 4. Agent별 상세 기능

### 4-1. Planner Agent (기획 Agent)

역할: 시니어 시청자를 대상으로 하는 콘텐츠 소재와 이야기 구조를 기획한다.

주요 기능:
- 콘텐츠 소재 발굴
- 시니어 관심 주제 분석
- 제목 5개 생성
- 썸네일 문구 생성
- 등장인물 설정
- 전체 줄거리 작성
- 8개 챕터 구성
- 핵심 갈등 및 반전 설계

기획 소재 예시:
- 부모와 자식 간 갈등
- 며느리와 시어머니 갈등
- 황혼 이혼 및 재혼
- 노후 빈곤과 재산 상속
- 가족의 배신과 용서
- 오랜 세월 감춰진 비밀
- 노년의 우정과 사랑

출력:
- 콘텐츠 제목
- 썸네일 문구
- 시놉시스
- 등장인물 정보
- 챕터별 이야기 구성
- 복선 및 반전 계획

### 4-2. Writer Agent (대본 작성 Agent)

역할: 승인된 기획안을 바탕으로 실제 영상에 사용할 나레이션 대본을 작성한다.

목표:
- 영상 길이 약 30분
- 8개 챕터
- 초기 목표 분량 약 8,000~10,000자
- 자연스러운 한국어 나레이션
- 대사와 상황 묘사 포함

작성 원칙:
- 초반 30초에 강력한 후킹 배치
- 챕터마다 독립적인 사건 구성
- 중간부에 새로운 갈등 및 반전 배치
- 후반부에 초반 복선 회수
- 불필요한 반복 문장 제거
- 실제 한국 가족관계와 생활환경 반영

한 번에 전체 대본을 생성하지 않고 챕터 단위로 생성한다.

### 4-3. Reviewer Agent (검수 Agent)

역할: 생성된 대본의 품질을 검증한다.

검수 항목:
- 등장인물 이름 및 나이 일관성
- 가족관계 오류
- 시간적 흐름 오류
- 사건의 개연성
- 이야기 중복
- 반복적인 표현
- 챕터 간 연결성
- 초반 후킹의 완성도
- 결말의 완성도
- 목표 영상 길이 충족 여부

검수 결과:
- PASS: 다음 단계 진행
- REVISION: 수정 요청
- FAIL: 기획 또는 대본 재작성

무한 재생성을 방지하기 위해 수정 횟수는 최대 3회로 제한한다.

### 4-4. Image Prompt Agent (이미지 프롬프트 Agent)

역할: 대본을 영상 제작에 필요한 장면 단위로 분리한다.

주요 기능:
- 대본을 장면별로 분할
- 장면별 이미지 프롬프트 생성
- 등장인물 외형 정의
- 인물별 이미지 일관성 유지
- 이미지 파일명 지정
- 장면별 이미지 생성 지침 작성

출력 예시:

```text
01.png
- 60대 한국인 여성
- 오래된 아파트 거실
- 창밖을 바라보는 모습
- 쓸쓸하고 어두운 분위기

02.png
- 60대 여성과 30대 남성
- 식탁에서 마주 앉은 장면
- 갈등이 느껴지는 표정
```

이미지 생성 API는 별도 모듈로 분리하며, 초기에는 사람이 이미지를 준비해 Drive에 업로드하는 방식도 지원한다.

---

## 5. 콘텐츠 제작 Workflow

### 1단계. 콘텐츠 생성 요청

GitHub Actions에서 Workflow를 실행한다.

입력값:
- 콘텐츠 유형: 쇼츠 / 롱폼
- 콘텐츠 소재
- 목표 영상 길이
- AI 모델 선택

### 2단계. 기획 생성

Planner Agent가 소재와 시놉시스를 생성한다.

### 3단계. 대본 생성

Writer Agent가 챕터별 대본을 생성한다.

### 4단계. 대본 검수

Reviewer Agent가 대본을 검수하고 필요한 경우 수정한다.

### 5단계. 이미지 프롬프트 생성

Image Prompt Agent가 장면별 이미지 제작 지침을 생성한다.

### 6단계. Notion 등록

생성된 콘텐츠를 Notion에 DRAFT 상태로 등록한다.

저장 항목:
- content_id
- 제목
- 썸네일 문구
- 시놉시스
- 전체 대본
- 챕터별 대본
- 이미지 프롬프트
- 예상 영상 길이
- 생성 모델
- 생성 일시
- 작업 상태

### 7단계. 사람 검토

사람이 Notion에서 내용을 확인하고 APPROVED로 변경한다.

### 8단계. 자료 업로드

Google Drive 자료 폴더에 이미지와 출처.txt를 업로드한다.

### 9단계. 영상 렌더링

기존 GitHub Actions 렌더링 Workflow를 실행한다.

### 10단계. 결과 알림

Telegram으로 렌더링 결과와 영상 링크를 전달한다.

---

## 6. GitHub 저장소 구조

```text
moruu/
│
├── agents/
│   ├── base.py
│   ├── planner.py
│   ├── writer.py
│   ├── reviewer.py
│   └── image_prompt.py
│
├── pipelines/
│   ├── generate.py
│   ├── media_folders.py
│   ├── render.py
│   └── upload.py
│
├── services/
│   ├── ai_client.py
│   ├── notion_client.py
│   ├── drive_client.py
│   └── telegram_client.py
│
├── prompts/
│   ├── planner.txt
│   ├── writer.txt
│   ├── reviewer.txt
│   └── image_prompt.txt
│
├── config/
│   └── settings.py
│
├── .github/
│   └── workflows/
│       ├── generate.yml
│       └── render.yml
│
├── requirements.txt
└── README.md
```

### 설계 원칙

- Agent별 역할 분리
- AI 모델 교체 가능 구조
- API 호출 모듈 분리
- 기존 렌더링 Pipeline 재사용
- Notion과 Google Drive 연동 분리
- 작업 실패 시 재실행 가능하도록 설계
- API 키는 GitHub Secrets로 관리

---

## 7. GitHub Actions 운영 전략

개인 PC가 아닌 GitHub 클라우드 환경에서 실행한다.

### Workflow A: 콘텐츠 생성

실행:
- 수동 실행
- 필요시 예약 실행

작업:
- Planner Agent
- Writer Agent
- Reviewer Agent
- Image Prompt Agent
- Notion DRAFT 등록

### Workflow B: 영상 렌더링

실행:
- 수동 실행
- APPROVED 콘텐츠 대상

작업:
- Notion 상태 확인
- Google Drive 자료 확인
- 영상 렌더링
- 결과 저장
- Telegram 알림

### 실행 시 주의사항

- 생성 Workflow와 렌더링 Workflow를 분리한다.
- 장시간 실행 작업은 단계별로 나눈다.
- 중복 실행을 방지한다.
- 실패한 작업은 기존 생성 결과를 재사용할 수 있도록 한다.
- GitHub Actions 실행 시간 및 무료 사용량을 관리한다.

---

## 8. 비용 및 무료 운영 전략

초기 개발 단계에서는 가능한 한 무료 서비스를 사용한다.

### 무료 운영 대상

- Python: 무료
- GitHub Actions: 무료 사용량 한도 내
- Ollama: 무료
- Notion: 무료 플랜 범위 내
- Google Drive: 무료 저장공간 범위 내
- Telegram Bot: 무료

### 별도 비용이 발생할 수 있는 항목

- Gemini 등 외부 AI API의 무료 사용량 초과
- 이미지 생성 API
- Kling 등 AI 영상 생성
- 고품질 TTS
- Google Drive 저장공간 추가
- GitHub Actions 무료 한도 초과

초기에는 대본 생성 및 검수까지 무료로 구현하고, 이미지와 영상 생성은 비용을 확인한 후 연결한다.

무료 API의 사용 가능 여부와 한도는 실제 가입 시점에 확인한다.

---

## 9. 단계별 개발 일정

### Phase 1. Agent 기본 구조

- Python Agent 기본 클래스 구현
- AI API 연결 모듈 구현
- Planner Agent 구현
- Writer Agent 구현
- Reviewer Agent 구현
- GitHub Actions 실행 환경 구성

완료 기준:
30분 분량의 시니어 롱폼 대본을 자동 생성하고 검수할 수 있어야 한다.

### Phase 2. Notion 연동

- Notion API 연결
- DRAFT 등록
- 콘텐츠 상태 관리
- 챕터별 대본 저장
- 생성 이력 관리

완료 기준:
생성한 대본이 Notion에 자동 등록되어야 한다.

### Phase 3. 이미지 프롬프트 자동화

- Image Prompt Agent 구현
- 장면별 이미지 분할
- 등장인물 설정 관리
- Google Drive 폴더 생성
- 이미지 파일명 및 출처 관리

완료 기준:
대본을 기반으로 이미지 제작 자료가 자동 준비되어야 한다.

### Phase 4. 기존 렌더링 Pipeline 연동

- APPROVED 콘텐츠 조회
- Drive 자료 확인
- 기존 Python 렌더링 연동
- 영상 저장
- Telegram 알림

완료 기준:
사람이 승인한 콘텐츠가 자동으로 영상화되어야 한다.

### Phase 5. 운영 안정화

- 중복 실행 방지
- 실패 작업 재시도
- API 비용 관리
- 생성 결과 품질 평가
- YouTube 업로드 연동 검토

완료 기준:
반복적인 콘텐츠 제작이 안정적으로 가능해야 한다.

---

## 10. 최종 목표

moruu는 단순한 AI 영상 생성기가 아니라 콘텐츠 기획부터 영상 제작까지 연결하는 자동화 플랫폼을 목표로 한다.

최종적으로 다음 작업을 하나의 시스템에서 처리한다.

1. 시니어 롱폼 소재 발굴
2. 콘텐츠 기획 및 대본 생성
3. AI 대본 검수
4. 이미지 및 영상 제작 자료 생성
5. Notion 콘텐츠 관리
6. Google Drive 자료 관리
7. GitHub Actions 영상 렌더링
8. Telegram 작업 알림
9. YouTube 업로드

**최우선 개발 목표는 무료 또는 최소 비용으로 30분짜리 시니어 롱폼 대본을 안정적으로 생성하는 Agent를 완성하는 것이다.**

영상 생성 및 업로드 자동화는 이후 단계에서 확장한다.
