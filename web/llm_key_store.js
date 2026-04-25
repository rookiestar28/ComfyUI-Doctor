import { app } from "../../../scripts/app.js";
import { getDoctorSetting, setDoctorSetting } from "./comfyui_frontend_compat.js";

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
        const legacy = getDoctorSetting("Doctor.LLM.ApiKey", "", app);
        if (!legacy || !String(legacy).trim()) {
            return false;
        }

        // One-time import to runtime memory, then wipe persisted frontend key.
        runtimeApiKey = String(legacy).trim();
        setDoctorSetting("Doctor.LLM.ApiKey", "", app);
        legacyMigrated = true;
        console.warn("[ComfyUI-Doctor] Migrated legacy persisted API key to session memory and cleared stored value.");
        return true;
    } catch (error) {
        console.warn("[ComfyUI-Doctor] Legacy API key migration failed:", error);
        return false;
    }
}
