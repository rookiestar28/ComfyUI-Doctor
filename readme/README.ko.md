# ComfyUI-Doctor

[繁中](README.zh-TW.md) | [简中](README.zh-CN.md) | [日本語](README.ja.md) | 한국어 | [Deutsch](README.de.md) | [Français](README.fr.md) | [Italiano](README.it.md) | [Español](README.es.md) | [English](../README.md) | [로드맵 & 개발 현황](../ROADMAP.md)

ComfyUI를 위한 지속적이고 실시간 런타임 진단 제품군으로, **LLM 기반 분석**, **대화형 디버깅 채팅**, **50개 이상의 수정 패턴**을 특징으로 합니다. 시작 시부터 모든 터미널 출력을 자동으로 가로채고, 완전한 Python 트레이스백을 캡처하며, 노드 수준의 컨텍스트 추출과 함께 우선순위가 지정된 수정 제안을 제공합니다. 이제 핫 리로드가 가능한 **JSON 기반 패턴 관리**와 9개 언어(en, zh_TW, zh_CN, ja, de, fr, it, es, ko)에 대한 **완전한 i18n 지원**을 제공합니다.

## 최신 업데이트 (2026년 1월)

<details>
<summary><strong>업데이트 (v1.4.1, 2026년 1월)</strong> - 클릭하여 펼치기</summary>

- A7 Preact 마이그레이션 완료 (5A–5C 단계: Chat/Stats 아일랜드, 레지스트리, 공유 렌더링, 견고한 폴백).
- F15 해결 상태 표시: 통계 탭에서 최신 오류를 해결됨/미해결/무시로 표시; 상태가 저장되고 로드 시 반영됩니다.
- 통합 강화: resolution_status 백엔드 데이터 흐름 보강 및 Playwright E2E 커버리지 강화.
- UI 수정: Locate Node 버튼 지속성 및 사이드바 툴팁 타이밍 수정.

</details>

---

<details>
<summary><strong>F4: 통계 대시보드</strong> - 클릭하여 펼치기</summary>

**ComfyUI 안정성을 한눈에 파악하세요!**

ComfyUI-Doctor에 오류 추세, 일반적인 문제 및 해결 진행 상황에 대한 통찰력을 제공하는 **통계 대시보드**가 포함되었습니다.

**기능**:

- 📊 **오류 추세**: 24시간/7일/30일 오류 통계를 추적
- 🔥 **상위 5개 패턴**: 가장 자주 발생하는 오류 확인
- 📈 **카테고리별 분석**: 카테고리별(메모리, 워크플로, 모델 로딩 등)로 오류 시각화
- ✅ **해결 추적**: 해결됨 vs 미해결 오류 모니터링
- 🌍 **완전한 i18n 지원**: 9개 언어 모두 지원

![통계 대시보드](assets/statistics_panel.png)

**사용 방법**:

1. Doctor 사이드바 패널 열기 (왼쪽의 🏥 아이콘 클릭)
2. "📊 Error Statistics(오류 통계)" 섹션 펼치기
3. 실시간 오류 분석 및 추세 보기
4. 진행 상황을 추적하기 위해 오류를 해결됨/무시함으로 표시

**백엔드 API**:

- `GET /doctor/statistics?time_range_days=30` - 통계 가져오기
- `POST /doctor/mark_resolved` - 해결 상태 업데이트

**테스트 커버리지**: 17/17 백엔드 테스트 ✅ | 14/18 E2E 테스트 (78% 통과율)

**구현 세부 정보**: `.planning/260104-F4_STATISTICS_RECORD.md` 참조

</details>

---

<details>
<summary><strong>T8: 패턴 검증 CI</strong> - 클릭하여 펼치기</summary>

**자동화된 품질 검사로 이제 패턴 무결성을 보호합니다!**

ComfyUI-Doctor에는 모든 오류 패턴에 대한 **지속적인 통합 테스트**가 포함되어 무결점 기여를 보장합니다.

**T8 검증 항목**:

- ✅ **JSON 형식**: 8개 패턴 파일 모두 올바르게 컴파일됨
- ✅ **Regex 구문**: 57개 패턴 모두 유효한 정규식 보유
- ✅ **i18n 완전성**: 100% 번역 커버리지 (57개 패턴 × 9개 언어 = 513개 검사)
- ✅ **스키마 준수**: 필수 필드 (`id`, `regex`, `error_key`, `priority`, `category`)
- ✅ **메타데이터 품질**: 유효한 우선순위 범위(50-95), 고유 ID, 올바른 카테고리

**GitHub Actions 통합**:

- `patterns/`, `i18n.py` 또는 테스트에 영향을 주는 모든 푸시/PR에서 트리거됨
- 약 3초 만에 실행, 비용 $0 (GitHub Actions 무료 등급)
- 검증 실패 시 병합 차단

**기여자용**:

```bash
# 커밋 전 로컬 검증
python run_pattern_tests.py

# 출력:
✅ All 57 patterns have required fields
✅ All 57 regex patterns compile successfully
✅ en: All 57 patterns have translations
✅ zh_TW: All 57 patterns have translations
... (총 9개 언어)
```

**테스트 결과**: 모든 검사에서 100% 통과율

**구현 세부 정보**: `.planning/260103-T8_IMPLEMENTATION_RECORD.md` 참조

</details>

---

<details>
<summary><strong>4B 단계: 패턴 시스템 개편 (1-3단계 완료)</strong> - 클릭하여 펼치기</summary>

ComfyUI-Doctor는 **57개 이상의 오류 패턴**과 **JSON 기반 패턴 관리**를 통해 대대적인 아키텍처 업그레이드를 거쳤습니다!

**1단계: 로거 아키텍처 수정**

- 대기열 기반 백그라운드 처리가 포함된 SafeStreamWrapper 구현
- 교착 상태 위험 및 경쟁 조건 제거
- ComfyUI의 LogInterceptor와의 로그 가로채기 충돌 수정

**2단계: JSON 패턴 관리 (F2)**

- 핫 리로드 기능이 있는 새로운 PatternLoader (재시작 필요 없음!)
- 패턴은 `patterns/` 디렉터리 아래의 JSON 파일에 정의됨
- `patterns/builtin/core.json`에 22개의 내장 패턴
- 확장 및 유지 관리 용이

**3단계: 커뮤니티 패턴 확장 (F12)**

- 인기 있는 확장을 다루는 **35개의 새로운 커뮤니티 패턴**:
  - **ControlNet** (8개 패턴): 모델 로딩, 전처리, 이미지 크기
  - **LoRA** (6개 패턴): 로딩 오류, 호환성, 가중치 문제
  - **VAE** (5개 패턴): 인코딩/디코딩 실패, 정밀도, 타일링
  - **AnimateDiff** (4개 패턴): 모델 로딩, 프레임 수, 컨텍스트 길이
  - **IPAdapter** (4개 패턴): 모델 로딩, 이미지 인코딩, 호환성
  - **FaceRestore** (3개 패턴): CodeFormer/GFPGAN 모델, 감지
  - **기타** (5개 패턴): 체크포인트, 샘플러, 스케줄러, CLIP
- 영어, 중국어 번체, 중국어 간체에 대한 완전한 i18n 지원
- 총계: **57개 오류 패턴** (22개 내장 + 35개 커뮤니티)

**이점**:

- ✅ 더 포괄적인 오류 커버리지
- ✅ ComfyUI 재시작 없이 패턴 핫 리로드
- ✅ 커뮤니티에서 JSON 파일을 통해 패턴 기여 가능
- ✅ 더 깔끔하고 유지 관리하기 쉬운 코드베이스

</details>

---

<details>
<summary><strong>이전 업데이트 (2025년 12월)</strong> - 클릭하여 펼치기</summary>

### F9: 다국어 지원 확장

언어 지원을 4개 언어에서 9개 언어로 확장했습니다! ComfyUI-Doctor는 이제 다음 언어로 오류 제안을 제공합니다.

- **English** 영어 (en)
- **繁體中文** 중국어 번체 (zh_TW)
- **简体中文** 중국어 간체 (zh_CN)
- **日本語** 일본어 (ja)
- **🆕 Deutsch** 독일어 (de)
- **🆕 Français** 프랑스어 (fr)
- **🆕 Italiano** 이탈리아어 (it)
- **🆕 Español** 스페인어 (es)
- **🆕 한국어** (ko)

57개 오류 패턴 모두 모든 언어로 완벽하게 번역되어 전 세계적으로 일관된 진단 품질을 보장합니다.

### F8: 사이드바 설정 통합

설정이 간소화되었습니다! 사이드바에서 직접 Doctor를 구성하세요.

- 사이드바 헤더의 ⚙️ 아이콘을 클릭하여 모든 설정에 액세스
- 언어 선택 (9개 언어)
- AI 제공자 빠른 전환 (OpenAI, DeepSeek, Groq, Gemini, Ollama 등)
- 제공자 변경 시 기본 URL 자동 입력
- API 키 관리 (비밀번호 보호 입력)
- 모델 이름 구성
- 설정은 localStorage를 통해 세션 간 유지됨
- 저장 시 시각적 피드백 (✅ 저장됨! / ❌ 오류)

ComfyUI 설정 패널에는 이제 활성화/비활성화 토글만 표시되며, 다른 모든 설정은 더 깔끔하고 통합된 환경을 위해 사이드바로 이동되었습니다.

</details>

---

## 기능

- **자동 오류 모니터링**: 모든 터미널 출력을 캡처하고 실시간으로 Python 트레이스백을 감지
- **지능형 오류 분석**: 57개 이상의 오류 패턴(22개 내장 + 35개 커뮤니티)과 실행 가능한 제안
- **노드 컨텍스트 추출**: 오류를 일으킨 노드 식별 (노드 ID, 이름, 클래스)
- **시스템 환경 컨텍스트**: AI 분석 시 Python 버전, 설치된 패키지(pip list), OS 정보를 자동으로 포함
- **다국어 지원**: 9개 언어 지원 (영어, 중국어 번체, 중국어 간체, 일본어, 독일어, 프랑스어, 이탈리아어, 스페인어, 한국어)
- **JSON 기반 패턴 관리**: ComfyUI 재시작 없이 오류 패턴 핫 리로드
- **커뮤니티 패턴 지원**: ControlNet, LoRA, VAE, AnimateDiff, IPAdapter, FaceRestore 등을 커버
- **디버그 검사기 노드**: 워크플로를 통해 흐르는 데이터에 대한 심층 검사
- **오류 기록**: API를 통해 최근 오류 버퍼 유지
- **RESTful API**: 프런트엔드 통합을 위한 7개의 엔드포인트
- **AI 기반 분석**: 8개 이상의 제공자(OpenAI, DeepSeek, Groq, Gemini, Ollama, LMStudio 등)를 지원하는 원클릭 LLM 오류 분석
- **대화형 채팅 인터페이스**: ComfyUI 사이드바에 통합된 멀티턴 AI 디버깅 도우미
- **대화형 사이드바 UI**: 노드 위치 확인 및 즉각적인 진단을 위한 시각적 오류 패널
- **유연한 구성**: 동작 사용자 정의를 위한 포괄적인 설정 패널

### 🆕 AI 채팅 인터페이스

새로운 대화형 채팅 인터페이스는 ComfyUI의 왼쪽 사이드바 내에서 직접 대화형 디버깅 경험을 제공합니다. 오류가 발생하면 "Analyze with AI"를 클릭하여 선호하는 LLM과 멀티턴 대화를 시작할 수 있습니다.

<div align="center">
<img src="assets/chat-ui.png" alt="AI Chat Interface">
</div>

**주요 기능:**

- **컨텍스트 인식**: 오류 세부 정보, 노드 정보 및 워크플로 컨텍스트를 자동으로 포함
- **환경 인식**: 정확한 디버깅을 위해 Python 버전, 설치된 패키지 및 OS 정보 포함
- **스트리밍 응답**: 적절한 서식을 갖춘 실시간 LLM 응답
- **멀티턴 대화**: 문제를 더 깊이 파고들기 위한 후속 질문 가능
- **항상 액세스 가능**: 입력 영역은 고정 위치(sticky positioning)로 하단에 항상 표시됨
- **8개 이상의 LLM 제공자 지원**: OpenAI, DeepSeek, Groq, Gemini, Ollama, LMStudio 등
- **스마트 캐싱**: 성능 영향을 피하기 위해 패키지 목록을 24시간 동안 캐시

**사용 방법:**

1. 오류가 발생하면 Doctor 사이드바(왼쪽 패널) 열기
2. 오류 컨텍스트 영역의 "✨ Analyze with AI" 버튼 클릭
3. AI가 자동으로 오류를 분석하고 제안을 제공
4. 계속 대화하려면 입력 상자에 후속 질문 입력
5. Enter를 누르거나 "Send"를 클릭하여 메시지 전송

> **💡 무료 API 팁**: [Google AI Studio](https://aistudio.google.com/app/apikey) (Gemini)는 신용 카드 없이도 넉넉한 무료 등급을 제공합니다. 비용 없이 AI 기반 디버깅을 시작하기에 완벽합니다!

---

## 설치

### 옵션 1: ComfyUI-Manager 사용 (권장)

1. ComfyUI를 열고 메뉴에서 **Manager** 버튼 클릭
2. **Install Custom Nodes** 선택
3. `ComfyUI-Doctor` 검색
4. **Install**을 클릭하고 ComfyUI 재시작

### 옵션 2: 수동 설치 (Git Clone)

1. ComfyUI 사용자 지정 노드 디렉터리로 이동:

   ```bash
   cd ComfyUI/custom_nodes/
   ```

2. 이 저장소 복제:

   ```bash
   git clone https://github.com/rookiestar28/ComfyUI-Doctor.git
   ```

3. ComfyUI 재시작

4. 콘솔에서 초기화 메시지를 찾아 설치 확인:

   ```text
   [ComfyUI-Doctor] Initializing Smart Debugger...
   [ComfyUI-Doctor] Log file: .../logs/comfyui_debug_2025-12-28.log
   
   ==================== SYSTEM SNAPSHOT ====================
   OS: Windows 11
   Python: 3.12.3
   PyTorch: 2.0.1+cu118
   CUDA Available: True
   ...
   ```

---

## 사용 방법

### 패시브 모드 (자동)

설치되면 ComfyUI-Doctor는 자동으로 다음을 수행합니다.

- 모든 콘솔 출력을 `logs/` 디렉터리에 기록
- 오류 감지 및 제안 제공
- 시스템 환경 정보 기록

**오류 출력 예**:

```
Traceback (most recent call last):
  ...
RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB

----------------------------------------
ERROR LOCATION: Node ID: #42 | Name: KSampler
SUGGESTION: OOM (메모리 부족): GPU VRAM이 가득 찼습니다. 시도해 보세요:
   1. 배치 크기 줄이기
   2. '--lowvram' 플래그 사용
   3. 다른 GPU 앱 닫기
----------------------------------------
```

### 액티브 모드 (디버그 노드)

1. 캔버스에서 우클릭 → `Add Node` → `Smart Debug Node`
2. 노드를 모든 연결에 인라인으로 연결 (와일드카드 입력 `*` 지원)
3. 워크플로 실행

**출력 예**:

```text
[DEBUG] Data Inspection:
  Type: Tensor
  Shape: torch.Size([1, 4, 64, 64])
  Dtype: torch.float16
  Device: cuda:0
  Stats (All): Min=-3.2156, Max=4.8912, Mean=0.0023
```

이 노드는 워크플로 실행에 영향을 주지 않고 데이터를 통과시킵니다.

---

## 프런트엔드 UI

ComfyUI-Doctor는 실시간 오류 모니터링 및 진단을 위한 대화형 사이드바 인터페이스를 제공합니다.

### Doctor 패널 액세스

ComfyUI 메뉴(왼쪽 사이드바)에서 **🏥 Doctor** 버튼을 클릭하여 Doctor 패널을 엽니다. 패널이 화면 오른쪽에서 슬라이드하여 나타납니다.

### 인터페이스 기능

<div align="center">
<img src="assets/doctor-side-bar.png" alt="Error Report">
</div>

Doctor 인터페이스는 두 개의 패널로 구성됩니다.

#### 왼쪽 사이드바 패널 (Doctor 사이드바)

ComfyUI 왼쪽 메뉴의 **🏥 Doctor** 아이콘을 클릭하여 액세스:

- **설정 패널** (⚙️ 아이콘): 언어, AI 제공자, API 키 및 모델 선택 구성
- **오류 컨텍스트 카드**: 오류 발생 시 표시:
  - **💡 제안**: 간결하고 실행 가능한 조언 (예: "입력 연결을 확인하고 노드 요구 사항을 충족하는지 확인하세요.")
  - **타임스탬프**: 오류 발생 시간
  - **노드 컨텍스트**: 노드 ID 및 이름 (해당되는 경우)
  - **✨ Analyze with AI**: 상세 디버깅을 위한 대화형 채팅 시작
- **AI 채팅 인터페이스**: 심층적인 오류 분석을 위한 LLM과의 멀티턴 대화
- **고정 입력 영역**: 하단에서 항상 액세스 가능하여 후속 질문이 용이함

#### 오른쪽 오류 패널 (최신 진단)

오른쪽 상단의 실시간 오류 알림:

![Doctor Error Report](./assets/error-report.png)

- **상태 표시기**: 시스템 상태를 보여주는 컬러 점
  - 🟢 **녹색**: 시스템 정상 작동, 오류 감지되지 않음
  - 🔴 **빨간색 (깜박임)**: 활성 오류 감지됨
- **최신 진단 카드**: 가장 최근 오류 표시:
  - **오류 요약**: 짧은 오류 설명 (빨간색 테마, 긴 경우 접기 가능)
  - **💡 제안**: 간결하고 실행 가능한 조언 (녹색 테마)
  - **타임스탬프**: 오류 발생 시간
  - **노드 컨텍스트**: 노드 ID, 이름 및 클래스
  - **🔍 캔버스에서 노드 찾기**: 문제가 있는 노드를 자동으로 중앙에 배치하고 강조 표시

**주요 디자인 원칙**:

- ✅ **간결한 제안**: 장황한 오류 설명 대신 실행 가능한 조언만 표시 (예: "입력 연결 확인...")
- ✅ **시각적 분리**: 오류 메시지(빨간색)와 제안(녹색)이 명확하게 구분됨
- ✅ **스마트 트렁케이션**: 긴 오류는 처음 3줄 + 마지막 3줄을 표시하고 전체 세부 정보를 펼칠 수 있음
- ✅ **실시간 업데이트**: WebSocket 이벤트를 통해 새 오류가 발생하면 두 패널 모두 자동으로 업데이트됨

---

## AI 기반 오류 분석

ComfyUI-Doctor는 널리 사용되는 LLM 서비스와 통합하여 지능적이고 상황을 인식하는 디버깅 제안을 제공합니다.

### 지원되는 AI 제공자

#### 클라우드 서비스

- **OpenAI** (GPT-4, GPT-4o 등)
- **DeepSeek** (DeepSeek-V2, DeepSeek-Coder)
- **Groq Cloud** (Llama 3, Mixtral - 초고속 LPU 추론)
- **Google Gemini** (Gemini Pro, Gemini Flash)
- **xAI Grok** (Grok-2, Grok-beta)
- **OpenRouter** (Claude, GPT-4 및 100개 이상의 모델에 액세스)

#### 로컬 서비스 (API 키 필요 없음)

- **Ollama** (`http://127.0.0.1:11434`) - Llama, Mistral, CodeLlama를 로컬에서 실행
- **LMStudio** (`http://localhost:1234/v1`) - GUI가 있는 로컬 모델 추론

> **💡 크로스 플랫폼 호환성**: 기본 URL은 환경 변수를 통해 재정의할 수 있습니다.
>
> - `OLLAMA_BASE_URL` - 사용자 지정 Ollama 엔드포인트 (기본: `http://127.0.0.1:11434`)
> - `LMSTUDIO_BASE_URL` - 사용자 지정 LMStudio 엔드포인트 (기본: `http://localhost:1234/v1`)
>
> 이렇게 하면 Windows와 WSL2 Ollama 인스턴스 간의 충돌이나 Docker/사용자 지정 설정에서 실행할 때의 충돌을 방지할 수 있습니다.

### 구성

![설정 패널](./assets/settings.png)

**Doctor 사이드바** → **Settings** 패널에서 AI 분석 구성:

1. **AI Provider**: 드롭다운 메뉴에서 선택합니다. 기본 URL이 자동 입력됩니다.
2. **AI Base URL**: API 엔드포인트 (자동 채워지지만 사용자 지정 가능)
3. **AI API Key**: API 키 (Ollama/LMStudio와 같은 로컬 LLM의 경우 비워 둠)
4. **AI Model Name**:
   - 드롭다운 목록에서 모델 선택 (제공자의 API에서 자동으로 채워짐)
   - 🔄 새로 고침 버튼을 클릭하여 사용 가능한 모델 다시 로드
   - 또는 "Enter model name manually"를 체크하여 사용자 지정 모델 이름 입력
5. **Privacy Mode**: 클라우드 AI 서비스에 대한 PII 삭제 수준 선택 (자세한 내용은 아래 [개인정보 보호 모드 (PII 삭제)](#개인정보-보호-모드-pii-삭제) 섹션 참조)

### AI 분석 사용

1. 오류가 발생하면 자동으로 Doctor 패널이 열립니다.
2. 내장된 제안을 검토하거나 오류 카드의 ✨ Analyze with AI 버튼을 클릭합니다.
3. LLM이 오류를 분석할 때까지 기다립니다(일반적으로 3~10초).
4. AI가 생성한 디버깅 제안을 검토합니다.

**보안 참고 사항**: API 키는 분석 요청을 위해 프런트엔드에서 백엔드로 안전하게 전송될 뿐입니다. 기록되거나 영구적으로 저장되지 않습니다.

### 개인정보 보호 모드 (PII 삭제)

ComfyUI-Doctor에는 클라우드 AI 서비스로 오류 메시지를 보낼 때 개인정보를 보호하기 위한 자동 **PII(개인 식별 정보) 삭제** 기능이 포함되어 있습니다.

**세 가지 개인정보 보호 수준**:

| 수준 | 설명 | 제거되는 내용 | 권장 대상 |
| ----- | ----------- | --------------- | --------------- |
| **None** | 삭제 없음 | 없음 | 로컬 LLM (Ollama, LMStudio) |
| **Basic** (기본값) | 표준 보호 | 사용자 경로, API 키, 이메일, IP 주소 | 클라우드 LLM을 사용하는 대부분의 사용자 |
| **Strict** | 최대 개인정보 보호 | Basic의 모든 항목 + IPv6, SSH 지문 | 엔터프라이즈/규정 준수 요구 사항 |

**삭제되는 내용** (Basic 수준):

- ✅ Windows 사용자 경로: `C:\Users\john\file.py` → `<USER_PATH>\file.py`
- ✅ Linux/macOS 홈: `/home/alice/test.py` → `<USER_HOME>/test.py`
- ✅ API 키: `sk-abc123...` → `<API_KEY>`
- ✅ 이메일 주소: `user@example.com` → `<EMAIL>`
- ✅ 사설 IP: `192.168.1.1` → `<PRIVATE_IP>`
- ✅ URL 자격 증명: `https://user:pass@host` → `https://<USER>@host`

**제거되지 않는 내용**:

- ❌ 오류 메시지 (디버깅에 필요)
- ❌ 모델 이름, 노드 이름
- ❌ 워크플로 구조
- ❌ 공용 파일 경로 (`/usr/bin/python`)

**개인정보 보호 모드 구성**: Doctor 사이드바 열기 → Settings → 🔒 Privacy Mode 드롭다운. 변경 사항은 모든 AI 분석 요청에 즉시 적용됩니다.

**GDPR 준수**: 이 기능은 GDPR 제25조(설계에 의한 데이터 보호)를 지원하며 엔터프라이즈 배포에 권장됩니다.

### 통계 대시보드

![통계 패널](assets/statistics_panel.png)

**통계 대시보드**는 ComfyUI 오류 패턴 및 안정성 추세에 대한 실시간 통찰력을 제공합니다.

**기능**:

- **📊 오류 추세**: 지난 24시간/7일/30일 동안의 총 오류 및 개수
- **🔥 최상위 오류 패턴**: 발생 횟수가 가장 많은 상위 5개 오류 유형
- **📈 카테고리별 분석**: 오류 카테고리(메모리, 워크플로, 모델 로딩, 프레임워크, 일반)별 시각적 분석
- **✅ 해결 추적**: 해결됨, 미해결, 무시된 오류 추적
- **🧭 상태 제어**: 통계 탭에서 최신 오류를 해결됨 / 미해결 / 무시로 표시

**사용 방법**:

1. Doctor 사이드바 열기 (왼쪽의 🏥 아이콘 클릭)
2. **📊 Error Statistics** 접을 수 있는 섹션 찾기
3. 클릭하여 펼치고 오류 분석 보기
4. **표시** 버튼으로 최신 오류 상태를 설정(해결됨 / 미해결 / 무시)

**해결 상태 제어**:

- 최신 오류 타임스탬프가 있을 때만 버튼이 활성화됨
- 상태 업데이트는 히스토리에 저장되며 해결률을 자동으로 갱신함

**데이터 이해**:

- **Total (30d)**: 지난 30일 동안의 누적 오류
- **Last 24h**: 지난 24시간 동안의 오류 (최근 문제 식별에 도움)
- **Resolution Rate (해결률)**: 알려진 문제 해결 진행 상황 표시
  - 🟢 **Resolved**: 수정한 문제
  - 🟠 **Unresolved**: 주의가 필요한 활성 문제
  - ⚪ **Ignored**: 무시하기로 선택한 중요하지 않은 문제
- **Top Patterns**: 우선적으로 주의가 필요한 오류 유형 식별
- **Categories**: 문제가 메모리 관련, 워크플로 문제, 모델 로딩 실패 등인지 이해하는 데 도움

**패널 상태 유지**: 패널의 열림/닫힘 상태는 브라우저의 localStorage에 저장되므로 기본 설정이 세션 간 유지됩니다.

### 공급자 설정 예

| 공급자 | 기본 URL | 모델 예 |
|------------------|------------------------------------------------------------|------------------------------|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| Groq | `https://api.groq.com/openai/v1` | `llama-3.1-70b-versatile` |
| Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-1.5-flash` |
| Ollama (Local) | `http://localhost:11434/v1` | `llama3.1:8b` |
| LMStudio (Local) | `http://localhost:1234/v1` | LMStudio에 로드된 모델 |

---

## 설정

ComfyUI 설정 패널(톱니바퀴 아이콘)을 통해 ComfyUI-Doctor 동작을 사용자 지정할 수 있습니다.

### 1. Show error notifications (오류 알림 표시)

**기능**: 오른쪽 상단 모서리에 떠 있는 오류 알림 카드(토스트)를 토글합니다.
**용도**: 시각적 방해 없이 사이드바에서 수동으로 오류를 확인하려는 경우 비활성화합니다.

### 2. Auto-open panel on error (오류 시 패널 자동 열기)

**기능**: 새 오류가 감지되면 Doctor 사이드바를 자동으로 펼칩니다.
**용도**: **권장됨**. 수동으로 클릭하지 않고도 진단 결과에 즉시 액세스할 수 있습니다.

### 3. Error Check Interval (ms)

**기능**: 프런트엔드-백엔드 오류 확인 빈도(밀리초). 기본값: `2000`.
**용도**: 낮은 값(예: 500)은 더 빠른 피드백을 제공하지만 부하를 증가시킵니다. 높은 값(예: 5000)은 리소스를 절약합니다.

### 4. Suggestion Language (제안 언어)

**기능**: 진단 보고서 및 Doctor 제안에 대한 언어입니다.
**용도**: 현재 영어, 중국어 번체, 중국어 간체, 일본어를 지원합니다(더 많은 언어 제공 예정). 변경 사항은 새 오류에 적용됩니다.

### 5. Enable Doctor (requires restart)

**기능**: 로그 가로채기 시스템의 마스터 스위치입니다.
**용도**: Doctor의 핵심 기능을 완전히 비활성화하려면 끕니다(ComfyUI 다시 시작 필요).

### 6. AI Provider

**기능**: 드롭다운 메뉴에서 선호하는 LLM 서비스 공급자를 선택합니다.
**옵션**: OpenAI, DeepSeek, Groq Cloud, Google Gemini, xAI Grok, OpenRouter, Ollama (Local), LMStudio (Local), Custom.
**용도**: 공급자를 선택하면 적절한 기본 URL이 자동으로 채워집니다. 로컬 공급자(Ollama/LMStudio)의 경우 사용 가능한 모델을 표시하는 경고가 표시됩니다.

### 7. AI Base URL

**기능**: LLM 서비스의 API 엔드포인트입니다.
**용도**: 공급자를 선택할 때 자동 채워지지만 자체 호스팅 또는 사용자 지정 엔드포인트에 대해 사용자 지정할 수 있습니다.

### 8. AI API Key

**기능**: 클라우드 LLM 서비스 인증을 위한 API 키입니다.
**용도**: 클라우드 공급자(OpenAI, DeepSeek 등)에 필수입니다. 로컬 LLM(Ollama, LMStudio)의 경우 비워 둡니다.
**보안**: 키는 분석 요청 중에만 전송되며 기록되거나 유지되지 않습니다.

### 9. AI Model Name

**기능**: 오류 분석에 사용할 모델을 지정합니다.
**용도**:

- **드롭다운 모드** (기본값): 자동으로 채워진 드롭다운 목록에서 모델을 선택합니다. 🔄 새로 고침 버튼을 클릭하여 사용 가능한 모델을 다시 로드합니다.
- **수동 입력 모드**: "Enter model name manually"를 체크하여 사용자 지정 모델 이름(예: `gpt-4o`, `deepseek-chat`, `llama3.1:8b`)을 입력합니다.
- 공급자를 변경하거나 새로 고침을 클릭하면 선택한 공급자의 API에서 모델을 자동으로 가져옵니다.
- 로컬 LLM(Ollama/LMStudio)의 경우 드롭다운에 로컬에서 사용 가능한 모든 모델이 표시됩니다.

---

## API 엔드포인트

### GET `/debugger/last_analysis`

가장 최근 오류 분석 검색:

```bash
curl http://localhost:8188/debugger/last_analysis
```

**응답 예**:

```json
{
  "status": "running",
  "log_path": ".../logs/comfyui_debug_2025-12-28.log",
  "language": "zh_TW",
  "supported_languages": ["en", "zh_TW", "zh_CN", "ja"],
  "last_error": "Traceback...",
  "suggestion": "SUGGESTION: ...",
  "timestamp": "2025-12-28T06:49:11",
  "node_context": {
    "node_id": "42",
    "node_name": "KSampler",
    "node_class": "KSamplerNode",
    "custom_node_path": "ComfyUI-Impact-Pack"
  }
}
```

### GET `/debugger/history`

오류 기록 검색 (최근 20개 항목):

```bash
curl http://localhost:8188/debugger/history
```

### POST `/debugger/set_language`

제안 언어를 변경합니다 (언어 전환 섹션 참조).

### POST `/doctor/analyze`

구성된 LLM 서비스를 사용하여 오류를 분석합니다.

**페이로드**:

```json
{
  "error": "Traceback...",
  "node_context": {...},
  "api_key": "your-api-key",
  "base_url": "https://api.openai.com/v1",
  "model": "gpt-4o",
  "language": "en"
}
```

**응답**:

```json
{
  "analysis": "AI-generated debugging suggestions..."
}
```

### POST `/doctor/verify_key`

LLM 공급자에 대한 연결을 테스트하여 API 키 유효성을 확인합니다.

**페이로드**:

```json
{
  "base_url": "https://api.openai.com/v1",
  "api_key": "your-api-key"
}
```

**응답**:

```json
{
  "success": true,
  "message": "API key is valid",
  "is_local": false
}
```

### POST `/doctor/list_models`

구성된 LLM 공급자에서 사용 가능한 모델을 나열합니다.

**페이로드**:

```json
{
  "base_url": "http://localhost:11434/v1",
  "api_key": ""
}
```

**응답**:

```json
{
  "success": true,
  "models": [
    {"id": "llama3.1:8b", "name": "llama3.1:8b"},
    {"id": "mistral:7b", "name": "mistral:7b"}
  ],
  "message": "Found 2 models"
}
```

---

## 로그 파일

모든 로그는 다음에 저장됩니다.

```text
ComfyUI/custom_nodes/ComfyUI-Doctor/logs/
```

파일 이름 형식: `comfyui_debug_YYYY-MM-DD_HH-MM-SS.log`

시스템은 가장 최근 10개의 로그 파일을 자동으로 유지합니다(`config.json`을 통해 구성 가능).

---

## 구성

`config.json`을 생성하여 동작을 사용자 정의합니다.

```json
{
  "max_log_files": 10,
  "buffer_limit": 100,
  "traceback_timeout_seconds": 5.0,
  "history_size": 20,
  "default_language": "zh_TW",
  "enable_api": true,
  "privacy_mode": "basic"
}
```

**매개 변수**:

- `max_log_files`: 유지할 로그 파일의 최대 수
- `buffer_limit`: 트레이스백 버퍼 크기 (줄 수)
- `traceback_timeout_seconds`: 불완전한 트레이스백에 대한 시간 초과
- `history_size`: 기록에 유지할 오류 수
- `default_language`: 기본 제안 언어
- `enable_api`: API 엔드포인트 활성화
- `privacy_mode`: PII 삭제 수준 - `"none"`, `"basic"` (기본값) 또는 `"strict"`

---

## 지원되는 오류 패턴

ComfyUI-Doctor는 다음을 감지하고 제안을 제공할 수 있습니다.

- 유형 불일치 (예: fp16 vs float32)
- 차원 불일치
- CUDA/MPS 메모리 부족 (OOM)
- 행렬 곱셈 오류
- 장치/유형 충돌
- 누락된 Python 모듈
- 어설션 실패
- 키/속성 오류
- 모양 불일치
- 파일을 찾을 수 없음 오류
- SafeTensors 로딩 오류
- CUDNN 실행 실패
- 누락된 InsightFace 라이브러리
- 모델/VAE 불일치
- 유효하지 않은 프롬프트 JSON

기타 등등...

---

## 팁

1. **ComfyUI Manager와 함께 사용**: 누락된 사용자 지정 노드 자동 설치
2. **로그 파일 확인**: 문제 보고를 위해 전체 트레이스백이 기록됩니다.
3. **내장 사이드바 사용**: 왼쪽 메뉴의 🏥 Doctor 아이콘을 클릭하여 실시간 진단
4. **노드 디버깅**: 의심스러운 데이터 흐름을 검사하기 위해 디버그 노드 연결

---

## 라이선스

MIT License

---

## 기여

기여는 환영합니다! 풀 리퀘스트를 자유롭게 제출해 주세요.

**문제 보고**: 버그를 발견했거나 제안 사항이 있습니까? GitHub에서 이슈를 열어주세요.
**PR 제출**: 버그 수정 또는 일반적인 개선으로 코드베이스를 개선하는 데 도움을 주세요.
**기능 요청**: 새로운 기능에 대한 아이디어가 있습니까? 저희에게 알려주세요.
