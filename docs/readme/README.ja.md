# ComfyUI-Doctor

[English](../../README.md) | [繁中](README.zh-TW.md) | [简中](README.zh-CN.md) | 日本語 | [한국어](README.ko.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | [Italiano](README.it.md) | [Español](README.es.md)

<div align="center">
<img src="../../assets/icon.png" alt="ComfyUI Doctor">
</div>

ComfyUI-Doctor は ComfyUI 向けのリアルタイム診断・デバッグ支援ツールです。実行時エラーを捕捉し、関連しそうなノード情報を抽出し、ローカルの修正候補を表示します。必要に応じて LLM チャットによる詳しい調査も利用できます。

## 最新状態

- Doctor が依存する ComfyUI、ComfyUI frontend、Desktop のホスト互換性チェックを追加しました。
- フロントエンド設定は現在の ComfyUI settings API を優先し、旧 API fallback は互換アダプターに集約しました。
- execution/progress イベントから実行エラーのノード lineage を補完できるようにしました。
- 共有サーバー向けに strict admin-token mode と loopback convenience mode の警告を追加しました。
- Server-side credential store の暗号化メタデータと encrypt-then-MAC 設計を文書化しました。
- 任意の coverage baseline lane を追加しました。既定の full validation flow は変わりません。

## 主な機能

- ComfyUI 起動時から console と traceback を監視。
- 58 個の JSON エラーパターン、内訳は 22 個の core pattern と 36 個の community extension pattern。
- ホストイベントから node ID、name、class、custom-node path を抽出。
- Doctor sidebar に Chat、Statistics、Settings タブを提供。
- OpenAI-compatible、Anthropic、Gemini、xAI、OpenRouter、Ollama、LMStudio などの LLM workflow に対応。
- Cloud LLM 送信前に path、credential-looking values、email、private IP などをマスクする privacy mode。
- Admin-gated server-side credential store と encryption-at-rest に対応。
- Diagnostics、statistics、plugin trust report、telemetry controls、community feedback preview/submit を搭載。
- 英語、繁体字中国語、簡体字中国語、日本語、韓国語、ドイツ語、フランス語、イタリア語、スペイン語に対応。

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

再起動後、左 sidebar に **Doctor** が表示されます。

## 基本的な使い方

- **自動診断**: エラーを捕捉し、既知パターンと照合して最新診断を表示します。
- **Doctor Sidebar**: Chat で最新エラーと LLM 会話、Statistics で傾向・診断・health 情報、Settings で language/provider/model/privacy/credential source を管理します。
- **Smart Debug Node**: workflow の接続に挿入し、type、shape、dtype、device、統計値を確認できます。出力データは変更しません。

## ドキュメント

- [User Guide](../USER_GUIDE.md)
- [Configuration and Security](../CONFIGURATION_SECURITY.md)
- [API Reference](../API_REFERENCE.md)
- [Validation Guide](../VALIDATION.md)
- [Plugin Guide](../PLUGIN_GUIDE.md)
- [Outbound Safety](../OUTBOUND_SAFETY.md)

## 検証

Windows:

```powershell
powershell -File scripts/run_full_tests_windows.ps1
```

Linux / WSL:

```bash
bash scripts/run_full_tests_linux.sh
```

## ライセンス

MIT License
