import { app } from "../../../scripts/app.js";

export const DOCTOR_DEFAULTS = {
    LANGUAGE: "en",
    POLL_INTERVAL: 2000,
    AUTO_OPEN_ON_ERROR: true,
    ENABLE_NOTIFICATIONS: true,
    LLM_PROVIDER: "openai",
    LLM_BASE_URL: "https://api.openai.com/v1",
    LLM_MODEL: "",
    PRIVACY_MODE: "basic",
    ENABLED: true,
    ERROR_BOUNDARIES: true,
};

export const SUPPORTED_LANGUAGES = [
    { value: "en", text: "English" },
    { value: "zh_TW", text: "繁體中文" },
    { value: "zh_CN", text: "简体中文" },
    { value: "ja", text: "日本語" },
    { value: "de", text: "Deutsch" },
    { value: "fr", text: "Français" },
    { value: "it", text: "Italiano" },
    { value: "es", text: "Español" },
    { value: "ko", text: "한국어" },
];

export const DOCTOR_EXTENSION_SETTINGS = [
    {
        id: "Doctor.General.Enable",
        category: ["Doctor", "General", "Enable"],
        name: "Enable Doctor (requires restart)",
        type: "boolean",
        defaultValue: DOCTOR_DEFAULTS.ENABLED,
        onChange: (newVal, oldVal) => {
            console.log(`[ComfyUI-Doctor] Enable changed: ${oldVal} -> ${newVal}`);
        },
    },
    {
        id: "Doctor.General.ErrorBoundaries",
        category: ["Doctor", "General", "ErrorBoundaries"],
        name: "Enable Error Boundaries (requires restart)",
        type: "boolean",
        defaultValue: DOCTOR_DEFAULTS.ERROR_BOUNDARIES,
        onChange: (newVal, oldVal) => {
            console.log(`[ComfyUI-Doctor] ErrorBoundaries changed: ${oldVal} -> ${newVal}`);
        },
    },
    {
        id: "Doctor.Info",
        category: ["Doctor", "General", "Info"],
        name: "ℹ️ Configure Doctor settings in the sidebar (left panel)",
        type: "text",
        defaultValue: "",
        attrs: { readonly: true, disabled: true },
    },
    {
        id: "Doctor.General.Language",
        category: ["Doctor", "General", "Language"],
        name: "Doctor: Language",
        type: "combo",
        options: SUPPORTED_LANGUAGES,
        defaultValue: DOCTOR_DEFAULTS.LANGUAGE,
    },
    {
        id: "Doctor.Privacy.Mode",
        category: ["Doctor", "Privacy", "Mode"],
        name: "Doctor: Privacy Mode",
        type: "combo",
        options: [
            { text: "None (Private)", value: "none" },
            { text: "Basic (Anonymized)", value: "basic" },
            { text: "Strict (No Sensitive Data)", value: "strict" },
        ],
        defaultValue: DOCTOR_DEFAULTS.PRIVACY_MODE,
    },
    {
        id: "Doctor.Behavior.PollInterval",
        category: ["Doctor", "Behavior", "PollInterval"],
        name: "Doctor: Error Poll Interval (ms)",
        type: "number",
        defaultValue: DOCTOR_DEFAULTS.POLL_INTERVAL,
        attrs: { min: 500, max: 10000, step: 100 },
    },
    {
        id: "Doctor.Behavior.AutoOpenOnError",
        category: ["Doctor", "Behavior", "AutoOpenOnError"],
        name: "Doctor: Auto-open sidebar on error",
        type: "boolean",
        defaultValue: DOCTOR_DEFAULTS.AUTO_OPEN_ON_ERROR,
    },
    {
        id: "Doctor.Behavior.EnableNotifications",
        category: ["Doctor", "Behavior", "EnableNotifications"],
        name: "Doctor: Enable Browser Notifications",
        type: "boolean",
        defaultValue: DOCTOR_DEFAULTS.ENABLE_NOTIFICATIONS,
    },
    {
        id: "Doctor.LLM.Provider",
        category: ["Doctor", "LLM", "Provider"],
        name: "Doctor: AI Provider",
        type: "text",
        defaultValue: DOCTOR_DEFAULTS.LLM_PROVIDER,
    },
    {
        id: "Doctor.LLM.BaseUrl",
        category: ["Doctor", "LLM", "BaseUrl"],
        name: "Doctor: LLM Base URL",
        type: "text",
        defaultValue: DOCTOR_DEFAULTS.LLM_BASE_URL,
    },
    {
        id: "Doctor.LLM.Model",
        category: ["Doctor", "LLM", "Model"],
        name: "Doctor: Model Name",
        type: "text",
        defaultValue: DOCTOR_DEFAULTS.LLM_MODEL,
    },
];

const DOCTOR_SETTING_DEFAULT_MAP = new Map(
    DOCTOR_EXTENSION_SETTINGS.map((setting) => [setting.id, setting.defaultValue])
);

function getModernSettingsApi(appInstance = app) {
    return appInstance?.extensionManager?.setting || null;
}

function getLegacySettingsApi(appInstance = app) {
    return appInstance?.ui?.settings || null;
}

export function getDoctorSetting(id, fallback, appInstance = app) {
    const modernSettings = getModernSettingsApi(appInstance);
    const legacySettings = getLegacySettingsApi(appInstance);
    const resolvedFallback = fallback ?? DOCTOR_SETTING_DEFAULT_MAP.get(id);

    if (modernSettings?.get) {
        try {
            const value = modernSettings.get(id);
            return value === undefined ? resolvedFallback : value;
        } catch (error) {
            console.warn(`[ComfyUI-Doctor] Modern settings get failed for ${id}; falling back`, error);
        }
    }

    if (legacySettings?.getSettingValue) {
        const value = legacySettings.getSettingValue(id, resolvedFallback);
        return value === undefined ? resolvedFallback : value;
    }

    return resolvedFallback;
}

export function setDoctorSetting(id, value, appInstance = app) {
    const modernSettings = getModernSettingsApi(appInstance);
    const legacySettings = getLegacySettingsApi(appInstance);

    if (modernSettings?.set) {
        try {
            const result = modernSettings.set(id, value);
            if (result && typeof result.catch === "function") {
                result.catch((error) => {
                    console.warn(`[ComfyUI-Doctor] Modern settings set failed for ${id}`, error);
                });
            }
            return value;
        } catch (error) {
            console.warn(`[ComfyUI-Doctor] Modern settings set failed for ${id}; falling back`, error);
        }
    }

    if (legacySettings?.setSettingValue) {
        legacySettings.setSettingValue(id, value);
    }
    return value;
}

export function getDoctorBooleanSetting(id, fallback, appInstance = app) {
    const resolvedFallback = fallback ?? DOCTOR_SETTING_DEFAULT_MAP.get(id) ?? false;
    const value = getDoctorSetting(id, resolvedFallback, appInstance);
    if (value === null || value === undefined) {
        return resolvedFallback;
    }
    return Boolean(value) && value !== "false" && value !== "0";
}

export function getDoctorRuntimeSettings(appInstance = app) {
    return {
        language: getDoctorSetting("Doctor.General.Language", DOCTOR_DEFAULTS.LANGUAGE, appInstance),
        pollInterval: getDoctorSetting("Doctor.Behavior.PollInterval", DOCTOR_DEFAULTS.POLL_INTERVAL, appInstance),
        autoOpenOnError: getDoctorBooleanSetting("Doctor.Behavior.AutoOpenOnError", DOCTOR_DEFAULTS.AUTO_OPEN_ON_ERROR, appInstance),
        enableNotifications: getDoctorBooleanSetting("Doctor.Behavior.EnableNotifications", DOCTOR_DEFAULTS.ENABLE_NOTIFICATIONS, appInstance),
        provider: getDoctorSetting("Doctor.LLM.Provider", DOCTOR_DEFAULTS.LLM_PROVIDER, appInstance),
        baseUrl: getDoctorSetting("Doctor.LLM.BaseUrl", DOCTOR_DEFAULTS.LLM_BASE_URL, appInstance),
        model: getDoctorSetting("Doctor.LLM.Model", DOCTOR_DEFAULTS.LLM_MODEL, appInstance),
        privacyMode: getDoctorSetting("Doctor.Privacy.Mode", DOCTOR_DEFAULTS.PRIVACY_MODE, appInstance),
    };
}

export function isDoctorEnabled(appInstance = app) {
    return getDoctorBooleanSetting("Doctor.General.Enable", DOCTOR_DEFAULTS.ENABLED, appInstance);
}


export function ensureDoctorSettingsRegistered(appInstance = app) {
    const settings = getLegacySettingsApi(appInstance);
    if (!settings?.addSetting) return;

    let settingsLookup = null;
    try {
        settingsLookup = settings.settingsLookup || settings.settingsParamLookup || settings.settingsById || null;
    } catch (_) {
        settingsLookup = null;
    }

    const missingSettings = DOCTOR_EXTENSION_SETTINGS.filter((setting) => !settingsLookup?.[setting.id]);
    if (!missingSettings.length) return;

    // CRITICAL: fallback only when declarative extension settings were not registered.
    missingSettings.forEach((setting) => settings.addSetting(setting));
}

export function isDoctorErrorBoundariesEnabled(appInstance = app) {
    return getDoctorBooleanSetting(
        "Doctor.General.ErrorBoundaries",
        DOCTOR_DEFAULTS.ERROR_BOUNDARIES,
        appInstance,
    );
}

// IMPORTANT: keep legacy app.graph fallback isolated in this adapter only.
export function getComfyRootGraph(appInstance = app) {
    if (!appInstance) return null;

    try {
        if (appInstance.isGraphReady === true) {
            return appInstance.rootGraph || null;
        }
    } catch (_) {
        // Fall through to guarded legacy checks below.
    }

    try {
        if (appInstance.rootGraph) {
            return appInstance.rootGraph;
        }
    } catch (_) {
        // Ignore rootGraph getter issues on older/early-init builds.
    }

    try {
        return appInstance.graph || null;
    } catch (_) {
        return null;
    }
}

export function getComfyNodeById(nodeId, appInstance = app) {
    const graph = getComfyRootGraph(appInstance);
    if (!graph || nodeId === null || nodeId === undefined || nodeId === "") {
        return null;
    }

    const rawId = String(nodeId);
    const numericId = Number(rawId);
    return graph.getNodeById?.(Number.isNaN(numericId) ? rawId : numericId)
        || graph.getNodeById?.(rawId)
        || graph._nodes?.find?.((candidate) => String(candidate?.id) === rawId)
        || null;
}

export function markComfyGraphDirty(appInstance = app, foreground = true, background = true) {
    const graph = getComfyRootGraph(appInstance);
    if (typeof graph?.setDirtyCanvas === "function") {
        graph.setDirtyCanvas(foreground, background);
        return;
    }

    if (typeof appInstance?.canvas?.setDirty === "function") {
        appInstance.canvas.setDirty(foreground, background);
    }
}

export function destroyDoctorSidebarMount(doctorUI) {
    if (typeof doctorUI?.sidebarCleanup === "function") {
        try {
            doctorUI.sidebarCleanup();
        } catch (error) {
            console.warn("[ComfyUI-Doctor] Sidebar cleanup failed:", error);
        }
    }
    if (doctorUI) {
        doctorUI.sidebarCleanup = null;
        doctorUI.sidebarTabContainer = null;
        doctorUI.tabManager = null;
    }
}
