import { readFile } from "node:fs/promises";
import path from "node:path";
import { describe, expect, test } from "vitest";

const FRONTEND_LANES = [
    { id: "desktop-0.9.4", version: "1.43.18", settingChangeTelemetry: false },
    { id: "core-pin-1.47.10", version: "1.47.10", settingChangeTelemetry: true },
    { id: "standalone-current", version: "1.49.1+", settingChangeTelemetry: true },
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

function createGraph(nodes = [], links = {}) {
    const graph = {
        isRootGraph: false,
        _nodes: nodes,
        getNodeById(id) {
            return this._nodes.find((node) => String(node.id) === String(id)) || null;
        },
        getLink(id) {
            return links[id] || null;
        },
    };
    nodes.forEach((node) => {
        node.graph = graph;
    });
    return graph;
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

describe("public validation boundary surfacing", () => {
    test("prefers public raw state and falls back when its getter throws", async () => {
        const { getComfyValidationNodeErrors } =
            await loadCompatibilityModule();
        const modern = { modern: { errors: [] } };
        const legacy = { legacy: { errors: [] } };

        expect(getComfyValidationNodeErrors({
            extensionManager: { lastNodeErrors: modern },
            lastNodeErrors: legacy,
        })).toBe(modern);

        const extensionManager = {};
        Object.defineProperty(extensionManager, "lastNodeErrors", {
            get() {
                throw new Error("early-init getter");
            },
        });
        expect(getComfyValidationNodeErrors({
            extensionManager,
            lastNodeErrors: legacy,
        })).toBe(legacy);
    });

    test("lifts a two-level boundary error to the outer host with source provenance", async () => {
        const { surfaceComfyValidationNodeErrors } =
            await loadCompatibilityModule();
        const leaf = {
            id: 3,
            type: "LeafNode",
            inputs: [{ name: "seed_input", link: "leaf-boundary" }],
        };
        const innerGraph = createGraph([leaf], {
            "leaf-boundary": {
                resolve: () => ({ subgraphInput: { name: "inner_seed" } }),
            },
        });
        const middleHost = {
            id: 2,
            title: "Middle Host",
            type: "Subgraph",
            subgraph: innerGraph,
            isSubgraphNode: () => true,
            inputs: [{ name: "inner_seed", link: "middle-boundary" }],
        };
        const outerGraph = createGraph([middleHost], {
            "middle-boundary": {
                resolve: () => ({ subgraphInput: { name: "outer_seed" } }),
            },
        });
        const outerHost = {
            id: 1,
            title: "Outer Host",
            type: "Subgraph",
            subgraph: outerGraph,
            isSubgraphNode: () => true,
        };
        const rootGraph = createGraph([outerHost]);
        rootGraph.isRootGraph = true;
        outerHost.graph = rootGraph;
        const raw = {
            "1:2:3": {
                class_type: "LeafNode",
                dependent_outputs: ["9"],
                errors: [{
                    type: "required_input_missing",
                    message: "Required input is missing",
                    extra_info: { input_name: "seed_input", retained: "yes" },
                }],
            },
        };
        const original = structuredClone(raw);

        const surfaced = surfaceComfyValidationNodeErrors(raw, { rootGraph });

        expect(raw).toEqual(original);
        expect(Object.keys(surfaced)).toEqual(["1"]);
        expect(surfaced["1"]).toMatchObject({
            class_type: "Outer Host",
            dependent_outputs: [],
        });
        expect(surfaced["1"].errors[0].extra_info).toEqual({
            input_name: "outer_seed",
            retained: "yes",
            source_execution_id: "1:2:3",
            source_input_name: "seed_input",
        });
    });

    test("splits input errors while node-level and unknown errors remain on source", async () => {
        const { surfaceComfyValidationNodeErrors } =
            await loadCompatibilityModule();
        const leaf = {
            id: 5,
            type: "LeafNode",
            inputs: [{ name: "seed_input", link: 7 }],
        };
        const subgraph = createGraph([leaf], {
            7: {
                resolve: () => ({ subgraphInput: { name: "seed" } }),
            },
        });
        const host = {
            id: 12,
            title: "Visible Host",
            type: "Subgraph",
            subgraph,
            isSubgraphNode: () => true,
        };
        const rootGraph = createGraph([host]);
        rootGraph.isRootGraph = true;
        host.graph = rootGraph;
        const raw = {
            "12": {
                class_type: "ExistingHostClass",
                dependent_outputs: ["existing"],
                errors: [{
                    type: "value_smaller_than_min",
                    extra_info: { input_name: "other" },
                }],
            },
            "12:5": {
                class_type: "LeafNode",
                dependent_outputs: [],
                errors: [
                    {
                        type: "required_input_missing",
                        extra_info: { input_name: "seed_input" },
                    },
                    {
                        type: "exception_during_validation",
                        extra_info: { input_name: "seed_input" },
                    },
                    {
                        type: "future_backend_validation_type",
                        extra_info: { input_name: "seed_input" },
                    },
                    {
                        type: "custom_validation_failed",
                        message: "Invalid image file",
                        extra_info: { input_name: "seed_input" },
                    },
                    {
                        type: "required_input_missing",
                        extra_info: {},
                    },
                ],
            },
        };

        const surfaced = surfaceComfyValidationNodeErrors(raw, { rootGraph });

        expect(surfaced["12"]).toMatchObject({
            class_type: "ExistingHostClass",
            dependent_outputs: ["existing"],
        });
        expect(surfaced["12"].errors.map((error) => error.type)).toEqual([
            "value_smaller_than_min",
            "required_input_missing",
        ]);
        expect(surfaced["12:5"].errors.map((error) => error.type)).toEqual([
            "exception_during_validation",
            "future_backend_validation_type",
            "custom_validation_failed",
            "required_input_missing",
        ]);
    });

    test("fails open for unproven topology and preserves empty entries", async () => {
        const { surfaceComfyValidationNodeErrors } =
            await loadCompatibilityModule();
        const leaf = {
            id: 5,
            inputs: [{ name: "seed_input", link: 9 }],
        };
        const subgraph = createGraph([leaf], {
            9: { resolve: () => ({}) },
        });
        const host = {
            id: 12,
            title: "Visible Host",
            subgraph,
            isSubgraphNode: () => true,
        };
        const rootGraph = createGraph([host]);
        rootGraph.isRootGraph = true;
        host.graph = rootGraph;
        const raw = {
            empty: {
                class_type: "EmptyNode",
                dependent_outputs: [],
                errors: [],
            },
            "12:5": {
                class_type: "LeafNode",
                dependent_outputs: [],
                errors: [{
                    type: "required_input_missing",
                    extra_info: { input_name: "seed_input" },
                }],
            },
        };
        const original = structuredClone(raw);

        expect(surfaceComfyValidationNodeErrors(raw, { rootGraph })).toEqual(original);
        expect(raw).toEqual(original);
    });

    test("runtime compatibility source does not couple to private frontend stores", async () => {
        const files = [
            "web/comfyui_frontend_compat.js",
            "web/doctor_ui.js",
        ];
        const sources = await Promise.all(
            files.map((file) => readFile(path.resolve(process.cwd(), file), "utf8")),
        );

        for (const source of sources) {
            expect(source).not.toMatch(
                /executionErrorStore|surfacedNodeErrors|missingModelStore|pinia/iu,
            );
        }
    });
});
