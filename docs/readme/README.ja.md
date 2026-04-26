# ComfyUI-Doctor

[繁中](README.zh-TW.md) | [简中](README.zh-CN.md) | 日本語 | [한국어](README.ko.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | [Italiano](README.it.md) | [Español](README.es.md) | [English](../../README.md) |

<div align="center">
<img src="../../assets/icon.png" alt="ComfyUI Doctor">
</div>

ComfyUI-Doctor は、ComfyUI 向けのリアルタイム診断およびデバッグ支援ツールです。実行時エラーを取得し、関連する可能性が高いノードコンテキストを特定し、実行可能なローカル提案を表示します。必要に応じて、LLM チャット workflow を使ったより深いトラブルシューティングも利用できます。

## 最新更新

最新更新は英語版 README を基準にしています。[Latest Updates](../../README.md#latest-updates---click-to-expand) を参照してください。

## 主な機能

- 起動時から ComfyUI の console/error 出力をリアルタイムに取得します。
- 22 個の core pattern と 36 個の community-extension pattern を含む、58 個の JSON ベースのエラーパターン提案を内蔵しています。
- ComfyUI が十分なイベントデータを提供している場合、直近の workflow 実行エラーからノードコンテキストを検証付きで抽出します。
- Doctor サイドバーには Chat、Statistics、Settings タブがあります。
- OpenAI-compatible services、Anthropic、Gemini、xAI、OpenRouter、Ollama、LMStudio による任意の LLM 分析に対応し、統一された provider request/response 処理を使います。
- 外部 LLM リクエスト向けに、パス、キー、メールアドレス、IP のサニタイズモードを含むプライバシー制御を提供します。
- 任意のサーバー側 credential store は、admin guarding と encryption-at-rest をサポートします。
- ローカル診断、統計、plugin trust report、telemetry 制御、community feedback のプレビュー/送信ツールを提供します。
- Doctor API の失敗応答は、一貫した JSON error envelope を使用します。
- UI と提案は、英語、繁体字中国語、簡体字中国語、日本語、韓国語、ドイツ語、フランス語、イタリア語、スペイン語に完全対応しています。

## スクリーンショット

<div align="center">
<img src="../../assets/chat-ui.png" alt="Doctor chat interface">
</div>

<div align="center">
<img src="../../assets/doctor-side-bar.png" alt="Doctor sidebar">
</div>

## インストール

### ComfyUI-Manager

1. ComfyUI を開き、**Manager** をクリックします。
2. **Install Custom Nodes** を選択します。
3. `ComfyUI-Doctor` を検索します。
4. インストール後、ComfyUI を再起動します。

### 手動インストール

```bash
cd ComfyUI/custom_nodes/
git clone https://github.com/rookiestar28/ComfyUI-Doctor.git
```

Clone 後に ComfyUI を再起動してください。Doctor は起動診断を出力し、`Doctor` サイドバー項目を登録します。

## 基本的な使い方

### 自動診断

インストール後、Doctor は ComfyUI の実行時出力を受動的に記録し、traceback を検出し、既知のエラーパターンと照合して、最新の診断をサイドバーと任意の右側レポートパネルに表示します。
任意の LLM 分析を使用する場合、Doctor はサニタイズ、ノードコンテキスト、実行ログ、workflow pruning、システム情報を扱う同じ構造化 pipeline から prompt context を構築します。

### Doctor サイドバー

ComfyUI の左サイドバーで **Doctor** を開きます。

- **Chat**：最新のエラーコンテキストを確認し、追加のデバッグ質問を行います。
- **Statistics**：最近のエラー傾向、診断、trust/health 情報、telemetry 制御、feedback tools を確認します。
- **Settings**：言語、LLM provider、base URL、model、privacy mode、自動オープン動作、任意のサーバー側 credential storage を選択します。

### Smart Debug Node

Canvas を右クリックして **Smart Debug Node** を追加し、workflow output を変更せずに通過データを確認するため workflow 内に配置します。

## 任意の LLM 設定

クラウド provider では、session-only UI field、環境変数、または任意の admin-gated server store から credential を提供する必要があります。Ollama や LMStudio などのローカル provider は、クラウド credential なしで実行できます。
Doctor は OpenAI-compatible APIs、Anthropic、Ollama の provider-specific request/response 形式を正規化し、chat、single-shot analysis、model listing、connectivity check が同じバックエンド動作を共有できるようにします。

推奨デフォルト：

- クラウド provider では **Privacy Mode: Basic** または **Strict** を使用します。
- 共有環境または production に近い環境では環境変数を使用します。
- 共有サーバーでは `DOCTOR_ADMIN_TOKEN` と `DOCTOR_REQUIRE_ADMIN_TOKEN=1` を設定します。
- local-only loopback convenience mode は、単一ユーザーのデスクトップ用途のみに限定してください。

## ドキュメント

- [User Guide](../USER_GUIDE.md)：UI walkthrough、診断、privacy mode、LLM setup、feedback flow。
- [Configuration and Security](../CONFIGURATION_SECURITY.md)：環境変数、admin guard behavior、credential storage、outbound safety、telemetry、CSP notes。
- [API Reference](../API_REFERENCE.md)：公開 Doctor endpoint と debugger endpoint。
- [Validation Guide](../VALIDATION.md)：ローカル full-gate コマンドと任意の compatibility/coverage lanes。
- [Plugin Guide](../PLUGIN_GUIDE.md)：community plugin trust model と plugin authoring notes。
- [Plugin Migration](../PLUGIN_MIGRATION.md)：plugin manifest と allowlist の migration tooling。
- [Outbound Safety](../OUTBOUND_SAFETY.md)：static checker と outbound request safety rules。

## 対応エラーパターン

Pattern は `patterns/` 以下の JSON ファイルとして保存されており、コード変更なしで更新できます。

| Pack | Count |
| --- | ---: |
| Core builtin patterns | 22 |
| Community extension patterns | 36 |
| **Total** | **58** |

Community pack は現在、ControlNet、LoRA、VAE、AnimateDiff、IPAdapter、FaceRestore、checkpoint、sampler、scheduler、CLIP の一般的な失敗モードを対象にしています。

## 検証

ローカル CI-parity 検証には、プロジェクトの full-test script を使用します。

```powershell
powershell -File scripts/run_full_tests_windows.ps1
```

```bash
bash scripts/run_full_tests_linux.sh
```

Full gate は secrets detection、pre-commit hooks、host-like startup validation、backend unit tests、frontend Playwright E2E tests を対象にします。明示的な段階別コマンドと任意 lanes は [Validation Guide](../VALIDATION.md) を参照してください。

## 要件

- ComfyUI custom-node 環境。
- Python 3.10 以上。
- Node.js 18 以上は frontend E2E validation のみに必要です。
- ComfyUI の bundled environment と Python standard library 以外に、runtime Python package dependency は不要です。

## ライセンス

MIT License

## コントリビューション

エラーパターンとドキュメントの貢献を歓迎します。コード変更の場合は、pull request を開く前に full validation gate を実行し、生成されたローカル状態、ログ、credential、内部 planning file をコミットしないでください。
