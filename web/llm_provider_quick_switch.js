import { app } from "../../../scripts/app.js";
import { doctorContext } from "./doctor_state.js";
import { getDoctorRuntimeSettings, setDoctorSetting } from "./comfyui_frontend_compat.js";

export const LLM_PROVIDER_OPTIONS = [
    { value: "openai", label: "OpenAI", baseUrl: "https://api.openai.com/v1" },
    { value: "anthropic", label: "Anthropic Claude", baseUrl: "https://api.anthropic.com" },
    { value: "deepseek", label: "DeepSeek", baseUrl: "https://api.deepseek.com/v1" },
    { value: "groq", label: "Groq Cloud (LPU)", baseUrl: "https://api.groq.com/openai/v1" },
    { value: "gemini", label: "Google Gemini", baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai" },
    { value: "xai", label: "xAI Grok", baseUrl: "https://api.x.ai/v1" },
    { value: "openrouter", label: "OpenRouter", baseUrl: "https://openrouter.ai/api/v1" },
    { value: "ollama", label: "Ollama (Local)", baseUrl: "http://127.0.0.1:11434" },
    { value: "lmstudio", label: "LMStudio (Local)", baseUrl: "http://localhost:1234/v1" },
    { value: "custom", label: "Custom", baseUrl: "" },
];

export function getProviderOption(provider) {
    return LLM_PROVIDER_OPTIONS.find((option) => option.value === provider) || null;
}

export function resolveProviderBaseUrl(provider, providerDefaults = {}) {
    const fromRuntimeDefaults = providerDefaults?.[provider];
    if (typeof fromRuntimeDefaults === "string") {
        return fromRuntimeDefaults;
    }
    return getProviderOption(provider)?.baseUrl || "";
}

export function getProviderQuickSwitchState(appInstance = app) {
    const settings = getDoctorRuntimeSettings(appInstance);
    const provider = getProviderOption(settings.provider) ? settings.provider : "openai";
    const providerDefaults = appInstance?.Doctor?.providerDefaults || {};
    return {
        provider,
        baseUrl: settings.baseUrl || resolveProviderBaseUrl(provider, providerDefaults),
        options: LLM_PROVIDER_OPTIONS,
    };
}

export function applyProviderQuickSwitch(provider, appInstance = app) {
    const option = getProviderOption(provider);
    if (!option) {
        throw new Error(`Unsupported provider: ${provider}`);
    }

    const providerDefaults = appInstance?.Doctor?.providerDefaults || {};
    const baseUrl = resolveProviderBaseUrl(option.value, providerDefaults);

    setDoctorSetting("Doctor.LLM.Provider", option.value, appInstance);
    setDoctorSetting("Doctor.LLM.BaseUrl", baseUrl, appInstance);
    doctorContext.refreshSettings?.();

    return {
        provider: option.value,
        label: option.label,
        baseUrl,
    };
}
