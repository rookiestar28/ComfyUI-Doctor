# ComfyUI-Doctor

[繁中](README.zh-TW.md) | [简中](README.zh-CN.md) | 日本語 | [한국어](README.ko.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | [Italiano](README.it.md) | [Español](README.es.md) | [English](../README.md) | [ロードマップ & 開発状況](../ROADMAP.md)

ComfyUIのための継続的かつリアルタイムなランタイム診断スイートです。**LLM（大規模言語モデル）による分析**、**対話型デバッグチャット**、**50以上の修復パターン** を備えています。起動時からすべてのターミナル出力を自動的にインターセプトし、完全なPythonトレースバックをキャプチャし、ノードレベルのコンテキスト抽出とともに優先順位付けされた修復提案を提供します。**JSONベースのパターン管理**（ホットリロード対応）と、9言語（en, zh_TW, zh_CN, ja, de, fr, it, es, ko）の**完全なi18nサポート**に対応しました。

## 最新のアップデート (2026年1月) - クリックして展開

<details>
<summary><strong>スマートトークン予算管理 (v1.5.0)</strong></summary>

**スマートコンテキスト管理 (コスト最適化):**

- **自動トリミング**：リモートLLM向けにコンテキストを自動削減 (Token 60-80% 削減)
- **段階的戦略**：ワークフロー剪定 → システム情報削除 → トレースバック切り捨て
- **ローカルオプトイン**：Ollama/LMStudio向けの穏やかなトリミング (12K/16K 制限)
- **可観測性の向上**：ステップバイステップのToken追跡 & A/B検証ハーネス

**ネットワークレジリエンス:**

- **指数バックオフ**：429/5xxエラーの自動リトライ (ジッター付き)
- **ストリーミング保護**：ストールしたSSEチャンクに対する30秒タイムアウト監視
- **レート & 同時実行制限**：トークンバケット (30回/分) + 同時実行セマフォ (最大 3)

**新しい設定:**

| Config Key | Default | Description |
|------------|---------|-------------|
| `r12_enabled_remote` | `true` | スマート予算を有効化 (リモート) |
| `retry_max_attempts` | `3` | 最大リトライ回数 |
| `stream_chunk_timeout` | `30` | ストリームタイムアウト (秒) |

</details>

---

<details>
<summary><strong>メジャー修正: パイプラインガバナンス & プラグインセキュリティ (v1.4.5)</strong></summary>

**セキュリティ強化:**

- **SSRF保護++**: 部分文字列チェックをHost/Port解析に置換; 外部へのリダイレクトをブロック (`allow_redirects=False`)
- **外部データサニタイズファネル**: 単一の境界 (`outbound.py`) で全ての外部ペイロードのサニタイズを保証; `privacy_mode=none` は検証済みのローカルLLMのみ許可

**プラグイン信頼システム:**

- **デフォルトセキュア**: プラグインはデフォルトで無効、明示的な許可リスト (Allowlist) + マニフェスト/SHA256 が必要
- **信頼分類**: `trusted` (信頼済み) | `unsigned` (未署名) | `untrusted` (信頼なし) | `blocked` (ブロック済み)
- **ファイルシステム強化**: realpathによる封じ込め、シンボリックリンク拒否、サイズ制限、厳格なファイル名ルール
- **オプションのHMAC署名**: 共有秘密鍵による整合性検証 (公開鍵署名ではない)

**パイプラインガバナンス:**

- **メタデータ契約**: スキーマバージョン管理 + 実行終了後検証 + 無効なキーの隔離 (Quarantine)
- **依存関係ポリシー**: `requires/provides` の強制; 依存不足 → ステージスキップ、ステータス `degraded` (低下)
- **Loggerバックプレッシャー**: 優先度認識付き `DroppingQueue` + ドロップメトリクス
- **起動前ハンドオフ**: SmartLoggerが引き継ぐ前にLoggerをクリーンにアンインストール

**観測可能性:**

- `/doctor/health` エンドポイント: キューメトリクス、ドロップ数、SSRFブロック数、パイプラインステータスを提供

**テスト結果**: 159個のPythonテスト合格 | 17個のPhase 2ゲートテスト

</details>

---

<details>
<summary><strong>機能強化: CIゲート & プラグインツール</strong></summary>

**Phase 2 リリースCIゲート:**

- GitHub Actionsワークフロー (`phase2-release-gate.yml`): 4つのpytestスイート + E2Eを強制
- ローカル検証スクリプト (`scripts/phase2_gate.py`): `--fast` および `--e2e` モードをサポート

**外部安全性静的チェッカー:**

- ASTベースの解析器 (`scripts/check_outbound_safety.py`) でバイパスパターンを検出
- 6つの検出ルール: `RAW_FIELD_IN_PAYLOAD`, `DANGEROUS_FALLBACK`, `POST_WITHOUT_SANITIZATION` など
- CIワークフロー + 8つのユニットテスト + ドキュメント (`docs/OUTBOUND_SAFETY.md`)

**プラグイン移行ツール:**

- `scripts/plugin_manifest.py`: SHA256ハッシュ付きマニフェスト生成
- `scripts/plugin_allowlist.py`: プラグインスキャンと設定提案
- `scripts/plugin_validator.py`: マニフェストと設定の検証
- `scripts/plugin_hmac_sign.py`: オプションのHMAC署名生成
- ドキュメント更新: `docs/PLUGIN_MIGRATION.md`, `docs/PLUGIN_GUIDE.md`

</details>

---

<details>
<summary><strong>機能強化: CSPドキュメント & テレメトリ</strong></summary>

**S1 - CSPコンプライアンスドキュメント:**

- 全てのアセットがローカルロードされることを検証 (`web/lib/`); CDN URLはフォールバックのみ
- READMEに "CSP Compatibility" セクションを追加
- コード監査完了 (手動検証待ち)

**S3 - ローカルテレメトリインフラ:**

- バックエンド: `telemetry.py` (TelemetryStore, RateLimiter, PII検出)
- 6つのAPIエンドポイント: `/doctor/telemetry/{status,buffer,track,clear,export,toggle}`
- フロントエンド: テレメトリ管理用の設定UIコントロール
- セキュリティ: オリジンチェック (403 クロスオリジン), 1KBペイロード制限, フィールドホワイトリスト
- **デフォルトOFF**: 明示的に有効化しない限り記録/通信なし
- 81個のi18n文字列 (9 keys × 9 languages)

**テスト結果**: 27個のテレメトリユニットテスト | 8個のE2Eテスト

</details>

---

<details>
<summary><strong>機能強化: E2Eランナー強化 & 信頼/健全性UI</strong></summary>

**E2Eランナー強化 (WSL `/mnt/c` サポート):**

- WSL上でのPlaywright変換キャッシュ権限問題を修正
- リポジトリ配下に書き込み可能な一時ディレクトリ (`.tmp/playwright`) を追加
- `PW_PYTHON` オーバーライドによるクロスプラットフォーム互換性

**信頼 & 健全性UIパネル:**

- 設定タブに "Trust & Health" パネルを追加
- 表示: pipeline_status, ssrf_blocked, dropped_logs
- プラグイン信頼リスト (バッジと理由付き)
- `GET /doctor/plugins` スキャン専用エンドポイント (コードインポートなし)

**テスト結果**: 61/61個のE2Eテスト合格 | 159/159個のPythonテスト合格

</details>

---

<details>
<summary><strong>以前のアップデート (v1.4.0, Jan 2026)</strong></summary>

- A7 Preact移行完了 (Phase 5A–5C: Chat/Stats islands, registry, shared rendering, robust fallbacks)。
- 統合強化: Playwright E2Eカバレッジを強化。
- UI修正: サイドバーツールチップのタイミング修正。

</details>

---

<details>
<summary><strong>統計ダッシュボード</strong></summary>

**ComfyUIの安定性を一目で把握！**

ComfyUI-Doctorに**統計ダッシュボード**が追加されました。エラートレンド、一般的な問題、解決の進捗状況に関する洞察を提供します。

**特徴**:

- 📊 **エラートレンド**: 24時間/7日間/30日間のエラー統計を追跡
- 🔥 **トップ5パターン**: 最も頻繁に発生しているエラーを確認
- 📈 **カテゴリ内訳**: エラーをカテゴリ別（メモリ、ワークフロー、モデルロードなど）に可視化
- ✅ **解決追跡**: 解決済み vs 未解決のエラーを監視
- 🌍 **完全なi18nサポート**: 全9言語に対応

![統計ダッシュボード](assets/statistics_panel.png)

**使用方法**:

1. Doctorサイドバーパネル（左側の 🏥 アイコン）を開く
2. 「📊 Error Statistics（エラー統計）」セクションを展開
3. リアルタイムのエラー分析とトレンドを表示
4. 進捗を追跡するためにエラーを解決済み/無視としてマーク

**バックエンドAPI**:

- `GET /doctor/statistics?time_range_days=30` - 統計を取得
- `POST /doctor/mark_resolved` - 解決ステータスを更新

**テストカバレッジ**: 17/17 バックエンドテスト ✅ | 14/18 E2Eテスト（合格率78%）

**実装詳細**: `.planning/260104-F4_STATISTICS_RECORD.md` を参照

</details>

---

<details>
<summary><strong>パターン検証CI</strong></summary>

**自動品質チェックがパターンの完全性を保護します！**

ComfyUI-Doctorは、すべてのエラーパターンに対して**継続的インテグレーション（CI）テスト**を導入し、欠陥のないコントリビューションを保証します。

**T8が検証するもの**:

- ✅ **JSONフォーマット**: 全8つのパターンファイルが正しくコンパイルされるか
- ✅ **Regex構文**: 全57パターンが有効な正規表現を持っているか
- ✅ **i18n完全性**: 100%の翻訳カバレッジ（57パターン × 9言語 = 513チェック）
- ✅ **スキーマ準拠**: 必須フィールド（`id`, `regex`, `error_key`, `priority`, `category`）
- ✅ **メタデータ品質**: 有効な優先度範囲（50-95）、一意のID、正しいカテゴリ

**GitHub Actions統合**:

- `patterns/`、`i18n.py`、またはテストに影響を与えるプッシュ/PRごとにトリガー
- 約3秒で実行、コスト$0（GitHub Actions無料枠）
- 検証に失敗した場合、マージをブロック

**コントリビューター向け**:

```bash
# コミット前のローカル検証
python run_pattern_tests.py

# 出力:
✅ All 57 patterns have required fields
✅ All 57 regex patterns compile successfully
✅ en: All 57 patterns have translations
✅ zh_TW: All 57 patterns have translations
... (全9言語)
```

**テスト結果**: すべてのチェックで合格率100%

**実装詳細**: `.planning/260103-T8_IMPLEMENTATION_RECORD.md` を参照

</details>

---

<details>
<summary><strong>パターンシステムの刷新 (STAGE 1-3 完了)</strong></summary>

ComfyUI-Doctorは、**57以上のエラーパターン**と**JSONベースのパターン管理**を備えた大規模なアーキテクチャアップグレードを実施しました！

**STAGE 1: Loggerアーキテクチャの修正**

- SafeStreamWrapperとキューベースのバックグラウンド処理を実装
- デッドロックのリスクと競合状態を排除
- ComfyUIのLogInterceptorとのログ傍受の競合を修正

**STAGE 2: JSONパターン管理 (F2)**

- ホットリロード機能を備えた新しいPatternLoader（再起動不要！）
- パターンは `patterns/` ディレクトリ配下のJSONファイルで定義
- `patterns/builtin/core.json` に22個の組み込みパターン
- 拡張とメンテナンスが容易

**STAGE 3: コミュニティパターンの拡張 (F12)**

- 人気の拡張機能をカバーする**35個の新しいコミュニティパターン**:
  - **ControlNet** (8パターン): モデルロード、前処理、画像サイズ
  - **LoRA** (6パターン): ロードエラー、互換性、ウェイト問題
  - **VAE** (5パターン): エンコード/デコード失敗、精度、タイリング
  - **AnimateDiff** (4パターン): モデルロード、フレーム数、コンテキスト長
  - **IPAdapter** (4パターン): モデルロード、画像エンコード、互換性
  - **FaceRestore** (3パターン): CodeFormer/GFPGANモデル、検出
  - **その他** (5パターン): チェックポイント、サンプラー、スケジューラー、CLIP
- 英語、繁体字中国語、簡体字中国語の完全なi18nサポート
- 合計: **57のエラーパターン**（22組み込み + 35コミュニティ）

**メリット**:

- ✅ より包括的なエラーカバレッジ
- ✅ ComfyUIを再起動せずにパターンをホットリロード
- ✅ コミュニティがJSONファイルを介してパターンを寄稿可能
- ✅ よりクリーンで保守性の高いコードベース

</details>

---

<details>
<summary><strong>以前のアップデート (2025年12月)</strong></summary>

### F9: 多言語サポートの拡大

言語サポートを4言語から9言語に拡大しました！ComfyUI-Doctorは以下の言語でエラー提案を提供します：

- **English** 英語 (en)
- **繁體中文** 繁体字中国語 (zh_TW)
- **简体中文** 簡体字中国語 (zh_CN)
- **日本語** (ja)
- **🆕 Deutsch** ドイツ語 (de)
- **🆕 Français** フランス語 (fr)
- **🆕 Italiano** イタリア語 (it)
- **🆕 Español** スペイン語 (es)
- **🆕 한국어** 韓国語 (ko)

57種類すべてのエラーパターンが全言語で完全に翻訳されており、世界中で一貫した診断品質を保証します。

### F8: サイドバー設定の統合

設定が簡素化されました！Doctorをサイドバーから直接設定できます：

- サイドバーヘッダーの ⚙️ アイコンをクリックして全設定にアクセス
- 言語選択（9言語）
- AIプロバイダーのクイック切り替え（OpenAI, DeepSeek, Groq, Gemini, Ollamaなど）
- プロバイダー変更時のベースURL自動入力
- APIキー管理（パスワード保護入力）
- モデル名設定
- 設定はlocalStorageでセッションを超えて保持されます
- 保存時の視覚的フィードバック（✅ 保存しました！ / ❌ エラー）

ComfyUI設定パネルには有効/無効の切り替えスイッチのみが表示され、他のすべての設定はサイドバーに移動し、よりクリーンで統合された体験を提供します。

</details>

---

## 機能

- **自動エラー監視**: すべてのターミナル出力をキャプチャし、Pythonトレースバックをリアルタイムで検出
- **インテリジェントなエラー分析**: 57以上のエラーパターン（22組み込み + 35コミュニティ）と実用的な提案
- **ノードコンテキスト抽出**: エラーの原因となったノードを特定（ノードID、名前、クラス）
- **システム環境コンテキスト**: AI分析時にPythonバージョン、インストール済みパッケージ（pip list）、OS情報を自動的に含める
- **多言語サポート**: 9言語対応（英語、繁体字中国語、簡体字中国語、日本語、ドイツ語、フランス語、イタリア語、スペイン語、韓国語）
- **JSONベースのパターン管理**: ComfyUIを再起動せずにエラーパターンをホットリロード
- **コミュニティパターンサポート**: ControlNet, LoRA, VAE, AnimateDiff, IPAdapter, FaceRestoreなどをカバー
- **デバッグインスペクターノード**: ワークフローを流れるデータの詳細な検査
- **エラー履歴**: API経由で最近のエラーのバッファを保持
- **RESTful API**: フロントエンド統合のための7つのエンドポイント
- **AI搭載分析**: 8つ以上のプロバイダー（OpenAI, DeepSeek, Groq, Gemini, Ollama, LMStudioなど）をサポートするワンクリックLLMエラー分析
- **対話型チャットインターフェース**: ComfyUIサイドバーに統合されたマルチターンAIデバッグアシスタント
- **インタラクティブなサイドバーUI**: ノードの位置特定と即時診断が可能な視覚的エラーパネル
- **柔軟な設定**: 動作をカスタマイズするための包括的な設定パネル

### 🆕 AIチャットインターフェース

新しい対話型チャットインターフェースは、ComfyUIの左サイドバー内で直接会話型のデバッグ体験を提供します。エラーが発生した場合、「Analyze with AI」をクリックするだけで、お好みのLLMとのマルチターン会話を開始できます。

<div align="center">
<img src="assets/chat-ui.png" alt="AI Chat Interface">
</div>

**主な機能:**

- **コンテキスト認識**: エラー詳細、ノード情報、ワークフローコンテキストを自動的に含めます
- **環境認識**: 正確なデバッグのためにPythonバージョン、インストール済みパッケージ、OS情報を含めます
- **ストリーミング応答**: 適切なフォーマットによるリアルタイムLLM応答
- **マルチターン会話**: 問題を深く掘り下げるための追加質問が可能
- **常にアクセス可能**: 入力エリアはスティッキーポジショニングで下部に常に表示されます
- **8つ以上のLLMプロバイダーをサポート**: OpenAI, DeepSeek, Groq, Gemini, Ollama, LMStudioなど
- **スマートキャッシング**: パッケージリストはパフォーマンスへの影響を避けるため24時間キャッシュされます

**使用方法:**

1. エラーが発生したら、Doctorサイドバー（左パネル）を開く
2. エラーコンテキストエリアの「✨ Analyze with AI」ボタンをクリック
3. AIが自動的にエラーを分析し、提案を提供
4. 入力ボックスに追加の質問を入力して会話を継続
5. Enterキーを押すか「Send」をクリックしてメッセージを送信

> **💡 無料APIのヒント**: [Google AI Studio](https://aistudio.google.com/app/apikey) (Gemini) は、クレジットカード不要で寛大な無料枠を提供しています。コストをかけずにAI搭載のデバッグを始めるのに最適です！

---

## インストール

### オプション 1: ComfyUI-Managerの使用（推奨）

1. ComfyUIを開き、メニューの **Manager** ボタンをクリック
2. **Install Custom Nodes** を選択
3. `ComfyUI-Doctor` を検索
4. **Install** をクリックしてComfyUIを再起動

### オプション 2: 手動インストール (Git Clone)

1. ComfyUIのカスタムノードディレクトリに移動:

   ```bash
   cd ComfyUI/custom_nodes/
   ```

2. リポジトリをクローン:

   ```bash
   git clone https://github.com/rookiestar28/ComfyUI-Doctor.git
   ```

3. ComfyUIを再起動

4. コンソールで初期化メッセージを確認:

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

## 使用方法

### パッシブモード（自動）

インストール後、ComfyUI-Doctorは自動的に以下を行います:

- すべてのコンソール出力を `logs/` ディレクトリに記録
- エラーを検出し、提案を提供
- システム環境情報を記録

**エラー出力例**:

```
Traceback (most recent call last):
  ...
RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB

----------------------------------------
ERROR LOCATION: Node ID: #42 | Name: KSampler
SUGGESTION: OOM (Out Of Memory): GPU VRAMが一杯です。試してください:
   1. バッチサイズを減らす
   2. '--lowvram' フラグを使用する
   3. 他のGPUアプリを閉じる
----------------------------------------
```

### アクティブモード（デバッグノード）

1. キャンバス上で右クリック → `Add Node` → `Smart Debug Node`
2. 任意の接続にノードをインラインで接続（ワイルドカード入力 `*` をサポート）
3. ワークフローを実行

**出力例**:

```text
[DEBUG] Data Inspection:
  Type: Tensor
  Shape: torch.Size([1, 4, 64, 64])
  Dtype: torch.float16
  Device: cuda:0
  Stats (All): Min=-3.2156, Max=4.8912, Mean=0.0023
```

このノードはワークフローの実行に影響を与えることなくデータを通過させます。

---

## フロントエンドUI

ComfyUI-Doctorは、リアルタイムのエラー監視と診断のためのインタラクティブなサイドバーインターフェースを提供します。

### Doctorパネルへのアクセス

ComfyUIメニュー（左サイドバー）の **🏥 Doctor** ボタンをクリックしてDoctorパネルを開きます。パネルは画面の右側からスライドインします。

### インターフェース機能

<div align="center">
<img src="assets/doctor-side-bar.png" alt="Error Report">
</div>

Doctorインターフェースは2つのパネルで構成されています:

#### 左サイドバーパネル (Doctorサイドバー)

ComfyUIの左メニューにある **🏥 Doctor** アイコンをクリックしてアクセス:

- **設定パネル** (⚙️ アイコン): 言語、AIプロバイダー、APIキー、モデル選択の設定
- **エラーコンテキストカード**: エラー発生時に表示:
  - **💡 提案**: 簡潔で実用的なアドバイス（例：「入力接続を確認し、ノードの要件を満たしていることを確認してください。」）
  - **タイムスタンプ**: エラー発生時刻
  - **ノードコンテキスト**: ノードIDと名前（該当する場合）
  - **✨ Analyze with AI**: 詳細なデバッグのための対話型チャットを起動
- **AIチャットインターフェース**: 詳細なエラー分析のためのLLMとのマルチターン会話
- **スティッキー入力エリア**: 下部に常にアクセス可能で、フォローアップ質問が簡単

#### 右エラーパネル (最新の診断)

右上のリアルタイムエラー通知:

![Doctor Error Report](./assets/error-report.png)

- **ステータスインジケーター**: システムの健全性を示す色付きドット
  - 🟢 **緑**: システム正常、エラーなし
  - 🔴 **赤 (点滅)**: アクティブなエラーを検出
- **最新診断カード**: 最新のエラーを表示:
  - **エラーサマリー**: 短いエラー説明（赤色テーマ、長い場合は折りたたみ可能）
  - **💡 提案**: 簡潔で実用的なアドバイス（緑色テーマ）
  - **タイムスタンプ**: エラー発生時刻
  - **ノードコンテキスト**: ノードID、名前、クラス
  - **🔍 キャンバス上のノードを特定**: 問題のあるノードを自動的に中央に配置しハイライト

**主要な設計原則**:

- ✅ **簡潔な提案**: 冗長なエラー説明ではなく、実用的なアドバイスのみを表示（例：「入力接続を確認してください...」）
- ✅ **視覚的な分離**: エラーメッセージ（赤）と提案（緑）を明確に区別
- ✅ **スマートな省略**: 長いエラーは最初の3行と最後の3行を表示し、完全な詳細は展開可能
- ✅ **リアルタイム更新**: WebSocketイベントを通じて新しいエラーが発生すると両パネルが自動的に更新

---

## AI搭載エラー分析

ComfyUI-Doctorは一般的なLLMサービスと統合し、インテリジェントでコンテキストを認識したデバッグ提案を提供します。

### サポートされているAIプロバイダー

#### クラウドサービス

- **OpenAI** (GPT-4, GPT-4oなど)
- **DeepSeek** (DeepSeek-V2, DeepSeek-Coder)
- **Groq Cloud** (Llama 3, Mixtral - 超高速LPU推論)
- **Google Gemini** (Gemini Pro, Gemini Flash)
- **xAI Grok** (Grok-2, Grok-beta)
- **OpenRouter** (Claude, GPT-4, 100以上のモデルへのアクセス)

#### ローカルサービス（APIキー不要）

- **Ollama** (`http://127.0.0.1:11434`) - Llama, Mistral, CodeLlamaをローカルで実行
- **LMStudio** (`http://localhost:1234/v1`) - GUI付きのローカルモデル推論

> **💡 クロスプラットフォーム互換性**: デフォルトURLは環境変数で上書き可能です:
>
> - `OLLAMA_BASE_URL` - カスタムOllamaエンドポイント（デフォルト: `http://127.0.0.1:11434`）
> - `LMSTUDIO_BASE_URL` - カスタムLMStudioエンドポイント（デフォルト: `http://localhost:1234/v1`）
>
> これにより、WindowsとWSL2のOllamaインスタンス間の競合や、Docker/カスタムセットアップでの実行時の競合を防ぎます。

### 構成

![設定パネル](./assets/settings.png)

**Doctorサイドバー** → **Settings** パネルでAI分析を設定します:

1. **AI Provider**: ドロップダウンメニューから選択します。ベースURLは自動入力されます。
2. **AI Base URL**: APIエンドポイント（自動入力されますが、カスタマイズ可能）
3. **AI API Key**: あなたのAPIキー（Ollama/LMStudioのようなローカルLLMの場合は空欄で可）
4. **AI Model Name**:
   - ドロップダウンリストからモデルを選択（プロバイダーのAPIから自動的に入力）
   - 🔄 更新ボタンをクリックして利用可能なモデルをリロード
   - または「Enter model name manually」をチェックしてカスタムモデル名を入力
5. **Privacy Mode**: クラウドAIサービス向けのPIIサニタイズレベルを選択（詳細は下記の[プライバシーモード (PIIサニタイゼーション)](#プライバシーモード-piiサニタイゼーション)セクションを参照）

### AI分析の使用

1. エラーが発生すると自動的にDoctorパネルが開きます。
2. 組み込みの提案を確認するか、エラーカードの ✨ Analyze with AI ボタンをクリックします。
3. LLMがエラーを分析するのを待ちます（通常3〜10秒）。
4. AIが生成したデバッグ提案を確認します。

**セキュリティ上の注意**: APIキーは分析リクエストのためにフロントエンドからバックエンドに安全に送信されるだけです。ログに記録されたり、永続的に保存されることはありません。

### プライバシーモード (PIIサニタイゼーション)

ComfyUI-Doctorには、エラーメッセージをクラウドAIサービスに送信する際にプライバシーを保護するための自動**PII（個人識別情報）サニタイゼーション**が含まれています。

**3つのプライバシーレベル**:

| レベル | 説明 | 削除されるもの | 推奨 |
| ----- | ----------- | --------------- | --------------- |
| **None** | サニタイズなし | なし | ローカルLLM (Ollama, LMStudio) |
| **Basic** (デフォルト) | 標準的な保護 | ユーザーパス、APIキー、Email、IPアドレス | クラウドLLMを使用するほとんどのユーザー |
| **Strict** | 最大限のプライバシー | Basicの全項目 + IPv6, SSHフィンガープリント | エンタープライズ/コンプライアンス要件 |

**サニタイズされるもの** (Basicレベル):

- ✅ Windowsユーザーパス: `C:\Users\john\file.py` → `<USER_PATH>\file.py`
- ✅ Linux/macOSホーム: `/home/alice/test.py` → `<USER_HOME>/test.py`
- ✅ APIキー: `sk-abc123...` → `<API_KEY>`
- ✅ メールアドレス: `user@example.com` → `<EMAIL>`
- ✅ プライベートIP: `192.168.1.1` → `<PRIVATE_IP>`
- ✅ URL認証情報: `https://user:pass@host` → `https://<USER>@host`

**削除されないもの**:

- ❌ エラーメッセージ（デバッグに必要）
- ❌ モデル名、ノード名
- ❌ ワークフロー構造
- ❌ パブリックファイルパス (`/usr/bin/python`)

**プライバシーモードの設定**: Doctorサイドバーを開く → Settings → 🔒 Privacy Mode ドロップダウン。変更はすべてのAI分析リクエストに即座に適用されます。

**GDPR準拠**: この機能はGDPR第25条（データ保護の設計）をサポートしており、エンタープライズ展開に推奨されます。

### 統計ダッシュボード

![統計パネル](assets/statistics_panel.png)

**統計ダッシュボード**は、ComfyUIのエラーパターンと安定性の傾向に関するリアルタイムの洞察を提供します。

**機能**:

- **📊 エラートレンド**: 過去24時間/7日間/30日間の合計エラー数とカウント
- **🔥 トップエラーパターン**: 発生頻度の高い上位5つのエラータイプ
- **📈 カテゴリ内訳**: エラーカテゴリ（メモリ、ワークフロー、モデルロード、フレームワーク、一般）による視覚的な内訳
- **✅ 解決追跡**: 解決済み、未解決、無視されたエラーを追跡
- **🧭 ステータス操作**: 統計タブから最新エラーを解決済み / 未解決 / 無視 に設定

**使用方法**:

1. Doctorサイドバーを開く（左側の 🏥 アイコンをクリック）
2. **📊 Error Statistics** の折りたたみセクションを見つける
3. クリックして展開し、エラー分析を表示
4. **Mark as** ボタンで最新エラーの状態を設定（解決済み / 未解決 / 無視）

**解決ステータス操作**:

- 最新のエラーにタイムスタンプがある場合のみボタンが有効
- ステータス更新は履歴に保存され、解決率が自動で更新

**データの理解**:

- **Total (30d)**: 過去30日間の累積エラー
- **Last 24h**: 過去24時間のエラー（最近の問題の特定に役立ちます）
- **Resolution Rate (解決率)**: 既知の問題の解決に向けた進捗を示します
  - 🟢 **Resolved**: 修正した問題
  - 🟠 **Unresolved**: 注意が必要なアクティブな問題
  - ⚪ **Ignored**: 無視することを選択した重要でない問題
- **Top Patterns**: 優先的に注意が必要なエラータイプを特定
- **Categories**: 問題がメモリ関連、ワークフローの問題、モデルロードの失敗などであるかを理解するのに役立ちます

**パネル状態の保持**: パネルの開閉状態はブラウザのlocalStorageに保存されるため、設定はセッションを超えて保持されます。

### プロバイダー設定例

| プロバイダー | Base URL | モデル例 |
|------------------|------------------------------------------------------------|------------------------------|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| Groq | `https://api.groq.com/openai/v1` | `llama-3.1-70b-versatile` |
| Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-1.5-flash` |
| Ollama (Local) | `http://localhost:11434/v1` | `llama3.1:8b` |
| LMStudio (Local) | `http://localhost:1234/v1` | LMStudioでロードされたモデル |

---

## 設定

ComfyUIの設定パネル（歯車アイコン）からComfyUI-Doctorの動作をカスタマイズできます。

### 1. Show error notifications (エラー通知を表示)

**機能**: 作業画面右上にフローティングエラー通知カード（トースト）を表示するかどうかを切り替えます。
**用途**: 視覚的な中断なしにサイドバーで手動でエラーを確認したい場合は無効にします。

### 2. Auto-open panel on error (エラー時にパネルを自動で開く)

**機能**: 新しいエラーが検出されると自動的にDoctorサイドバーを展開します。
**用途**: **推奨**。手動でクリックすることなく、診断結果に即座にアクセスできます。

### 3. Error Check Interval (ms)

**機能**: フロントエンドとバックエンドのエラーチェックの頻度（ミリ秒単位）。デフォルト: `2000`。
**用途**: 低い値（例：500）はより速いフィードバックを提供しますが、負荷が増加します。高い値（例：5000）はリソースを節約します。

### 4. Suggestion Language (提案言語)

**機能**: 診断レポートとDoctorの提案に使用する言語。
**用途**: 現在、英語、繁体字中国語、簡体字中国語、日本語をサポートしています（順次追加予定）。変更は新しいエラーに適用されます。

### 5. Enable Doctor (requires restart)

**機能**: ログ傍受システムのマスター・スイッチ。
**用途**: オフにするとDoctorの主要機能が完全に無効になります（ComfyUIの再起動が必要）。

### 6. AI Provider

**機能**: ドロップダウンメニューからお好みのLLMサービスプロバイダーを選択します。
**オプション**: OpenAI, DeepSeek, Groq Cloud, Google Gemini, xAI Grok, OpenRouter, Ollama (Local), LMStudio (Local), Custom.
**用途**: プロバイダーを選択すると適切なベースURLが自動的に入力されます。ローカルプロバイダー（Ollama/LMStudio）の場合、利用可能なモデルを表示するアラートが表示されます。

### 7. AI Base URL

**機能**: LLMサービスのAPIエンドポイント。
**用途**: プロバイダーを選択すると自動入力されますが、セルフホストやカスタムエンドポイント用にカスタマイズ可能です。

### 8. AI API Key

**機能**: クラウドLLMサービスとの認証用APIキー。
**用途**: クラウドプロバイダー（OpenAI, DeepSeekなど）には必須です。ローカルLLM（Ollama, LMStudio）の場合は空のままで構いません。
**セキュリティ**: キーは分析リクエスト中にのみ送信され、ログに記録されたり永続化されたりすることはありません。

### 9. AI Model Name

**機能**: エラー分析に使用するモデルを指定します。
**用途**:

- **ドロップダウンモード**（デフォルト）: 自動入力されたドロップダウンリストからモデルを選択します。利用可能なモデルをリロードするには 🔄 更新ボタンをクリックします。
- **手動入力モード**: 「Enter model name manually」をチェックしてカスタムモデル名を入力します（例：`gpt-4o`, `deepseek-chat`, `llama3.1:8b`）。
- プロバイダーを変更したり更新をクリックしたりすると、選択したプロバイダーのAPIからモデルが自動的に取得されます。
- ローカルLLM（Ollama/LMStudio）の場合、ドロップダウンにはローカルで利用可能なすべてのモデルが表示されます。

### 10. 信頼性と健全性 (Trust & Health)

**機能**: システムの健全性ステータスとプラグイン信頼レポートを表示します。
**使用法**: 🔄 更新ボタンをクリックして `/doctor/health` エンドポイントのデータを取得します。

**表示内容**:

- **Pipeline Status**: 現在の分析パイプラインの状態
- **SSRF Blocked**: ブロックされた疑わしいアウトバウンドリクエストの数
- **Dropped Logs**: バックプレッシャーによりドロップされたログメッセージの数
- **Plugin Trust List**: 検出されたすべてのプラグインと信頼ステータスバッジを表示:
  - 🟢 **Trusted**: 有効なマニフェストを持つ許可リスト登録済みプラグイン
  - 🟡 **Unsigned**: マニフェストのないプラグイン (注意して使用してください)
  - 🔴 **Blocked**: ブロックリスト登録済みプラグイン

### 11. 匿名テレメトリ (建設中 🚧)

**機能**: Doctorの改善に役立つ匿名使用状況データの収集へのオプトイン。
**ステータス**: **建設中** — 現在はローカル保存のみで、ネットワークアップロードはありません。

**コントロール**:

- **Toggle**: テレメトリ記録の有効化/無効化 (デフォルト: OFF)
- **View Buffer**: アップロード前にバッファされたイベントを検査
- **Clear All**: バッファされたすべてのテレメトリデータを削除
- **Export**: レビュー用にバッファされたデータをJSONとしてダウンロード

**プライバシー保証**:

- ✅ **オプトインのみ**: 明示的に有効にするまでデータは記録されません
- ✅ **ローカルのみ**: 現在はデータをローカルにのみ保存します (`Upload destination: None`)
- ✅ **PII 検出**: 機密情報を自動的にフィルタリングします
- ✅ **完全な透明性**: 将来のアップロードの前にすべてのデータを表示/エクスポート

---

## APIエンドポイント

### GET `/debugger/last_analysis`

最新のエラー分析を取得:

```bash
curl http://localhost:8188/debugger/last_analysis
```

**レスポンス例**:

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

エラー履歴を取得（最新20件）:

```bash
curl http://localhost:8188/debugger/history
```

### POST `/debugger/set_language`

提案言語を変更します（言語切り替えセクションを参照）。

### POST `/doctor/analyze`

設定されたLLMサービスを使用してエラーを分析します。

**ペイロード**:

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

**レスポンス**:

```json
{
  "analysis": "AI-generated debugging suggestions..."
}
```

### POST `/doctor/verify_key`

LLMプロバイダーへの接続をテストしてAPIキーの有効性を検証します。

**ペイロード**:

```json
{
  "base_url": "https://api.openai.com/v1",
  "api_key": "your-api-key"
}
```

**レスポンス**:

```json
{
  "success": true,
  "message": "API key is valid",
  "is_local": false
}
```

### POST `/doctor/list_models`

設定されたLLMプロバイダーから利用可能なモデルをリストします。

**ペイロード**:

```json
{
  "base_url": "http://localhost:11434/v1",
  "api_key": ""
}
```

**レスポンス**:

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

## ログファイル

すべてのログは以下に保存されます:

```text
ComfyUI/custom_nodes/ComfyUI-Doctor/logs/
```

ファイル名形式: `comfyui_debug_YYYY-MM-DD_HH-MM-SS.log`

システムは自動的に最新の10個のログファイルを保持します（`config.json` で設定可能）。

---

## 設定

`config.json` を作成して動作をカスタマイズ:

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

**パラメータ**:

- `max_log_files`: 保持するログファイルの最大数
- `buffer_limit`: トレースバックバッファサイズ（行数）
- `traceback_timeout_seconds`: 不完全なトレースバックのタイムアウト
- `history_size`: 履歴に保持するエラー数
- `default_language`: デフォルトの提案言語
- `enable_api`: APIエンドポイントを有効にする
- `privacy_mode`: PIIサニタイズレベル - `"none"`, `"basic"` (デフォルト), または `"strict"`

---

## サポートされているエラーパターン

ComfyUI-Doctorは以下を検出して提案を提供できます:

- 型の不一致（例：fp16 vs float32）
- 次元の不一致
- CUDA/MPSメモリ不足 (OOM)
- 行列乗算エラー
- デバイス/タイプの競合
- Pythonモジュールの欠落
- アサーションの失敗
- キー/属性エラー
- 形状の不一致
- ファイルが見つからないエラー
- SafeTensorsロードエラー
- CUDNN実行エラー
- InsightFaceライブラリの欠落
- モデル/VAEの不一致
- 無効なプロンプトJSON

その他多数...

---

## ヒント

1. **ComfyUI Managerと併用**: 欠落しているカスタムノードを自動的にインストール
2. **ログファイルを確認**: 問題報告用に完全なトレースバックが記録されています
3. **組み込みサイドバーを使用**: 左メニューの 🏥 Doctor アイコンをクリックしてリアルタイム診断
4. **ノードデバッグ**: Debugノードを接続して疑わしいデータフローを検査

---

## ライセンス

MIT License

---

## 貢献

貢献は大歓迎です！プルリクエスト（PR）を自由に送信してください。

**問題を報告**: バグを見つけた場合や提案がありますか？GitHubでissueを開いてください。
**PRを送信**: バグ修正や一般的な改善でコードベースを改善するのを手伝ってください。
**機能リクエスト**: 新機能のアイデアはありますか？私たちに知らせてください。
