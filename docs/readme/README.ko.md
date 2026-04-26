# ComfyUI-Doctor

[繁中](README.zh-TW.md) | [简中](README.zh-CN.md) | [日本語](README.ja.md) | 한국어 | [Deutsch](README.de.md) | [Français](README.fr.md) | [Italiano](README.it.md) | [Español](README.es.md) | [English](../../README.md) |

<div align="center">
<img src="../../assets/icon.png" alt="ComfyUI Doctor">
</div>

ComfyUI-Doctor는 ComfyUI용 실시간 진단 및 디버깅 도우미입니다. 런타임 오류를 캡처하고, 관련 가능성이 높은 노드 컨텍스트를 식별하며, 실행 가능한 로컬 제안을 보여 줍니다. 선택적으로 LLM 채팅 workflow를 사용해 더 깊은 문제 해결도 할 수 있습니다.

## 최신 업데이트

최신 업데이트는 영어 README를 기준으로 합니다. [Latest Updates](../../README.md#latest-updates---click-to-expand)를 참조하세요.

## 주요 기능

- 시작 단계부터 ComfyUI console/error 출력을 실시간으로 캡처합니다.
- 22개의 core pattern과 36개의 community-extension pattern을 포함한 58개의 JSON 기반 오류 패턴 제안을 내장합니다.
- ComfyUI가 충분한 이벤트 데이터를 제공할 때 최근 workflow 실행 오류의 노드 컨텍스트를 검증하여 추출합니다.
- Doctor 사이드바는 Chat, Statistics, Settings 탭을 제공합니다.
- OpenAI-compatible services, Anthropic, Gemini, xAI, OpenRouter, Ollama, LMStudio를 통한 선택적 LLM 분석을 지원하며 통합 provider request/response 처리를 사용합니다.
- 외부 LLM 요청을 위해 경로, 키, 이메일, IP sanitization mode를 포함한 privacy controls를 제공합니다.
- 선택적 서버 측 credential store는 admin guarding과 encryption-at-rest를 지원합니다.
- 로컬 diagnostics, statistics, plugin trust report, telemetry controls, community feedback preview/submit tools를 제공합니다.
- Doctor API 실패 응답은 일관된 JSON error envelope를 사용합니다.
- UI와 제안은 영어, 번체 중국어, 간체 중국어, 일본어, 한국어, 독일어, 프랑스어, 이탈리아어, 스페인어를 완전히 지원합니다.

## 스크린샷

<div align="center">
<img src="../../assets/chat-ui.png" alt="Doctor chat interface">
</div>

<div align="center">
<img src="../../assets/doctor-side-bar.png" alt="Doctor sidebar">
</div>

## 설치

### ComfyUI-Manager

1. ComfyUI를 열고 **Manager**를 클릭합니다.
2. **Install Custom Nodes**를 선택합니다.
3. `ComfyUI-Doctor`를 검색합니다.
4. 설치 후 ComfyUI를 다시 시작합니다.

### 수동 설치

```bash
cd ComfyUI/custom_nodes/
git clone https://github.com/rookiestar28/ComfyUI-Doctor.git
```

Clone 후 ComfyUI를 다시 시작하세요. Doctor는 시작 진단을 출력하고 `Doctor` 사이드바 항목을 등록합니다.

## 기본 사용법

### 자동 진단

설치 후 Doctor는 ComfyUI 런타임 출력을 수동으로 기록하고 traceback을 감지하며 알려진 오류 패턴과 매칭한 뒤 최신 진단을 사이드바와 선택적 오른쪽 보고서 패널에 표시합니다.
선택적 LLM 분석을 사용할 때 Doctor는 sanitization, node context, execution logs, workflow pruning, system information을 처리하는 동일한 구조화 pipeline에서 prompt context를 구성합니다.

### Doctor 사이드바

ComfyUI 왼쪽 사이드바에서 **Doctor**를 엽니다.

- **Chat**: 최신 오류 컨텍스트를 검토하고 후속 디버깅 질문을 합니다.
- **Statistics**: 최근 오류 추세, diagnostics, trust/health information, telemetry controls, feedback tools를 확인합니다.
- **Settings**: 언어, LLM provider, base URL, model, privacy mode, 자동 열기 동작, 선택적 서버 측 credential storage를 선택합니다.

### Smart Debug Node

Canvas를 오른쪽 클릭해 **Smart Debug Node**를 추가하고, workflow output을 변경하지 않고 전달 데이터를 검사하도록 workflow 안에 배치합니다.

## 선택적 LLM 설정

Cloud provider는 session-only UI field, 환경 변수, 또는 선택적 admin-gated server store를 통해 credential을 제공해야 합니다. Ollama와 LMStudio 같은 로컬 provider는 cloud credential 없이 실행할 수 있습니다.
Doctor는 OpenAI-compatible APIs, Anthropic, Ollama의 provider-specific request/response 형식을 정규화하여 chat, single-shot analysis, model listing, connectivity check가 동일한 백엔드 동작을 공유하게 합니다.

권장 기본값:

- Cloud provider에는 **Privacy Mode: Basic** 또는 **Strict**를 사용합니다.
- 공유 또는 production 유사 환경에서는 환경 변수를 사용합니다.
- 공유 서버에서는 `DOCTOR_ADMIN_TOKEN`과 `DOCTOR_REQUIRE_ADMIN_TOKEN=1`을 설정합니다.
- local-only loopback convenience mode는 단일 사용자 데스크톱 용도로만 유지하세요.

## 문서

- [User Guide](../USER_GUIDE.md): UI walkthrough, diagnostics, privacy modes, LLM setup, feedback flow.
- [Configuration and Security](../CONFIGURATION_SECURITY.md): environment variables, admin guard behavior, credential storage, outbound safety, telemetry, CSP notes.
- [API Reference](../API_REFERENCE.md): public Doctor and debugger endpoints.
- [Validation Guide](../VALIDATION.md): local full-gate commands and optional compatibility/coverage lanes.
- [Plugin Guide](../PLUGIN_GUIDE.md): community plugin trust model and plugin authoring notes.
- [Plugin Migration](../PLUGIN_MIGRATION.md): migration tooling for plugin manifests and allowlists.
- [Outbound Safety](../OUTBOUND_SAFETY.md): static checker and outbound request safety rules.

## 지원되는 오류 패턴

패턴은 `patterns/` 아래의 JSON 파일로 저장되며 코드 변경 없이 업데이트할 수 있습니다.

| Pack | Count |
| --- | ---: |
| Core builtin patterns | 22 |
| Community extension patterns | 36 |
| **Total** | **58** |

Community pack은 현재 일반적인 ControlNet, LoRA, VAE, AnimateDiff, IPAdapter, FaceRestore, checkpoint, sampler, scheduler, CLIP failure modes를 다룹니다.

## 검증

로컬 CI-parity 검증에는 프로젝트 full-test script를 사용합니다.

```powershell
powershell -File scripts/run_full_tests_windows.ps1
```

```bash
bash scripts/run_full_tests_linux.sh
```

Full gate는 secrets detection, pre-commit hooks, host-like startup validation, backend unit tests, frontend Playwright E2E tests를 포함합니다. 명시적인 단계별 명령과 선택적 lanes는 [Validation Guide](../VALIDATION.md)를 참조하세요.

## 요구 사항

- ComfyUI custom-node 환경.
- Python 3.10 이상.
- Node.js 18 이상은 frontend E2E validation에만 필요합니다.
- ComfyUI의 bundled environment와 Python standard library 외에는 runtime Python package dependency가 필요하지 않습니다.

## 라이선스

MIT License

## 기여

오류 패턴과 문서 기여를 환영합니다. 코드 변경의 경우 pull request를 열기 전에 full validation gate를 실행하고, 생성된 로컬 상태, 로그, credential, 내부 planning file을 커밋하지 마세요.
