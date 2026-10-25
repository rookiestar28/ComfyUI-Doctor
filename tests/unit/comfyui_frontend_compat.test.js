import { readFile } from "node:fs/promises";
import path from "node:path";
import { describe, expect, test, vi } from "vitest";
const FRONTEND_LANES = [
    {
        id: "desktop-0.9.4",
        version: "1.43.18",
        settingChangeTelemetry: false,
        asyncSettingOnChange: false,
    },
    {
        id: "core-pin-1.57.1",
        version: "1.57.1",
        settingChangeTelemetry: true,
        asyncSettingOnChange: true,
    },
    {
        id: "standalone-1.59.1",
        version: "1.59.1",
        settingChangeTelemetry: true,
        asyncSettingOnChange: true,
    },
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

async function invokeWithLaneSettingContract(lane, handler) {
    if (!lane.asyncSettingOnChange) return handler();
    try {
        return await handler();
    } catch {
        return undefined;
    }
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

describe("Exact opaque node identity", () => {
    const opaqueId = "insert:synthetic-operation:root:node:9";
    const appFor = (root) => ({ graph: root, rootGraph: root, rootGraphOrUndefined: root });

    test("raw colon IDs and leading-zero IDs never alias their tail or numeric form", async () => {
        const compat = await loadCompatibilityModule();
        const raw = { id: opaqueId };
        const zero = { id: "09" };
        const numeric = { id: 9 };
        const root = createGraph([raw, numeric, zero]);
        const instance = appFor(root);
        expect(compat.resolveComfyFixTargetNode(opaqueId, instance)).toBe(raw);
        expect(compat.resolveComfyFixTargetNode("09", instance)).toBe(zero);
        expect(compat.getComfyNodeById("09", instance)).toBe(zero);
        expect(compat.resolveComfyFixTargetNode("9", instance)).toBe(numeric);
        expect(compat.resolveComfyFixTargetNode("other:node:9", instance)).toBeNull();
    });

    test("nested paths consume whole colon-bearing host and leaf IDs", async () => {
        const compat = await loadCompatibilityModule();
        const leaf = { id: opaqueId };
        const inner = createGraph([leaf]);
        const host = { id: "host:synthetic", subgraph: inner, isSubgraphNode: () => true };
        const root = createGraph([host]);
        expect(compat.resolveComfyFixTargetNode(`host:synthetic:${opaqueId}`, appFor(root))).toBe(leaf);
    });

    test("raw-versus-path ambiguity and duplicate live identities fail closed", async () => {
        const compat = await loadCompatibilityModule();
        const leaf = { id: 5 };
        const inner = createGraph([leaf]);
        const host = { id: 12, subgraph: inner, isSubgraphNode: () => true };
        const root = createGraph([host, { id: "12:5" }]);
        expect(compat.resolveComfyFixTargetNode("12:5", appFor(root))).toBeNull();
        const duplicate = createGraph([{ id: 9 }, { id: "9" }]);
        expect(compat.resolveComfyFixTargetNode("9", appFor(duplicate))).toBeNull();
    });

    test("an ineligible nested host still makes a raw fix target ambiguous", async () => {
        const compat = await loadCompatibilityModule();
        const nestedHost = { id: 5, subgraph: createGraph([]), isSubgraphNode: () => true };
        const host = { id: 12, subgraph: createGraph([nestedHost]), isSubgraphNode: () => true };
        const raw = { id: "12:5" };
        const root = createGraph([host, raw]);
        expect(compat.resolveComfyFixTargetNode("12:5", appFor(root))).toBeNull();
        expect(compat.resolveComfyNodeTarget("12:5", appFor(root))).toBeNull();
    });

    test("authoritative membership defeats stale or coercing host lookup caches", async () => {
        const compat = await loadCompatibilityModule();
        const live = { id: 9 };
        const stale = { id: opaqueId };
        const root = createGraph([live]);
        root.getNodeById = () => stale;
        expect(compat.resolveComfyFixTargetNode(opaqueId, appFor(root))).toBeNull();
        const legacy = { getNodeById: () => live };
        expect(compat.resolveComfyFixTargetNode("09", appFor(legacy))).toBeNull();
    });

    test("malformed scalars are rejected without invoking user coercion", async () => {
        const compat = await loadCompatibilityModule();
        const instance = appFor(createGraph([{ id: 9 }]));
        const hostile = { toString() { throw new Error("coercion must not run"); } };
        for (const value of [hostile, [], true, null, NaN, Infinity, -1, 9.5, " 9", "9\n", "x".repeat(1025)]) {
            expect(compat.resolveComfyFixTargetNode(value, instance)).toBeNull();
        }
    });

    test("resolution depth and candidate budgets fail the entire lookup closed", async () => {
        const compat = await loadCompatibilityModule();
        const makeChain = (count) => {
            let root = createGraph([{ id: "leaf" }]);
            const parts = ["leaf"];
            for (let index = 1; index < count; index++) {
                parts.unshift(`host${index}`);
                root = createGraph([{ id: `host${index}`, subgraph: root, isSubgraphNode: () => true }]);
            }
            return { root, text: parts.join(":") };
        };
        const allowed = makeChain(16);
        expect(compat.resolveComfyFixTargetNode(allowed.text, appFor(allowed.root))?.id).toBe("leaf");
        const overflow = makeChain(17);
        expect(compat.resolveComfyFixTargetNode(overflow.text, appFor(overflow.root))).toBeNull();
        const manyPrefixes = "a:".repeat(257) + "leaf";
        const root = createGraph([{ id: manyPrefixes }]);
        expect(compat.resolveComfyFixTargetNode(manyPrefixes, appFor(root))).toBeNull();
    });
});

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

    test("core 1.57.1 and exact standalone 1.59.1 support asynchronous settings", () => {
        expect(
            FRONTEND_LANES
                .filter((lane) => lane.asyncSettingOnChange)
                .map((lane) => lane.id),
        ).toEqual(["core-pin-1.57.1", "standalone-1.59.1"]);
    });

    test.each(FRONTEND_LANES)(
        "$id frontend $version accepts Doctor's synchronous callbacks directly and when awaited",
        async () => {
            const { DOCTOR_EXTENSION_SETTINGS } = await loadCompatibilityModule();
            const callbacks = DOCTOR_EXTENSION_SETTINGS
                .map((setting) => setting.onChange)
                .filter((callback) => typeof callback === "function");
            const logSpy = vi.spyOn(console, "log").mockImplementation(() => {});

            try {
                expect(callbacks).toHaveLength(2);
                for (const callback of callbacks) {
                    expect(callback(true, false)).toBeUndefined();
                    await expect(
                        Promise.resolve(callback(false, true)),
                    ).resolves.toBeUndefined();
                }
            } finally {
                logSpy.mockRestore();
            }
        },
    );

    test.each(FRONTEND_LANES)(
        "$id frontend $version applies callback failure containment only where sourced",
        async (lane) => {
            const syncFailure = () => {
                throw new Error("synthetic synchronous callback failure");
            };
            const asyncFailure = () => Promise.reject(
                new Error("synthetic asynchronous callback failure"),
            );

            if (lane.asyncSettingOnChange) {
                await expect(
                    invokeWithLaneSettingContract(lane, syncFailure),
                ).resolves.toBeUndefined();
                await expect(
                    invokeWithLaneSettingContract(lane, asyncFailure),
                ).resolves.toBeUndefined();
            } else {
                await expect(
                    invokeWithLaneSettingContract(lane, syncFailure),
                ).rejects.toThrow("synthetic synchronous callback failure");
                await expect(
                    invokeWithLaneSettingContract(lane, asyncFailure),
                ).rejects.toThrow("synthetic asynchronous callback failure");
            }
        },
    );
});

describe("public validation boundary surfacing", () => {
    test.each([null, undefined, "throwing getter"])(
        "retains loop validation metadata when root is %s",
        async (root) => {
            const { surfaceComfyValidationNodeErrors } = await loadCompatibilityModule();
            const app = { get rootGraph() {
                if (root === "throwing getter") throw new Error("not ready");
                return root;
            } };
            const raw = { "12:5": { errors: [{
                type: "custom_validation_failed",
                message: "Synthetic loop boundary error",
                extra_info: {
                    input_name: "loop boundary", loop_error_type: "invalid_boundary",
                    node_ids: ["12:5"], output_ids: ["9"], future_field: true,
                },
            }], dependent_outputs: ["9"] } };
            const original = structuredClone(raw);
            expect(surfaceComfyValidationNodeErrors(raw, app)).toEqual(original);
            expect(raw).toEqual(original);
        },
    );
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

    test("keeps partner policy validation errors at node level with raw context intact", async () => {
        const { surfaceComfyValidationNodeErrors } =
            await loadCompatibilityModule();
        const leaf = {
            id: 5,
            type: "SyntheticPartnerNode",
            inputs: [{ name: "policy_target", link: 7 }],
        };
        const subgraph = createGraph([leaf], {
            7: {
                resolve: () => ({ subgraphInput: { name: "outer_target" } }),
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
            "12:5": {
                class_type: "SyntheticPartnerNode",
                dependent_outputs: [],
                errors: [{
                    type: "PARTNER_NODE_DISABLED",
                    message: "Workspace policy disabled this node.",
                    details: "Select an allowed alternative.",
                    extra_info: {
                        input_name: "policy_target",
                        provider: "synthetic-partner",
                    },
                }],
            },
        };
        const original = structuredClone(raw);

        const surfaced = surfaceComfyValidationNodeErrors(raw, { rootGraph });

        expect(surfaced).toEqual(original);
        expect(raw).toEqual(original);
        expect(Object.keys(surfaced)).toEqual(["12:5"]);
        expect(surfaced["12:5"].errors[0]).toMatchObject({
            type: "PARTNER_NODE_DISABLED",
            message: "Workspace policy disabled this node.",
            details: "Select an allowed alternative.",
            extra_info: {
                input_name: "policy_target",
                provider: "synthetic-partner",
            },
        });
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

    test("runtime compatibility remains observational and does not own host queue or authentication", async () => {
        const files = [
            "web/comfyui_frontend_compat.js",
            "web/doctor_ui.js",
        ];
        const sources = await Promise.all(
            files.map((file) => readFile(path.resolve(process.cwd(), file), "utf8")),
        );

        for (const source of sources) {
            expect(source).not.toMatch(
                /queuePrompt|partnerRunGate|useAuthStore|\/prompt\b/iu,
            );
        }
    });
});

describe("public setting setter promise containment", () => {
    test.each(FRONTEND_LANES)("$id contains a rejected setter without retrying a write", async () => {
        const { setDoctorSetting } = await loadCompatibilityModule();
        const failure = new Error("synthetic setter rejection");
        const legacy = vi.fn();
        const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
        try {
            const set = vi.fn(() => Promise.reject(failure));
            expect(setDoctorSetting("Doctor.General.Enable", true, {
                extensionManager: { setting: { set } },
                ui: { settings: { setSettingValue: legacy } },
            })).toBe(true);
            await Promise.resolve();
            expect(set).toHaveBeenCalledExactlyOnceWith("Doctor.General.Enable", true);
            expect(legacy).not.toHaveBeenCalled();
            expect(warn).toHaveBeenCalledWith(expect.stringContaining("Modern settings set failed"), failure);
        } finally {
            warn.mockRestore();
        }
    });
});
