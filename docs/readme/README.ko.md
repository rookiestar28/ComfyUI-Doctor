# ComfyUI-Doctor

[English](../../README.md) | [繁中](README.zh-TW.md) | [简中](README.zh-CN.md) | [日本語](README.ja.md) | 한국어 | [Deutsch](README.de.md) | [Français](README.fr.md) | [Italiano](README.it.md) | [Español](README.es.md)

<div align="center">
<img src="../../assets/icon.png" alt="ComfyUI Doctor">
</div>

ComfyUI-Doctor는 ComfyUI용 실시간 진단 및 디버깅 도우미입니다. 런타임 오류를 캡처하고 관련 노드 컨텍스트를 찾아 로컬 수정 제안을 표시하며, 필요한 경우 LLM 채팅으로 더 깊은 분석을 진행할 수 있습니다.

## 최신 상태

- Doctor가 의존하는 ComfyUI, ComfyUI frontend, Desktop 호스트 표면에 대한 호환성 검사를 추가했습니다.
- 프론트엔드 설정은 현재 ComfyUI settings API를 우선 사용하고, legacy fallback은 호환 어댑터에 격리했습니다.
- 최근 execution/progress 이벤트를 사용해 실행 오류의 노드 lineage를 보강합니다.
- 공유 서버용 strict admin-token mode와 loopback convenience mode 경고를 추가했습니다.
- Server-side credential store의 암호화 메타데이터와 encrypt-then-MAC 설계를 문서화했습니다.
- 선택적 coverage baseline lane을 추가했으며 기본 full validation flow는 그대로 유지됩니다.

## 핵심 기능

- ComfyUI 시작 단계부터 console과 traceback을 모니터링합니다.
- 58개의 JSON 오류 패턴을 제공합니다: 22개 core pattern, 36개 community extension pattern.
- 호스트 이벤트에서 node ID, name, class, custom-node path를 추출합니다.
- Doctor sidebar에 Chat, Statistics, Settings 탭을 제공합니다.
- OpenAI-compatible, Anthropic, Gemini, xAI, OpenRouter, Ollama, LMStudio 등의 LLM workflow를 지원합니다.
- Cloud LLM 전송 전 path, credential-looking values, email, private IP 등을 가리는 privacy mode를 제공합니다.
- Admin-gated server-side credential store와 encryption-at-rest를 지원합니다.
- Diagnostics, statistics, plugin trust report, telemetry controls, community feedback preview/submit 기능을 포함합니다.
- 영어, 번체 중국어, 간체 중국어, 일본어, 한국어, 독일어, 프랑스어, 이탈리아어, 스페인어를 지원합니다.

## 설치

### ComfyUI-Manager

1. ComfyUI를 열고 **Manager**를 클릭합니다.
2. **Install Custom Nodes**를 선택합니다.
3. `ComfyUI-Doctor`를 검색합니다.
4. 설치 후 ComfyUI를 재시작합니다.

### 수동 설치

```bash
cd ComfyUI/custom_nodes/
git clone https://github.com/rookiestar28/ComfyUI-Doctor.git
```

재시작 후 왼쪽 sidebar에 **Doctor** 항목이 표시됩니다.

## 기본 사용법

- **자동 진단**: 오류를 캡처하고 알려진 패턴과 매칭하여 최신 진단을 표시합니다.
- **Doctor Sidebar**: Chat에서 최신 오류와 LLM 대화, Statistics에서 추세/진단/health 정보, Settings에서 language/provider/model/privacy/credential source를 관리합니다.
- **Smart Debug Node**: workflow 연결에 삽입해 type, shape, dtype, device, 통계값을 확인합니다. 출력 데이터는 변경하지 않습니다.

## 문서

- [User Guide](../USER_GUIDE.md)
- [Configuration and Security](../CONFIGURATION_SECURITY.md)
- [API Reference](../API_REFERENCE.md)
- [Validation Guide](../VALIDATION.md)
- [Plugin Guide](../PLUGIN_GUIDE.md)
- [Outbound Safety](../OUTBOUND_SAFETY.md)

## 검증

Windows:

```powershell
powershell -File scripts/run_full_tests_windows.ps1
```

Linux / WSL:

```bash
bash scripts/run_full_tests_linux.sh
```

## 라이선스

MIT License
