import { readFile } from "node:fs/promises";
import path from "node:path";
import { describe, expect, test } from "vitest";

// The same vectors drive tests/test_node_identity_vectors.py against the Python validator.
const VECTORS = JSON.parse(
    await readFile(path.resolve(process.cwd(), "tests/fixtures/node_identity_vectors.json"), "utf8"),
).vectors;

async function loadCompatibilityModule() {
    const modulePath = path.resolve(process.cwd(), "web/comfyui_frontend_compat.js");
    const source = await readFile(modulePath, "utf8");
    const isolatedSource = source.replace(
        /^import \{ app \} from "\.\.\/\.\.\/\.\.\/scripts\/app\.js";\r?\n/u,
        "const app = {};\n",
    );
    return import(`data:text/javascript;base64,${Buffer.from(isolatedSource, "utf8").toString("base64")}`);
}

function build(vector) {
    switch (vector.kind) {
        case "null": return null;
        case "list": return [];
        case "object": return {};
        default: return "repeat" in vector ? vector.repeat.repeat(vector.count) : vector.value;
    }
}

describe("shared node-id vectors", () => {
    test("the fixture covers both outcomes and every value kind", () => {
        expect(new Set(VECTORS.map((vector) => vector.kind))).toEqual(
            new Set(["int", "str", "null", "bool", "float", "list", "object"]),
        );
        expect(VECTORS.some((vector) => vector.accept)).toBe(true);
        expect(VECTORS.some((vector) => !vector.accept)).toBe(true);
        expect(new Set(VECTORS.map((vector) => vector.name)).size).toBe(VECTORS.length);
    });

    test.each(VECTORS.map((vector) => [vector.name, vector]))(
        "the frontend validator matches the vector: %s",
        async (_name, vector) => {
            const { getComfyNodeFromGraph } = await loadCompatibilityModule();
            const value = build(vector);
            // The only public way to the identity rule is a lookup: a node whose own id is the value is
            // found exactly when the value is a valid id.
            const node = { id: value };
            const graph = { nodes: [node] };

            const found = getComfyNodeFromGraph(graph, value);

            expect(found).toBe(vector.accept ? node : null);
        },
    );
});
