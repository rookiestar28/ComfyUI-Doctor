import { readFile } from "node:fs/promises";
import path from "node:path";
import { describe, expect, test } from "vitest";

const FRONTEND_LANES = [
    { id: "desktop-0.9.4", version: "1.43.18", settingChangeTelemetry: false },
    { id: "core-pin-1.45.21", version: "1.45.21", settingChangeTelemetry: false },
    { id: "standalone-current", version: "1.48.3+", settingChangeTelemetry: true },
];

async function loadCompatibilityModule() {
    const modulePath = path.resolve(
        process.cwd(),
        "web/comfyui_frontend_compat.js",
    );
    const source = await readFile(modulePath, "utf8");
    const isolatedSource = source.replace(
        /^import \{ app \} from "\.\.\/\.\.\/\.\.\/scripts\/app\.js";\r?\n/u,
        "const app = {};\n",
    );
    const moduleUrl = `data:text/javascript;base64,${Buffer.from(
        isolatedSource,
        "utf8",
    ).toString("base64")}`;
    return import(moduleUrl);
}

describe("Doctor setting telemetry contract", () => {
    test("every Doctor setting explicitly opts out of host change telemetry", async () => {
        const { DOCTOR_EXTENSION_SETTINGS } = await loadCompatibilityModule();
        const missingOrInvalid = DOCTOR_EXTENSION_SETTINGS
            .filter(
                (setting) =>
                    setting.telemetry?.trackChanges !== false
                    || Object.keys(setting.telemetry).length !== 1,
            )
            .map((setting) => setting.id);

        expect(DOCTOR_EXTENSION_SETTINGS).toHaveLength(11);
        expect(missingOrInvalid).toEqual([]);
    });

    test("setting ids stay unique and the session-only API key is not registered", async () => {
        const { DOCTOR_EXTENSION_SETTINGS } = await loadCompatibilityModule();
        const ids = DOCTOR_EXTENSION_SETTINGS.map((setting) => setting.id);

        expect(new Set(ids).size).toBe(ids.length);
        expect(ids.some((id) => /api.?key/iu.test(id))).toBe(false);
    });

    test("modern settings access and legacy fallback retain their behavior", async () => {
        const { getDoctorSetting, setDoctorSetting } =
            await loadCompatibilityModule();
        const modernCalls = [];
        const legacyCalls = [];
        const modernApp = {
            extensionManager: {
                setting: {
                    get: () => false,
                    set: (id, value) => modernCalls.push([id, value]),
                },
            },
            ui: {
                settings: {
                    getSettingValue: () => true,
                    setSettingValue: (id, value) => legacyCalls.push([id, value]),
                },
            },
        };
        const legacyApp = {
            ui: {
                settings: {
                    getSettingValue: () => false,
                    setSettingValue: (id, value) => legacyCalls.push([id, value]),
                },
            },
        };

        expect(
            getDoctorSetting("Doctor.General.Enable", true, modernApp),
        ).toBe(false);
        setDoctorSetting("Doctor.General.Enable", true, modernApp);
        expect(modernCalls).toEqual([["Doctor.General.Enable", true]]);
        expect(legacyCalls).toEqual([]);

        expect(
            getDoctorSetting("Doctor.General.Enable", true, legacyApp),
        ).toBe(false);
        setDoctorSetting("Doctor.General.Enable", true, legacyApp);
        expect(legacyCalls).toEqual([["Doctor.General.Enable", true]]);
    });

    test.each(FRONTEND_LANES)(
        "$id frontend $version preserves additive metadata and current opt-out semantics",
        async (lane) => {
            const { DOCTOR_EXTENSION_SETTINGS } = await loadCompatibilityModule();
            const registered = new Map();
            const emittedSettingIds = [];

            for (const setting of DOCTOR_EXTENSION_SETTINGS) {
                registered.set(setting.id, { ...setting });
                if (
                    lane.settingChangeTelemetry
                    && setting.telemetry?.trackChanges !== false
                ) {
                    emittedSettingIds.push(setting.id);
                }
            }

            expect(registered.size).toBe(11);
            expect(
                [...registered.values()].every(
                    (setting) => setting.telemetry?.trackChanges === false,
                ),
            ).toBe(true);
            expect(emittedSettingIds).toEqual([]);
        },
    );
});
