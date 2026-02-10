import { app } from "../../../scripts/app.js";

let runtimeApiKey = "";
let legacyMigrated = false;

export function setRuntimeApiKey(value) {
    runtimeApiKey = (value || "").trim();
}

export function getRuntimeApiKey() {
    return runtimeApiKey;
}

export function isLegacyApiKeyMigrated() {
    return legacyMigrated;
}

export function migrateLegacyApiKeyFromSettings() {
    try {
        const settings = app?.ui?.settings;
        if (!settings) return false;

        const legacy = settings.getSettingValue("Doctor.LLM.ApiKey", "");
        if (!legacy || !String(legacy).trim()) {
            return false;
        }

        // One-time import to runtime memory, then wipe persisted frontend key.
        runtimeApiKey = String(legacy).trim();
        settings.setSettingValue("Doctor.LLM.ApiKey", "");
        legacyMigrated = true;
        console.warn("[ComfyUI-Doctor] Migrated legacy persisted API key to session memory and cleared stored value.");
        return true;
    } catch (error) {
        console.warn("[ComfyUI-Doctor] Legacy API key migration failed:", error);
        return false;
    }
}

