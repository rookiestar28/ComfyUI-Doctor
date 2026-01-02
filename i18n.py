"""
Internationalization (i18n) module for ComfyUI Runtime Diagnostics.
Provides multi-language support for error suggestions.
"""

from typing import Dict, Optional

# Current language setting
_current_language = "zh_TW"

# Supported languages
SUPPORTED_LANGUAGES = ["en", "zh_TW", "zh_CN", "ja", "de", "fr", "it", "es", "ko"]

# Error pattern keys (used as identifiers)
ERROR_KEYS = {
    # Core patterns
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
    "MISSING_INPUT": "missing_input",
    # ControlNet patterns
    "CONTROLNET_MODEL_NOT_FOUND": "controlnet_model_not_found",
    "CONTROLNET_PREPROCESSOR_FAILED": "controlnet_preprocessor_failed",
    "CONTROLNET_SIZE_MISMATCH": "controlnet_size_mismatch",
    "CONTROLNET_UNSUPPORTED_MODEL": "controlnet_unsupported_model",
    "CONTROLNET_INVALID_STRENGTH": "controlnet_invalid_strength",
    "CONTROLNET_MISSING_PREPROCESSOR": "controlnet_missing_preprocessor",
    "CONTROLNET_CHANNEL_MISMATCH": "controlnet_channel_mismatch",
    "CONTROLNET_DEVICE_MISMATCH": "controlnet_device_mismatch",
    # LoRA patterns
    "LORA_NOT_FOUND": "lora_not_found",
    "LORA_INCOMPATIBLE": "lora_incompatible",
    "LORA_CORRUPTED": "lora_corrupted",
    "LORA_STRENGTH_INVALID": "lora_strength_invalid",
    "LORA_OOM": "lora_oom",
    "LORA_KEY_MISMATCH": "lora_key_mismatch",
    # VAE patterns
    "VAE_DECODE_FAILED": "vae_decode_failed",
    "VAE_ENCODE_FAILED": "vae_encode_failed",
    "VAE_TILING_ERROR": "vae_tiling_error",
    "VAE_FP16_ISSUE": "vae_fp16_issue",
    "VAE_BATCH_SIZE_ERROR": "vae_batch_size_error",
    # AnimateDiff patterns
    "ANIMATEDIFF_MODEL_NOT_FOUND": "animatediff_model_not_found",
    "ANIMATEDIFF_FRAME_MISMATCH": "animatediff_frame_mismatch",
    "ANIMATEDIFF_CONTEXT_ERROR": "animatediff_context_error",
    "ANIMATEDIFF_OOM": "animatediff_oom",
    # IPAdapter patterns
    "IPADAPTER_MODEL_NOT_FOUND": "ipadapter_model_not_found",
    "IPADAPTER_IMAGE_ENCODING_FAILED": "ipadapter_image_encoding_failed",
    "IPADAPTER_INCOMPATIBLE": "ipadapter_incompatible",
    "IPADAPTER_WEIGHT_ERROR": "ipadapter_weight_error",
    # FaceRestore patterns
    "FACERESTORE_MODEL_NOT_FOUND": "facerestore_model_not_found",
    "FACERESTORE_DETECTION_FAILED": "facerestore_detection_failed",
    "FACERESTORE_OOM": "facerestore_oom",
    # Misc patterns
    "CHECKPOINT_CORRUPTED": "checkpoint_corrupted",
    "IMAGE_FORMAT_UNSUPPORTED": "image_format_unsupported",
    "SAMPLER_NOT_FOUND": "sampler_not_found",
    "SCHEDULER_ERROR": "scheduler_error",
    "CLIP_ENCODING_ERROR": "clip_encoding_error",
}

# Multi-language UI text for frontend
UI_TEXT: Dict[str, Dict[str, str]] = {
    "en": {
        "info_title": "INFO",
        "info_message": "Click 🏥 Doctor button (left sidebar) to analyze errors with AI",
        "settings_hint": "Settings available in",
        "settings_path": "ComfyUI Settings → Doctor",
        "sidebar_hint": "Open the Doctor sidebar (left panel) to analyze with AI",
        "locate_node_btn": "Locate Node on Canvas",
        "no_errors": "No active errors detected.",
        "privacy_mode": "Privacy Mode",
        "privacy_mode_none": "None (No sanitization)",
        "privacy_mode_basic": "Basic (Recommended)",
        "privacy_mode_strict": "Strict (Maximum privacy)",
        "privacy_mode_hint": "Controls what sensitive information is removed before sending to AI",
        # F7: Smart Parameter Injection
        "fix_apply_button": "⚡ Apply",
        "fix_apply_tooltip": "Apply parameter fix",
        "fix_applying": "Applying...",
        "fix_applied": "✓ Applied",
        "fix_error_node_not_found": "Node not found",
        "fix_error_widget_not_found": "Widget not found",
        "fix_error_unsafe_type": "Unsafe widget type",
        "fix_error_invalid_number": "Invalid number value",
    },
    "zh_TW": {
        "info_title": "資訊",
        "info_message": "點擊左側 🏥 Doctor 按鈕使用 AI 分析錯誤",
        "settings_hint": "設定選項位於",
        "settings_path": "ComfyUI 設定 → Doctor",
        "sidebar_hint": "點擊左側 Doctor 側邊欄以使用 AI 分析錯誤",
        "locate_node_btn": "在畫布上定位節點",
        "no_errors": "目前沒有偵測到錯誤。",
        "privacy_mode": "隱私模式",
        "privacy_mode_none": "無（不過濾）",
        "privacy_mode_basic": "基本（建議）",
        "privacy_mode_strict": "嚴格（最大隱私）",
        "privacy_mode_hint": "控制發送給 AI 前移除哪些敏感資訊",
        # F7: Smart Parameter Injection
        "fix_apply_button": "⚡ 套用",
        "fix_apply_tooltip": "套用參數修正",
        "fix_applying": "套用中...",
        "fix_applied": "✓ 已套用",
        "fix_error_node_not_found": "找不到節點",
        "fix_error_widget_not_found": "找不到小工具",
        "fix_error_unsafe_type": "不安全的小工具類型",
        "fix_error_invalid_number": "無效的數值",
    },
    "zh_CN": {
        "info_title": "信息",
        "info_message": "点击左侧 🏥 Doctor 按钮使用 AI 分析错误",
        "settings_hint": "设置选项位于",
        "settings_path": "ComfyUI 设置 → Doctor",
        "sidebar_hint": "点击左侧 Doctor 侧边栏以使用 AI 分析错误",
        "locate_node_btn": "在画布上定位节点",
        "no_errors": "当前没有检测到错误。",
        "privacy_mode": "隐私模式",
        "privacy_mode_none": "无（不过滤）",
        "privacy_mode_basic": "基本（推荐）",
        "privacy_mode_strict": "严格（最大隐私）",
        "privacy_mode_hint": "控制发送给 AI 前移除哪些敏感信息",
        # F7: Smart Parameter Injection
        "fix_apply_button": "⚡ 应用",
        "fix_apply_tooltip": "应用参数修正",
        "fix_applying": "应用中...",
        "fix_applied": "✓ 已应用",
        "fix_error_node_not_found": "找不到节点",
        "fix_error_widget_not_found": "找不到小工具",
        "fix_error_unsafe_type": "不安全的小工具类型",
        "fix_error_invalid_number": "无效的数值",
    },
    "ja": {
        "info_title": "情報",
        "info_message": "左側の 🏥 Doctor ボタンをクリックして AI でエラーを分析",
        "settings_hint": "設定は次の場所にあります",
        "settings_path": "ComfyUI 設定 → Doctor",
        "sidebar_hint": "左側の Doctor サイドバーを開いて AI で分析します",
        "locate_node_btn": "キャンバス上のノードを見つける",
        "no_errors": "アクティブなエラーは検出されていません。",
        "privacy_mode": "プライバシーモード",
        "privacy_mode_none": "なし（サニタイズなし）",
        "privacy_mode_basic": "基本（推奨）",
        "privacy_mode_strict": "厳格（最大プライバシー）",
        "privacy_mode_hint": "AI に送信する前に削除される機密情報を制御",
        # F7: Smart Parameter Injection
        "fix_apply_button": "⚡ 適用",
        "fix_apply_tooltip": "パラメータ修正を適用",
        "fix_applying": "適用中...",
        "fix_applied": "✓ 適用済み",
        "fix_error_node_not_found": "ノードが見つかりません",
        "fix_error_widget_not_found": "ウィジェットが見つかりません",
        "fix_error_unsafe_type": "安全でないウィジェットタイプ",
        "fix_error_invalid_number": "無効な数値",
    },
    "de": {
        "info_title": "INFO",
        "info_message": "Klicken Sie auf die 🏥 Doctor-Schaltfläche (linke Seitenleiste), um Fehler mit KI zu analysieren",
        "settings_hint": "Einstellungen verfügbar in",
        "settings_path": "ComfyUI Einstellungen → Doctor",
        "sidebar_hint": "Öffnen Sie die Doctor-Seitenleiste (linkes Panel), um mit KI zu analysieren",
        "locate_node_btn": "Knoten auf Canvas finden",
        "no_errors": "Keine aktiven Fehler erkannt.",
        "privacy_mode": "Datenschutzmodus",
        "privacy_mode_none": "Keine (Keine Bereinigung)",
        "privacy_mode_basic": "Grundlegend (Empfohlen)",
        "privacy_mode_strict": "Streng (Maximaler Datenschutz)",
        "privacy_mode_hint": "Steuert, welche sensiblen Informationen vor dem Senden an die KI entfernt werden",
        # F7: Smart Parameter Injection
        "fix_apply_button": "⚡ Anwenden",
        "fix_apply_tooltip": "Parameterkorrektur anwenden",
        "fix_applying": "Wird angewendet...",
        "fix_applied": "✓ Angewendet",
        "fix_error_node_not_found": "Knoten nicht gefunden",
        "fix_error_widget_not_found": "Widget nicht gefunden",
        "fix_error_unsafe_type": "Unsicherer Widget-Typ",
        "fix_error_invalid_number": "Ungültiger Zahlenwert",
    },
    "fr": {
        "info_title": "INFO",
        "info_message": "Cliquez sur le bouton 🏥 Doctor (barre latérale gauche) pour analyser les erreurs avec l'IA",
        "settings_hint": "Paramètres disponibles dans",
        "settings_path": "Paramètres ComfyUI → Doctor",
        "sidebar_hint": "Ouvrez la barre latérale Doctor (panneau gauche) pour analyser avec l'IA",
        "locate_node_btn": "Localiser le nœud sur le canevas",
        "no_errors": "Aucune erreur active détectée.",
        "privacy_mode": "Mode de confidentialité",
        "privacy_mode_none": "Aucun (Pas de nettoyage)",
        "privacy_mode_basic": "De base (Recommandé)",
        "privacy_mode_strict": "Strict (Confidentialité maximale)",
        "privacy_mode_hint": "Contrôle quelles informations sensibles sont supprimées avant l'envoi à l'IA",
        # F7: Smart Parameter Injection
        "fix_apply_button": "⚡ Appliquer",
        "fix_apply_tooltip": "Appliquer la correction",
        "fix_applying": "Application...",
        "fix_applied": "✓ Appliqué",
        "fix_error_node_not_found": "Nœud introuvable",
        "fix_error_widget_not_found": "Widget introuvable",
        "fix_error_unsafe_type": "Type de widget non sécurisé",
        "fix_error_invalid_number": "Valeur numérique invalide",
    },
    "it": {
        "info_title": "INFO",
        "info_message": "Fai clic sul pulsante 🏥 Doctor (barra laterale sinistra) per analizzare gli errori con l'IA",
        "settings_hint": "Impostazioni disponibili in",
        "settings_path": "Impostazioni ComfyUI → Doctor",
        "sidebar_hint": "Apri la barra laterale Doctor (pannello sinistro) per analizzare con l'IA",
        "locate_node_btn": "Trova nodo sulla tela",
        "no_errors": "Nessun errore attivo rilevato.",
        "privacy_mode": "Modalità privacy",
        "privacy_mode_none": "Nessuna (Nessuna pulizia)",
        "privacy_mode_basic": "Base (Consigliato)",
        "privacy_mode_strict": "Rigorosa (Privacy massima)",
        "privacy_mode_hint": "Controlla quali informazioni sensibili vengono rimosse prima dell'invio all'IA",
        # F7: Smart Parameter Injection
        "fix_apply_button": "⚡ Applica",
        "fix_apply_tooltip": "Applica correzione parametro",
        "fix_applying": "Applicazione...",
        "fix_applied": "✓ Applicato",
        "fix_error_node_not_found": "Nodo non trovato",
        "fix_error_widget_not_found": "Widget non trovato",
        "fix_error_unsafe_type": "Tipo di widget non sicuro",
        "fix_error_invalid_number": "Valore numerico non valido",
    },
    "es": {
        "info_title": "INFO",
        "info_message": "Haga clic en el botón 🏥 Doctor (barra lateral izquierda) para analizar errores con IA",
        "settings_hint": "Configuración disponible en",
        "settings_path": "Configuración de ComfyUI → Doctor",
        "sidebar_hint": "Abra la barra lateral de Doctor (panel izquierdo) para analizar con IA",
        "locate_node_btn": "Localizar nodo en lienzo",
        "no_errors": "No se detectaron errores activos.",
        "privacy_mode": "Modo de privacidad",
        "privacy_mode_none": "Ninguno (Sin limpieza)",
        "privacy_mode_basic": "Básico (Recomendado)",
        "privacy_mode_strict": "Estricto (Privacidad máxima)",
        "privacy_mode_hint": "Controla qué información sensible se elimina antes de enviar a la IA",
        # F7: Smart Parameter Injection
        "fix_apply_button": "⚡ Aplicar",
        "fix_apply_tooltip": "Aplicar corrección de parámetro",
        "fix_applying": "Aplicando...",
        "fix_applied": "✓ Aplicado",
        "fix_error_node_not_found": "Nodo no encontrado",
        "fix_error_widget_not_found": "Widget no encontrado",
        "fix_error_unsafe_type": "Tipo de widget no seguro",
        "fix_error_invalid_number": "Valor numérico inválido",
    },
    "ko": {
        "info_title": "정보",
        "info_message": "🏥 Doctor 버튼(왼쪽 사이드바)을 클릭하여 AI로 오류 분석",
        "settings_hint": "설정 위치",
        "settings_path": "ComfyUI 설정 → Doctor",
        "sidebar_hint": "AI로 분석하려면 Doctor 사이드바(왼쪽 패널)를 여세요",
        "locate_node_btn": "캔버스에서 노드 찾기",
        "no_errors": "활성 오류가 감지되지 않았습니다.",
        "privacy_mode": "개인정보 보호 모드",
        "privacy_mode_none": "없음 (정화 없음)",
        "privacy_mode_basic": "기본 (권장)",
        "privacy_mode_strict": "엄격 (최대 개인정보 보호)",
        "privacy_mode_hint": "AI로 전송하기 전에 제거할 민감한 정보 제어",
        # F7: Smart Parameter Injection
        "fix_apply_button": "⚡ 적용",
        "fix_apply_tooltip": "매개변수 수정 적용",
        "fix_applying": "적용 중...",
        "fix_applied": "✓ 적용됨",
        "fix_error_node_not_found": "노드를 찾을 수 없음",
        "fix_error_widget_not_found": "위젯을 찾을 수 없음",
        "fix_error_unsafe_type": "안전하지 않은 위젯 유형",
        "fix_error_invalid_number": "잘못된 숫자 값",
    },
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
        "validation_error": "Validation Error in {0}: {1}. Check input connections and ensure node requirements are met.",
        "tensor_nan_inf": "Data Anomaly: Detected {0} in the tensor. This often causes black images. Check your model precision (FP16/FP32), VAE config, or CFG scale.",
        "meta_tensor": "Empty Data: Detected a 'Meta Tensor' which contains shape info but no actual data. This usually happens before model execution. If this persists during execution, check upstream nodes.",
        "missing_input": "Missing Input: Required input '{0}' is not provided. Check if the upstream node output is connected correctly.",
        # ControlNet
        "controlnet_model_not_found": "ControlNet Model Not Found: The specified ControlNet model could not be found. Check if the model file exists in models/controlnet/ directory.",
        "controlnet_preprocessor_failed": "ControlNet Preprocessor Failed: The preprocessor execution failed. Verify the preprocessor is correctly installed and the input image is valid.",
        "controlnet_size_mismatch": "ControlNet Size Mismatch: The control image dimensions don't match the base image. Ensure both images have the same resolution.",
        "controlnet_unsupported_model": "Unsupported ControlNet Model: This ControlNet model type is not supported. Try using a different model or updating your ControlNet nodes.",
        "controlnet_invalid_strength": "Invalid ControlNet Strength: The control strength value must be between 0 and 1. Adjust the strength parameter.",
        "controlnet_missing_preprocessor": "Missing ControlNet Preprocessor: Required preprocessor not installed. Install the missing preprocessor via ComfyUI-Manager.",
        "controlnet_channel_mismatch": "ControlNet Channel Mismatch: The control image channel count doesn't match expectations. Ensure correct image format (RGB/Grayscale).",
        "controlnet_device_mismatch": "ControlNet Device Mismatch: ControlNet model is on a different device than the base model. Ensure all models are on the same device (GPU/CPU).",
        # LoRA
        "lora_not_found": "LoRA Not Found: The specified LoRA model file could not be found. Check if the file exists in models/loras/ directory.",
        "lora_incompatible": "Incompatible LoRA: This LoRA is incompatible with the current base model architecture. Ensure you're using the correct LoRA for your model (SD1.5/SDXL).",
        "lora_corrupted": "Corrupted LoRA File: The LoRA file appears to be corrupted or has an invalid format. Try re-downloading the file.",
        "lora_strength_invalid": "Invalid LoRA Strength: The LoRA strength value is invalid. Typical range is -2.0 to 2.0, with 1.0 being normal strength.",
        "lora_oom": "LoRA Out of Memory: Out of memory when loading or applying LoRA. Try reducing batch size or using fewer LoRAs simultaneously.",
        "lora_key_mismatch": "LoRA Key Mismatch: LoRA weight keys don't match the model structure. This LoRA may be for a different model architecture.",
        # VAE
        "vae_decode_failed": "VAE Decode Failed: VAE latent decode operation failed. Check VAE model compatibility and ensure latent dimensions are correct.",
        "vae_encode_failed": "VAE Encode Failed: VAE image encode operation failed. Verify input image format and VAE model compatibility.",
        "vae_tiling_error": "VAE Tiling Error: VAE tiling configuration is invalid. Adjust the tile size parameters or disable tiling.",
        "vae_fp16_issue": "VAE Precision Issue: VAE has precision issues, likely fp16/fp32 mismatch. Try using --force-fp32 or switch to a fp32 VAE.",
        "vae_batch_size_error": "VAE Batch Size Too Large: Batch size is too large for VAE processing. Reduce batch size or use tiled VAE.",
        # AnimateDiff
        "animatediff_model_not_found": "AnimateDiff Model Not Found: The AnimateDiff motion model file could not be found. Check models/animatediff/ directory.",
        "animatediff_frame_mismatch": "AnimateDiff Frame Mismatch: Frame count doesn't match expectations. Ensure consistent frame count throughout the workflow.",
        "animatediff_context_error": "AnimateDiff Context Error: Context length is invalid or out of range. Adjust the context_length parameter.",
        "animatediff_oom": "AnimateDiff Out of Memory: Out of memory during animation generation. Reduce frame count, resolution, or batch size.",
        # IPAdapter
        "ipadapter_model_not_found": "IPAdapter Model Not Found: The IPAdapter model file could not be found. Check models/ipadapter/ directory.",
        "ipadapter_image_encoding_failed": "IPAdapter Image Encoding Failed: Failed to encode image with CLIP vision model. Verify image format and model compatibility.",
        "ipadapter_incompatible": "Incompatible IPAdapter: This IPAdapter is incompatible with the current base model. Ensure correct IPAdapter version (SD1.5/SDXL).",
        "ipadapter_weight_error": "Invalid IPAdapter Weight: IPAdapter weight value is invalid. Typical range is 0.0 to 2.0.",
        # FaceRestore
        "facerestore_model_not_found": "Face Restoration Model Not Found: CodeFormer or GFPGAN model not found. Install via ComfyUI-Manager or check models/facerestore/.",
        "facerestore_detection_failed": "Face Detection Failed: No faces detected in the input image. Ensure the image contains visible faces.",
        "facerestore_oom": "Face Restoration Out of Memory: Out of memory during face restoration. Reduce image resolution or batch size.",
        # Misc
        "checkpoint_corrupted": "Corrupted Checkpoint: Model checkpoint file is corrupted or invalid. Try re-downloading the checkpoint.",
        "image_format_unsupported": "Unsupported Image Format: The image file format is not supported. Use common formats like PNG, JPG, or WEBP.",
        "sampler_not_found": "Sampler Not Found: The specified sampler is not available. Check sampler name or update ComfyUI to the latest version.",
        "scheduler_error": "Scheduler Configuration Error: The scheduler configuration is invalid. Verify scheduler parameters and compatibility.",
        "clip_encoding_error": "CLIP Text Encoding Failed: CLIP failed to encode the text prompt. Check for special characters or try simplifying the prompt.",
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
        "validation_error": "驗證錯誤於 {0}：{1}。請檢查輸入連接並確保符合節點要求。",
        "tensor_nan_inf": "數據異常：在 Tensor 中偵測到 {0}。這通常會導致黑圖或崩壞。請檢查模型精度 (FP16/FP32)、VAE 設定或 CFG 數值。",
        "meta_tensor": "空數據：偵測到 'Meta Tensor'（只有形狀無數據）。這在模型執行前是正常的。若在執行階段出現，請檢查上游節點是否有實作錯誤。",
        "missing_input": "輸入源資訊遺失：{0}。請檢查上游節點輸出是否正常連接。",
        # ControlNet
        "controlnet_model_not_found": "找不到 ControlNet 模型：找不到指定的 ControlNet 模型檔案。請檢查 models/controlnet/ 目錄中是否存在該檔案。",
        "controlnet_preprocessor_failed": "ControlNet 前處理器失敗：前處理器執行失敗。請確認前處理器已正確安裝且輸入圖像有效。",
        "controlnet_size_mismatch": "ControlNet 尺寸不匹配：控制圖像的尺寸與基底圖像不符。請確保兩張圖像解析度相同。",
        "controlnet_unsupported_model": "不支援的 ControlNet 模型：此 ControlNet 模型類型不被支援。請嘗試使用其他模型或更新 ControlNet 節點。",
        "controlnet_invalid_strength": "ControlNet 強度無效：控制強度值必須介於 0 到 1 之間。請調整強度參數。",
        "controlnet_missing_preprocessor": "缺少 ControlNet 前處理器：所需的前處理器未安裝。請透過 ComfyUI-Manager 安裝缺少的前處理器。",
        "controlnet_channel_mismatch": "ControlNet 通道數不匹配：控制圖像的通道數與預期不符。請確保使用正確的圖像格式（RGB/灰階）。",
        "controlnet_device_mismatch": "ControlNet 裝置不匹配：ControlNet 模型與基底模型在不同裝置上。請確保所有模型都在同一裝置（GPU/CPU）。",
        # LoRA
        "lora_not_found": "找不到 LoRA：找不到指定的 LoRA 模型檔案。請檢查 models/loras/ 目錄中是否存在該檔案。",
        "lora_incompatible": "LoRA 不相容：此 LoRA 與當前基底模型架構不相容。請確保使用正確的 LoRA（SD1.5/SDXL）。",
        "lora_corrupted": "LoRA 檔案損壞：LoRA 檔案似乎已損壞或格式無效。請嘗試重新下載檔案。",
        "lora_strength_invalid": "LoRA 強度無效：LoRA 強度值無效。典型範圍為 -2.0 到 2.0，正常強度為 1.0。",
        "lora_oom": "LoRA 記憶體不足：載入或套用 LoRA 時記憶體不足。請嘗試減少批次大小或同時使用較少的 LoRA。",
        "lora_key_mismatch": "LoRA 鍵值不匹配：LoRA 權重鍵值與模型結構不符。此 LoRA 可能適用於不同的模型架構。",
        # VAE
        "vae_decode_failed": "VAE 解碼失敗：VAE 潛在空間解碼操作失敗。請檢查 VAE 模型相容性並確保潛在空間維度正確。",
        "vae_encode_failed": "VAE 編碼失敗：VAE 圖像編碼操作失敗。請驗證輸入圖像格式和 VAE 模型相容性。",
        "vae_tiling_error": "VAE 分塊錯誤：VAE 分塊配置無效。請調整分塊大小參數或停用分塊功能。",
        "vae_fp16_issue": "VAE 精度問題：VAE 有精度問題，可能是 fp16/fp32 不匹配。請嘗試使用 --force-fp32 或切換到 fp32 VAE。",
        "vae_batch_size_error": "VAE 批次大小過大：批次大小對 VAE 處理而言過大。請減少批次大小或使用分塊 VAE。",
        # AnimateDiff
        "animatediff_model_not_found": "找不到 AnimateDiff 模型：找不到 AnimateDiff 動態模型檔案。請檢查 models/animatediff/ 目錄。",
        "animatediff_frame_mismatch": "AnimateDiff 幀數不匹配：幀數與預期不符。請確保整個工作流程中幀數一致。",
        "animatediff_context_error": "AnimateDiff 上下文錯誤：上下文長度無效或超出範圍。請調整 context_length 參數。",
        "animatediff_oom": "AnimateDiff 記憶體不足：動畫生成時記憶體不足。請減少幀數、解析度或批次大小。",
        # IPAdapter
        "ipadapter_model_not_found": "找不到 IPAdapter 模型：找不到 IPAdapter 模型檔案。請檢查 models/ipadapter/ 目錄。",
        "ipadapter_image_encoding_failed": "IPAdapter 圖像編碼失敗：無法使用 CLIP 視覺模型編碼圖像。請驗證圖像格式和模型相容性。",
        "ipadapter_incompatible": "IPAdapter 不相容：此 IPAdapter 與當前基底模型不相容。請確保使用正確的 IPAdapter 版本（SD1.5/SDXL）。",
        "ipadapter_weight_error": "IPAdapter 權重無效：IPAdapter 權重值無效。典型範圍為 0.0 到 2.0。",
        # FaceRestore
        "facerestore_model_not_found": "找不到臉部修復模型：找不到 CodeFormer 或 GFPGAN 模型。請透過 ComfyUI-Manager 安裝或檢查 models/facerestore/。",
        "facerestore_detection_failed": "臉部偵測失敗：輸入圖像中未偵測到臉部。請確保圖像包含可見的臉部。",
        "facerestore_oom": "臉部修復記憶體不足：臉部修復時記憶體不足。請減少圖像解析度或批次大小。",
        # Misc
        "checkpoint_corrupted": "Checkpoint 損壞：模型 checkpoint 檔案已損壞或無效。請嘗試重新下載 checkpoint。",
        "image_format_unsupported": "不支援的圖像格式：不支援該圖像檔案格式。請使用常見格式如 PNG、JPG 或 WEBP。",
        "sampler_not_found": "找不到取樣器：指定的取樣器不可用。請檢查取樣器名稱或將 ComfyUI 更新至最新版本。",
        "scheduler_error": "排程器配置錯誤：排程器配置無效。請驗證排程器參數和相容性。",
        "clip_encoding_error": "CLIP 文字編碼失敗：CLIP 無法編碼文字提示。請檢查特殊字元或嘗試簡化提示。",
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
        "validation_error": "验证错误于 {0}：{1}。请检查输入连接并确保符合节点要求。",
        "tensor_nan_inf": "数据异常：在 Tensor 中检测到 {0}。这通常会导致黑图或崩坏。请检查模型精度 (FP16/FP32)、VAE 设置或 CFG 数值。",
        "meta_tensor": "空数据：检测到 'Meta Tensor'（只有形状无数据）。这在模型执行前是正常的。若在执行阶段出现，请检查上游节点是否有实现错误。",
        "missing_input": "输入源信息缺失：{0}。请检查上游节点输出是否正常连接。",
        # ControlNet
        "controlnet_model_not_found": "找不到 ControlNet 模型：找不到指定的 ControlNet 模型文件。请检查 models/controlnet/ 目录中是否存在该文件。",
        "controlnet_preprocessor_failed": "ControlNet 预处理器失败：预处理器执行失败。请确认预处理器已正确安装且输入图像有效。",
        "controlnet_size_mismatch": "ControlNet 尺寸不匹配：控制图像的尺寸与基底图像不符。请确保两张图像分辨率相同。",
        "controlnet_unsupported_model": "不支持的 ControlNet 模型：此 ControlNet 模型类型不被支持。请尝试使用其他模型或更新 ControlNet 节点。",
        "controlnet_invalid_strength": "ControlNet 强度无效：控制强度值必须介于 0 到 1 之间。请调整强度参数。",
        "controlnet_missing_preprocessor": "缺少 ControlNet 预处理器：所需的预处理器未安装。请通过 ComfyUI-Manager 安装缺少的预处理器。",
        "controlnet_channel_mismatch": "ControlNet 通道数不匹配：控制图像的通道数与预期不符。请确保使用正确的图像格式（RGB/灰阶）。",
        "controlnet_device_mismatch": "ControlNet 设备不匹配：ControlNet 模型与基底模型在不同设备上。请确保所有模型都在同一设备（GPU/CPU）。",
        # LoRA
        "lora_not_found": "找不到 LoRA：找不到指定的 LoRA 模型文件。请检查 models/loras/ 目录中是否存在该文件。",
        "lora_incompatible": "LoRA 不兼容：此 LoRA 与当前基底模型架构不兼容。请确保使用正确的 LoRA（SD1.5/SDXL）。",
        "lora_corrupted": "LoRA 文件损坏：LoRA 文件似乎已损坏或格式无效。请尝试重新下载文件。",
        "lora_strength_invalid": "LoRA 强度无效：LoRA 强度值无效。典型范围为 -2.0 到 2.0，正常强度为 1.0。",
        "lora_oom": "LoRA 内存不足：载入或套用 LoRA 时内存不足。请尝试减少批次大小或同时使用较少的 LoRA。",
        "lora_key_mismatch": "LoRA 键值不匹配：LoRA 权重键值与模型结构不符。此 LoRA 可能适用于不同的模型架构。",
        # VAE
        "vae_decode_failed": "VAE 解码失败：VAE 潜在空间解码操作失败。请检查 VAE 模型兼容性并确保潜在空间维度正确。",
        "vae_encode_failed": "VAE 编码失败：VAE 图像编码操作失败。请验证输入图像格式和 VAE 模型兼容性。",
        "vae_tiling_error": "VAE 分块错误：VAE 分块配置无效。请调整分块大小参数或停用分块功能。",
        "vae_fp16_issue": "VAE 精度问题：VAE 有精度问题，可能是 fp16/fp32 不匹配。请尝试使用 --force-fp32 或切换到 fp32 VAE。",
        "vae_batch_size_error": "VAE 批次大小过大：批次大小对 VAE 处理而言过大。请减少批次大小或使用分块 VAE。",
        # AnimateDiff
        "animatediff_model_not_found": "找不到 AnimateDiff 模型：找不到 AnimateDiff 动态模型文件。请检查 models/animatediff/ 目录。",
        "animatediff_frame_mismatch": "AnimateDiff 帧数不匹配：帧数与预期不符。请确保整个工作流程中帧数一致。",
        "animatediff_context_error": "AnimateDiff 上下文错误：上下文长度无效或超出范围。请调整 context_length 参数。",
        "animatediff_oom": "AnimateDiff 内存不足：动画生成时内存不足。请减少帧数、分辨率或批次大小。",
        # IPAdapter
        "ipadapter_model_not_found": "找不到 IPAdapter 模型：找不到 IPAdapter 模型文件。请检查 models/ipadapter/ 目录。",
        "ipadapter_image_encoding_failed": "IPAdapter 图像编码失败：无法使用 CLIP 视觉模型编码图像。请验证图像格式和模型兼容性。",
        "ipadapter_incompatible": "IPAdapter 不兼容：此 IPAdapter 与当前基底模型不兼容。请确保使用正确的 IPAdapter 版本（SD1.5/SDXL）。",
        "ipadapter_weight_error": "IPAdapter 权重无效：IPAdapter 权重值无效。典型范围为 0.0 到 2.0。",
        # FaceRestore
        "facerestore_model_not_found": "找不到脸部修复模型：找不到 CodeFormer 或 GFPGAN 模型。请通过 ComfyUI-Manager 安装或检查 models/facerestore/。",
        "facerestore_detection_failed": "脸部侦测失败：输入图像中未侦测到脸部。请确保图像包含可见的脸部。",
        "facerestore_oom": "脸部修复内存不足：脸部修复时内存不足。请减少图像分辨率或批次大小。",
        # Misc
        "checkpoint_corrupted": "Checkpoint 损坏：模型 checkpoint 文件已损坏或无效。请尝试重新下载 checkpoint。",
        "image_format_unsupported": "不支持的图像格式：不支持该图像文件格式。请使用常见格式如 PNG、JPG 或 WEBP。",
        "sampler_not_found": "找不到采样器：指定的采样器不可用。请检查采样器名称或将 ComfyUI 更新至最新版本。",
        "scheduler_error": "调度器配置错误：调度器配置无效。请验证调度器参数和兼容性。",
        "clip_encoding_error": "CLIP 文字编码失败：CLIP 无法编码文字提示。请检查特殊字符或尝试简化提示。",
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
        "validation_error": "{0} の検証エラー：{1}。入力接続を確認し、ノード要件を満たしているか確認してください。",
        "tensor_nan_inf": "データ異常：Tensor 内に {0} が検出されました。これは通常、黒い画像の原因となります。モデルの精度 (FP16/FP32)、VAE 設定、または CFG 値を確認してください。",
        "meta_tensor": "空データ：'Meta Tensor'（形状のみでデータなし）が検出されました。これはモデル実行前には正常です。実行中に発生した場合は、上流ノードを確認してください。",
        "missing_input": "入力不足：必須入力 '{0}' が提供されていません。上流ノードの出力が正しく接続されているか確認してください。",
    },
    "de": {
        "type_mismatch": "Typkonflikt: Das Modell erwartet {0} (z.B. fp16), hat aber {1} (z.B. float32) erhalten. Versuchen Sie einen 'Cast Tensor'-Knoten zu verwenden oder überprüfen Sie die Ladepräzision Ihres VAE/Modells.",
        "dimension_mismatch": "Dimensionskonflikt: Tensor {0} (Größe {1}) passt nicht zu Tensor {2} (Größe {3}) an Dimension {4}. Überprüfen Sie Ihre Latent-Dimensionen oder Bildgrößen. Mischen Sie verschiedene Auflösungen?",
        "oom": "OOM (Speicher voll): Ihr GPU-VRAM ist voll. Versuchen Sie: 1. Batch-Größe reduzieren. 2. '--lowvram'-Flag verwenden. 3. Andere GPU-Apps schließen.",
        "matrix_mult": "Matrixmultiplikationsfehler: Dies tritt normalerweise auf, wenn Modellarchitektur nicht zu den Gewichten passt (z.B. SD1.5 vs SDXL). Prüfen Sie, ob Ihr Checkpoint zu LoRA/ControlNet passt.",
        "device_type": "Geräte-/Typfehler: Eingabe ist {0}, aber Gewichte sind {1}. Stellen Sie sicher, dass alles auf demselben Gerät (GPU/CPU) und derselben Präzision ist.",
        "missing_module": "Fehlende Abhängigkeit: Python-Modul '{0}' fehlt. Bitte führen Sie 'pip install {0}' in Ihrer ComfyUI Python-Umgebung aus.",
        "assertion": "Assertion fehlgeschlagen: {0}. Dies deutet normalerweise darauf hin, dass die Eingabedaten nicht den Erwartungen des Knotens entsprechen. Überprüfen Sie das Ausgabeformat des vorgelagerten Knotens.",
        "key_error": "Schlüsselfehler: Schlüssel '{0}' nicht gefunden. Dies könnte auf eine inkompatible Modellkonfiguration oder fehlerhaftes Workflow-JSON zurückzuführen sein.",
        "attribute_error": "Attributfehler: Typ '{0}' hat kein Attribut '{1}'. Dies könnte auf eine Versionsinkompatibilität bei benutzerdefinierten Knoten oder ein falsches Modellformat zurückzuführen sein.",
        "shape_mismatch": "Formkonflikt: {0}. Bitte überprüfen Sie, ob die Eingabebildabmessungen den Erwartungen des Modells entsprechen.",
        "file_not_found": "Datei nicht gefunden: '{0}'. Bitte überprüfen Sie, ob der Pfad korrekt ist und ob das Modell oder LoRA heruntergeladen wurde.",
        "torch_oom": "PyTorch Speicher voll! Dies ist das neuere CUDA-OOM-Fehlerformat. Vorschläge: 1. Batch-Größe reduzieren 2. --lowvram verwenden 3. Andere GPU-Programme schließen.",
        "autograd": "Ein PyTorch Autograd-Fehler ist aufgetreten. Wenn Sie trainieren, überprüfen Sie Ihre Verlustfunktion. Bei Inferenz sollte dies nicht passieren.",
        "safetensors_error": "SafeTensors-Fehler: Modell konnte nicht geladen werden. Die Datei könnte beschädigt sein (unvollständiger Download). Bitte löschen Sie das Modell und laden Sie es erneut herunter.",
        "cudnn_error": "CUDNN-Ausführungsfehler: Ihre GPU oder Ihr Treiber könnte Probleme mit bestimmten Operationen haben. Versuchen Sie ComfyUI mit '--force-fp32' zu starten oder aktualisieren Sie Ihre NVIDIA-Treiber.",
        "missing_insightface": "Fehlendes InsightFace: IPAdapter oder Reactor-Knoten benötigen 'insightface'. Bitte folgen Sie der ComfyUI-Manager-Anleitung zur Installation des vorgefertigten Wheels.",
        "model_vae_mismatch": "Modell/VAE-Konflikt: Inkompatible Konfigurationen erkannt (z.B. SDXL VAE mit SD1.5 Modell). Bitte ersetzen Sie VAE oder Checkpoint.",
        "mps_oom": "MPS (Mac) OOM: Speicher auf Mac Metal Backend voll. Versuchen Sie die Umgebungsvariable 'PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0' zu setzen.",
        "invalid_prompt": "Ungültiges Prompt-Format: Das an ComfyUI gesendete Workflow-JSON ist fehlerhaft. Bei API-Aufruf überprüfen Sie Ihre JSON-Syntax.",
        "validation_error": "Validierungsfehler in {0}: {1}. Überprüfen Sie Eingabeverbindungen und stellen Sie sicher, dass Knotenanforderungen erfüllt sind.",
        "tensor_nan_inf": "Datenanomalie: {0} im Tensor erkannt. Dies führt oft zu schwarzen Bildern. Überprüfen Sie Ihre Modellpräzision (FP16/FP32), VAE-Konfiguration oder CFG-Skalierung.",
        "meta_tensor": "Leere Daten: 'Meta Tensor' erkannt, der Forminformationen enthält, aber keine tatsächlichen Daten. Dies ist vor der Modellausführung normal. Wenn dies während der Ausführung fortbesteht, überprüfen Sie vorgelagerte Knoten.",
        "missing_input": "Fehlende Eingabe: Erforderliche Eingabe '{0}' wird nicht bereitgestellt. Überprüfen Sie, ob die Ausgabe des vorgelagerten Knotens korrekt verbunden ist.",
    },
    "fr": {
        "type_mismatch": "Incompatibilité de type : Le modèle attend {0} (par ex. fp16) mais a reçu {1} (par ex. float32). Essayez d'utiliser un nœud 'Cast Tensor' ou vérifiez la précision de chargement de votre VAE/Modèle.",
        "dimension_mismatch": "Incompatibilité de dimension : Le tenseur {0} (taille {1}) ne correspond pas au tenseur {2} (taille {3}) à la dimension {4}. Vérifiez vos dimensions latentes ou tailles d'image. Mélangez-vous différentes résolutions ?",
        "oom": "OOM (Mémoire insuffisante) : Votre VRAM GPU est pleine. Essayez : 1. Réduire la taille de lot. 2. Utiliser le flag '--lowvram'. 3. Fermer d'autres applications GPU.",
        "matrix_mult": "Erreur de multiplication matricielle : Cela se produit généralement lorsque l'architecture du modèle ne correspond pas aux poids (par ex. SD1.5 vs SDXL). Vérifiez si votre Checkpoint correspond à votre LoRA/ControlNet.",
        "device_type": "Erreur de périphérique/type : L'entrée est {0} mais les poids sont {1}. Assurez-vous que tout est sur le même périphérique (GPU/CPU) et la même précision.",
        "missing_module": "Dépendance manquante : Le module Python '{0}' est manquant. Veuillez exécuter 'pip install {0}' dans votre environnement Python ComfyUI.",
        "assertion": "Assertion échouée : {0}. Cela indique généralement que les données d'entrée ne répondent pas aux attentes du nœud. Vérifiez le format de sortie du nœud en amont.",
        "key_error": "Erreur de clé : Clé '{0}' introuvable. Cela peut être dû à une configuration de modèle incompatible ou un JSON de workflow malformé.",
        "attribute_error": "Erreur d'attribut : Le type '{0}' n'a pas d'attribut '{1}'. Cela peut être dû à une incompatibilité de version dans les nœuds personnalisés ou un format de modèle incorrect.",
        "shape_mismatch": "Incompatibilité de forme : {0}. Veuillez vérifier que les dimensions de l'image d'entrée correspondent aux attentes du modèle.",
        "file_not_found": "Fichier introuvable : '{0}'. Veuillez vérifier que le chemin est correct et que le modèle ou LoRA a été téléchargé.",
        "torch_oom": "Mémoire PyTorch insuffisante ! Ceci est le nouveau format d'erreur CUDA OOM. Suggestions : 1. Réduire la taille de lot 2. Utiliser --lowvram 3. Fermer d'autres programmes GPU.",
        "autograd": "Une erreur PyTorch Autograd s'est produite. Si vous entraînez, vérifiez votre fonction de perte. En inférence, cela ne devrait pas arriver.",
        "safetensors_error": "Erreur SafeTensors : Échec du chargement du modèle. Le fichier pourrait être corrompu (téléchargement incomplet). Veuillez supprimer et retélécharger le modèle.",
        "cudnn_error": "Échec d'exécution CUDNN : Votre GPU ou pilote pourrait avoir des problèmes avec des opérations spécifiques. Essayez d'exécuter ComfyUI avec '--force-fp32' ou mettez à jour vos pilotes NVIDIA.",
        "missing_insightface": "InsightFace manquant : Le nœud IPAdapter ou Reactor nécessite 'insightface'. Veuillez suivre le guide ComfyUI-Manager pour installer la roue pré-construite.",
        "model_vae_mismatch": "Incompatibilité Modèle/VAE : Configurations incompatibles détectées (par ex. VAE SDXL avec modèle SD1.5). Veuillez remplacer le VAE ou le Checkpoint.",
        "mps_oom": "MPS (Mac) OOM : Mémoire insuffisante sur le backend Mac Metal. Essayez de définir la variable d'environnement 'PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0'.",
        "invalid_prompt": "Format de prompt invalide : Le JSON de workflow envoyé à ComfyUI est malformé. Si c'est depuis l'API, vérifiez votre syntaxe JSON.",
        "validation_error": "Erreur de validation dans {0} : {1}. Vérifiez les connexions d'entrée et assurez-vous que les exigences du nœud sont respectées.",
        "tensor_nan_inf": "Anomalie de données : {0} détecté dans le tenseur. Cela cause souvent des images noires. Vérifiez la précision de votre modèle (FP16/FP32), la configuration VAE ou l'échelle CFG.",
        "meta_tensor": "Données vides : 'Meta Tensor' détecté qui contient des informations de forme mais pas de données réelles. C'est normal avant l'exécution du modèle. Si cela persiste pendant l'exécution, vérifiez les nœuds en amont.",
        "missing_input": "Entrée manquante : L'entrée requise '{0}' n'est pas fournie. Vérifiez si la sortie du nœud en amont est correctement connectée.",
    },
    "it": {
        "type_mismatch": "Tipo non corrispondente: Il modello si aspetta {0} (es. fp16) ma ha ricevuto {1} (es. float32). Prova a usare un nodo 'Cast Tensor' o controlla la precisione di caricamento del tuo VAE/Modello.",
        "dimension_mismatch": "Dimensione non corrispondente: Il tensore {0} (dimensione {1}) non corrisponde al tensore {2} (dimensione {3}) alla dimensione {4}. Controlla le dimensioni latenti o le dimensioni dell'immagine. Stai mescolando risoluzioni diverse?",
        "oom": "OOM (Memoria esaurita): La VRAM della tua GPU è piena. Prova: 1. Riduci la dimensione del batch. 2. Usa il flag '--lowvram'. 3. Chiudi altre app GPU.",
        "matrix_mult": "Errore di moltiplicazione matriciale: Questo di solito accade quando l'architettura del modello non corrisponde ai pesi (es. SD1.5 vs SDXL). Controlla se il tuo Checkpoint corrisponde al tuo LoRA/ControlNet.",
        "device_type": "Errore dispositivo/tipo: L'input è {0} ma i pesi sono {1}. Assicurati che tutto sia sullo stesso dispositivo (GPU/CPU) e stessa precisione.",
        "missing_module": "Dipendenza mancante: Il modulo Python '{0}' è mancante. Esegui 'pip install {0}' nel tuo ambiente Python ComfyUI.",
        "assertion": "Asserzione fallita: {0}. Questo di solito indica che i dati di input non soddisfano le aspettative del nodo. Controlla il formato di output del nodo a monte.",
        "key_error": "Errore di chiave: Chiave '{0}' non trovata. Questo potrebbe essere dovuto a una configurazione del modello incompatibile o JSON del workflow malformato.",
        "attribute_error": "Errore di attributo: Il tipo '{0}' non ha l'attributo '{1}'. Questo potrebbe essere dovuto a una non corrispondenza di versione nei nodi personalizzati o formato del modello errato.",
        "shape_mismatch": "Forma non corrispondente: {0}. Verifica che le dimensioni dell'immagine di input corrispondano alle aspettative del modello.",
        "file_not_found": "File non trovato: '{0}'. Verifica che il percorso sia corretto e che il modello o LoRA sia stato scaricato.",
        "torch_oom": "Memoria PyTorch esaurita! Questo è il nuovo formato di errore CUDA OOM. Suggerimenti: 1. Riduci dimensione batch 2. Usa --lowvram 3. Chiudi altri programmi GPU.",
        "autograd": "Si è verificato un errore PyTorch Autograd. Se stai addestrando, controlla la tua funzione di perdita. In inferenza, questo non dovrebbe accadere.",
        "safetensors_error": "Errore SafeTensors: Caricamento del modello fallito. Il file potrebbe essere corrotto (download incompleto). Elimina e riscarica il modello.",
        "cudnn_error": "Esecuzione CUDNN fallita: La tua GPU o driver potrebbe avere problemi con operazioni specifiche. Prova a eseguire ComfyUI con '--force-fp32' o aggiorna i tuoi driver NVIDIA.",
        "missing_insightface": "InsightFace mancante: Il nodo IPAdapter o Reactor richiede 'insightface'. Segui la guida ComfyUI-Manager per installare la wheel pre-costruita.",
        "model_vae_mismatch": "Incompatibilità Modello/VAE: Configurazioni non corrispondenti rilevate (es. VAE SDXL con modello SD1.5). Sostituisci il VAE o il Checkpoint.",
        "mps_oom": "MPS (Mac) OOM: Memoria esaurita sul backend Mac Metal. Prova a impostare la variabile d'ambiente 'PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0'.",
        "invalid_prompt": "Formato prompt non valido: Il JSON del workflow inviato a ComfyUI è malformato. Se è da API, controlla la tua sintassi JSON.",
        "validation_error": "Errore di validazione in {0}: {1}. Controlla le connessioni di input e assicurati che i requisiti del nodo siano soddisfatti.",
        "tensor_nan_inf": "Anomalia dati: {0} rilevato nel tensore. Questo spesso causa immagini nere. Controlla la precisione del tuo modello (FP16/FP32), configurazione VAE o scala CFG.",
        "meta_tensor": "Dati vuoti: Rilevato 'Meta Tensor' che contiene info sulla forma ma nessun dato effettivo. Questo è normale prima dell'esecuzione del modello. Se persiste durante l'esecuzione, controlla i nodi a monte.",
        "missing_input": "Input mancante: L'input richiesto '{0}' non è fornito. Controlla se l'output del nodo a monte è collegato correttamente.",
    },
    "es": {
        "type_mismatch": "Tipo no coincidente: El modelo espera {0} (ej. fp16) pero recibió {1} (ej. float32). Intenta usar un nodo 'Cast Tensor' o verifica la precisión de carga de tu VAE/Modelo.",
        "dimension_mismatch": "Dimensión no coincidente: El tensor {0} (tamaño {1}) no coincide con el tensor {2} (tamaño {3}) en la dimensión {4}. Verifica tus dimensiones latentes o tamaños de imagen. ¿Estás mezclando diferentes resoluciones?",
        "oom": "OOM (Sin memoria): Tu VRAM GPU está llena. Intenta: 1. Reducir el tamaño del lote. 2. Usar el flag '--lowvram'. 3. Cerrar otras apps GPU.",
        "matrix_mult": "Error de multiplicación de matrices: Esto generalmente ocurre cuando la arquitectura del modelo no coincide con los pesos (ej. SD1.5 vs SDXL). Verifica si tu Checkpoint coincide con tu LoRA/ControlNet.",
        "device_type": "Error de dispositivo/tipo: La entrada es {0} pero los pesos son {1}. Asegúrate de que todo esté en el mismo dispositivo (GPU/CPU) y misma precisión.",
        "missing_module": "Dependencia faltante: El módulo Python '{0}' está faltante. Ejecuta 'pip install {0}' en tu entorno Python de ComfyUI.",
        "assertion": "Aserción fallida: {0}. Esto generalmente indica que los datos de entrada no cumplen con las expectativas del nodo. Verifica el formato de salida del nodo anterior.",
        "key_error": "Error de clave: Clave '{0}' no encontrada. Esto puede deberse a una configuración de modelo incompatible o JSON de flujo malformado.",
        "attribute_error": "Error de atributo: El tipo '{0}' no tiene el atributo '{1}'. Esto puede deberse a una incompatibilidad de versión en nodos personalizados o formato de modelo incorrecto.",
        "shape_mismatch": "Forma no coincidente: {0}. Verifica que las dimensiones de la imagen de entrada coincidan con las expectativas del modelo.",
        "file_not_found": "Archivo no encontrado: '{0}'. Verifica que la ruta sea correcta y que el modelo o LoRA haya sido descargado.",
        "torch_oom": "¡Memoria PyTorch agotada! Este es el nuevo formato de error CUDA OOM. Sugerencias: 1. Reducir tamaño de lote 2. Usar --lowvram 3. Cerrar otros programas GPU.",
        "autograd": "Ocurrió un error de PyTorch Autograd. Si estás entrenando, verifica tu función de pérdida. En inferencia, esto no debería ocurrir.",
        "safetensors_error": "Error SafeTensors: Fallo al cargar el modelo. El archivo puede estar corrupto (descarga incompleta). Elimina y vuelve a descargar el modelo.",
        "cudnn_error": "Fallo de ejecución CUDNN: Tu GPU o controlador puede tener problemas con operaciones específicas. Intenta ejecutar ComfyUI con '--force-fp32' o actualiza tus controladores NVIDIA.",
        "missing_insightface": "InsightFace faltante: El nodo IPAdapter o Reactor requiere 'insightface'. Sigue la guía de ComfyUI-Manager para instalar el wheel pre-construido.",
        "model_vae_mismatch": "Incompatibilidad Modelo/VAE: Configuraciones no coincidentes detectadas (ej. VAE SDXL con modelo SD1.5). Reemplaza el VAE o Checkpoint.",
        "mps_oom": "MPS (Mac) OOM: Sin memoria en el backend Mac Metal. Intenta establecer la variable de entorno 'PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0'.",
        "invalid_prompt": "Formato de prompt inválido: El JSON del flujo enviado a ComfyUI está malformado. Si es desde API, verifica tu sintaxis JSON.",
        "validation_error": "Error de validación en {0}: {1}. Verifica las conexiones de entrada y asegúrate de que se cumplan los requisitos del nodo.",
        "tensor_nan_inf": "Anomalía de datos: {0} detectado en el tensor. Esto a menudo causa imágenes negras. Verifica la precisión de tu modelo (FP16/FP32), configuración VAE o escala CFG.",
        "meta_tensor": "Datos vacíos: Detectado 'Meta Tensor' que contiene info de forma pero sin datos reales. Esto es normal antes de la ejecución del modelo. Si persiste durante la ejecución, verifica los nodos anteriores.",
        "missing_input": "Entrada faltante: La entrada requerida '{0}' no está proporcionada. Verifica si la salida del nodo anterior está conectada correctamente.",
    },
    "ko": {
        "type_mismatch": "타입 불일치: 모델은 {0}(예: fp16)을 예상했지만 {1}(예: float32)을 받았습니다. 'Cast Tensor' 노드를 사용하거나 VAE/모델 로딩 정밀도를 확인하세요.",
        "dimension_mismatch": "차원 불일치: 텐서 {0}(크기 {1})이 텐서 {2}(크기 {3})와 차원 {4}에서 일치하지 않습니다. 잠재 공간 차원 또는 이미지 크기를 확인하세요. 서로 다른 해상도를 혼합하고 있나요?",
        "oom": "OOM(메모리 부족): GPU VRAM이 가득 찼습니다. 시도해보세요: 1. 배치 크기 줄이기 2. '--lowvram' 플래그 사용 3. 다른 GPU 앱 닫기.",
        "matrix_mult": "행렬 곱셈 오류: 이는 일반적으로 모델 아키텍처가 가중치와 일치하지 않을 때 발생합니다(예: SD1.5 vs SDXL). 체크포인트가 LoRA/ControlNet과 일치하는지 확인하세요.",
        "device_type": "디바이스/타입 오류: 입력은 {0}이지만 가중치는 {1}입니다. 모든 것이 동일한 디바이스(GPU/CPU)와 동일한 정밀도에 있는지 확인하세요.",
        "missing_module": "종속성 누락: Python 모듈 '{0}'이(가) 누락되었습니다. ComfyUI Python 환경에서 'pip install {0}'을(를) 실행하세요.",
        "assertion": "어설션 실패: {0}. 이는 일반적으로 입력 데이터가 노드의 기대를 충족하지 못함을 나타냅니다. 업스트림 노드의 출력 형식을 확인하세요.",
        "key_error": "키 오류: 키 '{0}'을(를) 찾을 수 없습니다. 이는 호환되지 않는 모델 구성 또는 잘못된 워크플로우 JSON 때문일 수 있습니다.",
        "attribute_error": "속성 오류: 타입 '{0}'에 속성 '{1}'이(가) 없습니다. 이는 사용자 정의 노드의 버전 불일치 또는 잘못된 모델 형식 때문일 수 있습니다.",
        "shape_mismatch": "형상 불일치: {0}. 입력 이미지 치수가 모델의 기대와 일치하는지 확인하세요.",
        "file_not_found": "파일을 찾을 수 없음: '{0}'. 경로가 올바른지 확인하고 모델 또는 LoRA가 다운로드되었는지 확인하세요.",
        "torch_oom": "PyTorch 메모리 부족! 이것은 새로운 CUDA OOM 오류 형식입니다. 제안사항: 1. 배치 크기 줄이기 2. --lowvram 사용 3. 다른 GPU 프로그램 닫기.",
        "autograd": "PyTorch Autograd 오류가 발생했습니다. 학습 중이라면 손실 함수를 확인하세요. 추론 중이라면 이 오류는 발생하지 않아야 합니다.",
        "safetensors_error": "SafeTensors 오류: 모델 로드 실패. 파일이 손상되었을 수 있습니다(불완전한 다운로드). 모델을 삭제하고 다시 다운로드하세요.",
        "cudnn_error": "CUDNN 실행 실패: GPU 또는 드라이버가 특정 작업에 문제가 있을 수 있습니다. '--force-fp32'로 ComfyUI를 실행하거나 NVIDIA 드라이버를 업데이트하세요.",
        "missing_insightface": "InsightFace 누락: IPAdapter 또는 Reactor 노드에는 'insightface'가 필요합니다. ComfyUI-Manager 가이드를 따라 미리 빌드된 휠을 설치하세요.",
        "model_vae_mismatch": "모델/VAE 불일치: 일치하지 않는 구성이 감지되었습니다(예: SD1.5 모델과 함께 SDXL VAE 사용). VAE 또는 체크포인트를 교체하세요.",
        "mps_oom": "MPS (Mac) OOM: Mac Metal 백엔드에서 메모리 부족. 환경 변수 'PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0'을 설정해보세요.",
        "invalid_prompt": "잘못된 프롬프트 형식: ComfyUI에 전송된 워크플로우 JSON이 잘못되었습니다. API에서 온 것이라면 JSON 구문을 확인하세요.",
        "validation_error": "{0} 검증 오류: {1}. 입력 연결을 확인하고 노드 요구 사항이 충족되는지 확인하세요.",
        "tensor_nan_inf": "데이터 이상: 텐서에서 {0}이(가) 감지되었습니다. 이는 종종 검은색 이미지를 유발합니다. 모델 정밀도(FP16/FP32), VAE 구성 또는 CFG 스케일을 확인하세요.",
        "meta_tensor": "빈 데이터: 형상 정보는 포함하지만 실제 데이터는 없는 'Meta Tensor'가 감지되었습니다. 이는 모델 실행 전에는 정상입니다. 실행 중에 지속되면 업스트림 노드를 확인하세요.",
        "missing_input": "입력 누락: 필수 입력 '{0}'이(가) 제공되지 않았습니다. 업스트림 노드의 출력이 올바르게 연결되어 있는지 확인하세요.",
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


def get_ui_text(key: str, lang: Optional[str] = None) -> str:
    """
    Get localized UI text by key.

    Args:
        key: The UI text key (from UI_TEXT values)
        lang: Optional language override (defaults to current language)

    Returns:
        Localized UI text, or English fallback if key not found.
    """
    target_lang = lang if lang else _current_language
    lang_dict = UI_TEXT.get(target_lang, UI_TEXT["en"])
    text = lang_dict.get(key)

    if text is None:
        # Fallback to English
        text = UI_TEXT["en"].get(key, f"[Missing: {key}]")

    return text
