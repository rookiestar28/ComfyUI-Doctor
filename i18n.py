"""
Internationalization (i18n) module for ComfyUI Runtime Diagnostics.
Provides multi-language support for error suggestions.
"""

from typing import Dict, Optional

# Current language setting
_current_language = "zh_TW"

# Supported languages
SUPPORTED_LANGUAGES = ["en", "zh_TW", "zh_CN", "ja"]

# Error pattern keys (used as identifiers)
ERROR_KEYS = {
    "TYPE_MISMATCH": "type_mismatch",
    "DIMENSION_MISMATCH": "dimension_mismatch",
    "OOM": "oom",
    "MATRIX_MULT": "matrix_mult",
    "DEVICE_TYPE": "device_type",
    "MISSING_MODULE": "missing_module",
    "ASSERTION": "assertion",
    "KEY_ERROR": "key_error",
    "ATTRIBUTE_ERROR": "attribute_error",
    "SHAPE_MISMATCH": "shape_mismatch",
    "FILE_NOT_FOUND": "file_not_found",
    "TORCH_OOM": "torch_oom",
    "AUTOGRAD": "autograd",
    "SAFETENSORS_ERROR": "safetensors_error",
    "CUDNN_ERROR": "cudnn_error",
    "MISSING_INSIGHTFACE": "missing_insightface",
    "MODEL_VAE_MISMATCH": "model_vae_mismatch",
    "MPS_OOM": "mps_oom",
    "INVALID_PROMPT": "invalid_prompt",
    "VALIDATION_ERROR": "validation_error",
    "TENSOR_NAN_INF": "tensor_nan_inf",
    "META_TENSOR": "meta_tensor",
}

# Multi-language suggestion templates
SUGGESTIONS: Dict[str, Dict[str, str]] = {
    "en": {
        "type_mismatch": "Type Mismatch: The model expects {0} (e.g., fp16) but received {1} (e.g., float32). Try using a 'Cast Tensor' node or checking your VAE/Model loading precision.",
        "dimension_mismatch": "Dimension Mismatch: Tensor {0} (size {1}) doesn't match Tensor {2} (size {3}) at dim {4}. Check your latent dimensions or image sizes. Are you mixing different resolutions?",
        "oom": "OOM (Out Of Memory): Your GPU VRAM is full. Try: 1. Reducing Batch Size. 2. Using '--lowvram' flag. 3. Closing other GPU apps.",
        "matrix_mult": "Matrix Multiplication Error: This usually happens when model architecture doesn't match the weights (e.g., SD1.5 vs SDXL). Check if your Checkpoint matches your LoRA/ControlNet.",
        "device_type": "Device/Type Error: Input is {0} but Weights are {1}. Ensure everything is on the same device (GPU/CPU) and same precision.",
        "missing_module": "Missing Dependency: Python module '{0}' is missing. Please run 'pip install {0}' in your ComfyUI python environment.",
        "assertion": "Assertion Failed: {0}. This usually indicates the input data doesn't meet the node's expectations. Check the upstream node's output format.",
        "key_error": "Key Error: Key '{0}' not found. This might be due to incompatible model config or malformed Workflow JSON.",
        "attribute_error": "Attribute Error: Type '{0}' has no attribute '{1}'. This might be due to version mismatch in custom nodes or incorrect model format.",
        "shape_mismatch": "Shape Mismatch: {0}. Please verify input image dimensions match the model's expectations.",
        "file_not_found": "File Not Found: '{0}'. Please verify the path is correct and check if the model or LoRA has been downloaded.",
        "torch_oom": "PyTorch Out of Memory! This is the newer CUDA OOM error format. Suggestions: 1. Reduce Batch Size 2. Use --lowvram 3. Close other GPU programs.",
        "autograd": "A PyTorch Autograd error occurred. If you are training, check your loss function. If inference, this shouldn't happen.",
        "safetensors_error": "SafeTensors Error: Failed to load model. The file might be corrupted (incomplete download). Please delete and re-download the model.",
        "cudnn_error": "CUDNN Execution Failed: Your GPU or Driver might have issues with specific operations. Try running ComfyUI with '--force-fp32' or update your NVIDIA drivers.",
        "missing_insightface": "Missing InsightFace: IPAdapter or Reactor node requires 'insightface'. Please follow ComfyUI-Manager guide to install the pre-built wheel.",
        "model_vae_mismatch": "Model/VAE Mismatch: Detected mismatched configurations (e.g. SDXL VAE with SD1.5 Model). Please replace the VAE or Checkpoint.",
        "mps_oom": "MPS (Mac) OOM: Out of memory on Mac Metal backend. Try setting 'PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0' environment variable.",
        "invalid_prompt": "Invalid Prompt Format: The workflow JSON sent to ComfyUI is malformed. If this is from API, check your JSON syntax.",
        "validation_error": "Validation Error: {0}. This occurs when inputs do not match requirements (e.g. wrong type connection). Please check the node inputs.",
        "tensor_nan_inf": "Data Anomaly: Detected {0} in the tensor. This often causes black images. Check your model precision (FP16/FP32), VAE config, or CFG scale.",
        "meta_tensor": "Empty Data: Detected a 'Meta Tensor' which contains shape info but no actual data. This usually happens before model execution. If this persists during execution, check upstream nodes.",
    },
    "zh_TW": {
        "type_mismatch": "類型不匹配：模型預期 {0}（例如 fp16）但收到 {1}（例如 float32）。嘗試使用「Cast Tensor」節點或檢查 VAE/模型載入精度。",
        "dimension_mismatch": "維度不匹配：Tensor {0}（大小 {1}）與 Tensor {2}（大小 {3}）在維度 {4} 不匹配。檢查潛在空間維度或圖像尺寸，是否混用了不同解析度？",
        "oom": "OOM（記憶體不足）：GPU VRAM 已滿。建議：1. 減少 Batch Size 2. 使用 '--lowvram' 參數 3. 關閉其他 GPU 程式。",
        "matrix_mult": "矩陣乘法錯誤：這通常發生於模型架構與權重不匹配時（例如 SD1.5 vs SDXL）。請檢查 Checkpoint 是否與 LoRA/ControlNet 相符。",
        "device_type": "裝置/類型錯誤：輸入為 {0}，但權重為 {1}。請確保所有資料在相同裝置（GPU/CPU）且精度一致。",
        "missing_module": "缺少依賴：找不到 Python 模組 '{0}'。請在 ComfyUI 的 Python 環境中執行 'pip install {0}'。",
        "assertion": "斷言失敗：{0}。這通常表示輸入資料不符合節點預期，請檢查上游節點的輸出格式。",
        "key_error": "字典鍵值錯誤：找不到鍵 '{0}'。可能是模型配置不相容或 Workflow JSON 格式錯誤。",
        "attribute_error": "屬性錯誤：類型 '{0}' 沒有屬性 '{1}'。可能是自訂節點版本不匹配或模型格式錯誤。",
        "shape_mismatch": "形狀不匹配：{0}。請確認輸入圖像尺寸與模型預期一致。",
        "file_not_found": "找不到檔案：'{0}'。請確認路徑正確，並檢查模型或 LoRA 是否已下載。",
        "torch_oom": "PyTorch 記憶體不足！這是 CUDA OOM 的新版錯誤格式。建議：1. 降低 Batch Size 2. 使用 --lowvram 3. 關閉其他 GPU 程式。",
        "autograd": "發生 PyTorch Autograd 錯誤。若正在訓練，請檢查損失函數；若為推論模式，此錯誤不應發生。",
        "safetensors_error": "SafeTensors 錯誤：模型載入失敗，檔案可能已損壞（下載不完整）。請刪除該 Checkpoint/LoRA 並重新下載。",
        "cudnn_error": "CUDNN 執行失敗：顯卡或驅動程式可能不支援此操作。嘗試使用 '--force-fp32' 啟動 ComfyUI，或更新 NVIDIA 驅動。",
        "missing_insightface": "缺少 InsightFace：IPAdapter 或 Reactor 節點需要 'insightface' 庫。請參考 ComfyUI-Manager 指南安裝對應的 .whl 檔案。",
        "model_vae_mismatch": "Model/VAE 不匹配：檢測到配置衝突（例如 SDXL VAE 用於 SD1.5 模型）。請更換 VAE 或 Checkpoint。",
        "mps_oom": "MPS (Mac) 記憶體不足：Mac Metal 後端記憶體耗盡。嘗試設置環境變數 'PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0'。",
        "invalid_prompt": "Prompt 格式錯誤：傳送給 ComfyUI 的工作流 JSON 格式錯誤。若為 API 呼叫，請檢查 JSON 語法。",
        "validation_error": "驗證錯誤：{0}。這發生於輸入連接不符合節點要求（例如類型不匹配）。請檢查相關節點的輸入連接。",
        "tensor_nan_inf": "數據異常：在 Tensor 中偵測到 {0}。這通常會導致黑圖或崩壞。請檢查模型精度 (FP16/FP32)、VAE 設定或 CFG 數值。",
        "meta_tensor": "空數據：偵測到 'Meta Tensor'（只有形狀無數據）。這在模型執行前是正常的。若在執行階段出現，請檢查上游節點是否有實作錯誤。",
    },
    "zh_CN": {
        "type_mismatch": "类型不匹配：模型预期 {0}（例如 fp16）但收到 {1}（例如 float32）。尝试使用「Cast Tensor」节点或检查 VAE/模型加载精度。",
        "dimension_mismatch": "维度不匹配：Tensor {0}（大小 {1}）与 Tensor {2}（大小 {3}）在维度 {4} 不匹配。检查潜在空间维度或图像尺寸，是否混用了不同分辨率？",
        "oom": "OOM（内存不足）：GPU VRAM 已满。建议：1. 减少 Batch Size 2. 使用 '--lowvram' 参数 3. 关闭其他 GPU 程序。",
        "matrix_mult": "矩阵乘法错误：这通常发生于模型架构与权重不匹配时（例如 SD1.5 vs SDXL）。请检查 Checkpoint 是否与 LoRA/ControlNet 相符。",
        "device_type": "设备/类型错误：输入为 {0}，但权重为 {1}。请确保所有数据在相同设备（GPU/CPU）且精度一致。",
        "missing_module": "缺少依赖：找不到 Python 模块 '{0}'。请在 ComfyUI 的 Python 环境中执行 'pip install {0}'。",
        "assertion": "断言失败：{0}。这通常表示输入数据不符合节点预期，请检查上游节点的输出格式。",
        "key_error": "字典键值错误：找不到键 '{0}'。可能是模型配置不兼容或 Workflow JSON 格式错误。",
        "attribute_error": "属性错误：类型 '{0}' 没有属性 '{1}'。可能是自定义节点版本不匹配或模型格式错误。",
        "shape_mismatch": "形状不匹配：{0}。请确认输入图像尺寸与模型预期一致。",
        "file_not_found": "找不到文件：'{0}'。请确认路径正确，并检查模型或 LoRA 是否已下载。",
        "torch_oom": "PyTorch 内存不足！这是 CUDA OOM 的新版错误格式。建议：1. 降低 Batch Size 2. 使用 --lowvram 3. 关闭其他 GPU 程序。",
        "autograd": "发生 PyTorch Autograd 错误。若正在训练，请检查损失函数；若为推论模式，此错误不应发生。",
        "safetensors_error": "SafeTensors 错误：模型加载失败，文件可能已损坏（下载不完整）。请删除该 Checkpoint/LoRA 并重新下载。",
        "cudnn_error": "CUDNN 执行失败：显卡或驱动程序可能不支持此操作。尝试使用 '--force-fp32' 启动 ComfyUI，或更新 NVIDIA 驱动。",
        "missing_insightface": "缺少 InsightFace：IPAdapter 或 Reactor 节点需要 'insightface' 库。请参考 ComfyUI-Manager 指南安装对应的 .whl 文件。",
        "model_vae_mismatch": "Model/VAE 不匹配：检测到配置冲突（例如 SDXL VAE 用于 SD1.5 模型）。请更换 VAE 或 Checkpoint。",
        "mps_oom": "MPS (Mac) 内存不足：Mac Metal 后端内存耗尽。尝试设置环境变量 'PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0'。",
        "invalid_prompt": "Prompt 格式错误：发送给 ComfyUI 的工作流 JSON 格式错误。若为 API 调用，请检查 JSON 语法。",
        "validation_error": "验证错误：{0}。这发生于输入连接不符合节点要求（例如类型不匹配）。请检查相关节点的输入连接。",
        "tensor_nan_inf": "数据异常：在 Tensor 中检测到 {0}。这通常会导致黑图或崩坏。请检查模型精度 (FP16/FP32)、VAE 设置或 CFG 数值。",
        "meta_tensor": "空数据：检测到 'Meta Tensor'（只有形状无数据）。这在模型执行前是正常的。若在执行阶段出现，请检查上游节点是否有实现错误。",
    },
    "ja": {
        "type_mismatch": "型不一致：モデルは {0}（例：fp16）を想定していますが、{1}（例：float32）を受け取りました。「Cast Tensor」ノードの使用または VAE/モデルのロード精度を確認してください。",
        "dimension_mismatch": "次元不一致：Tensor {0}（サイズ {1}）と Tensor {2}（サイズ {3}）が次元 {4} で一致しません。潜在空間の次元または画像サイズを確認してください。異なる解像度を混在させていませんか？",
        "oom": "OOM（メモリ不足）：GPU VRAM がいっぱいです。対策：1. バッチサイズを減らす 2. '--lowvram' フラグを使用 3. 他の GPU アプリを閉じる。",
        "matrix_mult": "行列乗算エラー：これは通常、モデルアーキテクチャと重みが一致しない場合に発生します（例：SD1.5 vs SDXL）。Checkpoint が LoRA/ControlNet と一致しているか確認してください。",
        "device_type": "デバイス/型エラー：入力は {0} ですが、重みは {1} です。すべてのデータが同じデバイス（GPU/CPU）で同じ精度であることを確認してください。",
        "missing_module": "依存関係不足：Python モジュール '{0}' が見つかりません。ComfyUI の Python 環境で 'pip install {0}' を実行してください。",
        "assertion": "アサーション失敗：{0}。これは通常、入力データがノードの期待を満たしていないことを示します。上流ノードの出力形式を確認してください。",
        "key_error": "キーエラー：キー '{0}' が見つかりません。モデル設定の非互換性または Workflow JSON の形式エラーの可能性があります。",
        "attribute_error": "属性エラー：型 '{0}' には属性 '{1}' がありません。カスタムノードのバージョン不一致またはモデル形式のエラーの可能性があります。",
        "shape_mismatch": "形状不一致：{0}。入力画像の寸法がモデルの期待と一致していることを確認してください。",
        "file_not_found": "ファイルが見つかりません：'{0}'。パスが正しいことを確認し、モデルまたは LoRA がダウンロードされているか確認してください。",
        "torch_oom": "PyTorch メモリ不足！これは CUDA OOM の新しいエラー形式です。対策：1. バッチサイズを減らす 2. --lowvram を使用 3. 他の GPU プログラムを閉じる。",
        "autograd": "PyTorch Autograd エラーが発生しました。トレーニング中の場合は損失関数を確認してください。推論中の場合、このエラーは発生しないはずです。",
        "safetensors_error": "SafeTensors エラー：モデルの読み込みに失敗しました。ファイルが破損している可能性があります（不完全なダウンロード）。Checkpoint/LoRA を削除して再ダウンロードしてください。",
        "cudnn_error": "CUDNN 実行エラー：GPU またはドライバが特定の操作に対応していない可能性があります。'--force-fp32' オプションで ComfyUI を起動するか、NVIDIA ドライバを更新してください。",
        "missing_insightface": "InsightFace 不足：IPAdapter または Reactor ノードには 'insightface' が必要です。ComfyUI-Manager のガイドに従って、対応する .whl ファイルをインストールしてください。",
        "model_vae_mismatch": "Model/VAE 不一致：構成の不一致が検出されました（例：SD1.5 モデルでの SDXL VAE 使用）。VAE または Checkpoint を交換してください。",
        "mps_oom": "MPS (Mac) OOM：Mac Metal バックエンドでメモリ不足が発生しました。環境変数 'PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0' を設定してみてください。",
        "invalid_prompt": "無効なプロンプト形式：ComfyUI に送信されたワークフロー JSON が不正です。API 呼び出しの場合は、JSON 構文を確認してください。",
        "validation_error": "検証エラー：{0}。これは入力がノードの要件と一致しない場合（型の不一致など）に発生します。ノードの入力を確認してください。",
        "tensor_nan_inf": "データ異常：Tensor 内に {0} が検出されました。これは通常、黒い画像の原因となります。モデルの精度 (FP16/FP32)、VAE 設定、または CFG 値を確認してください。",
        "meta_tensor": "空データ：'Meta Tensor'（形状のみでデータなし）が検出されました。これはモデル実行前には正常です。実行中に発生した場合は、上流ノードを確認してください。",
    },
}


def set_language(lang: str) -> bool:
    """
    Set the current language for suggestions.
    
    Args:
        lang: Language code (e.g., 'en', 'zh_TW', 'zh_CN', 'ja')
        
    Returns:
        True if language was set successfully, False otherwise.
    """
    global _current_language
    if lang in SUPPORTED_LANGUAGES:
        _current_language = lang
        return True
    return False


def get_language() -> str:
    """Get the current language setting."""
    return _current_language


def get_suggestion(key: str, *args) -> Optional[str]:
    """
    Get a localized suggestion by key.
    
    Args:
        key: The suggestion key (from ERROR_KEYS values)
        *args: Format arguments for the suggestion template
        
    Returns:
        Formatted localized suggestion, or None if key not found.
    """
    lang_dict = SUGGESTIONS.get(_current_language, SUGGESTIONS["en"])
    template = lang_dict.get(key)
    
    if template is None:
        # Fallback to English
        template = SUGGESTIONS["en"].get(key)
    
    if template is None:
        return None
    
    try:
        if args:
            return "💡 SUGGESTION: " + template.format(*args)
        return "💡 SUGGESTION: " + template
    except (IndexError, KeyError):
        return "💡 SUGGESTION: " + template
