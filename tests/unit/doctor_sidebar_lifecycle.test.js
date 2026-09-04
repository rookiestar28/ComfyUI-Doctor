import { afterEach, describe, expect, test, vi } from "vitest";

import {
    DOCTOR_SIDEBAR_MIN_WIDTH_PX,
    enforceDoctorSidebarMinWidth,
} from "../../web/doctor_sidebar_layout.js";

function createElement({ className = "", style = {}, width = 0 } = {}) {
    let styleAttribute = Object.entries(style)
        .map(([key, value]) => `${key}:${value}`)
        .join(";");
    return {
        className,
        style: {
            minWidth: style.minWidth ?? "",
            width: style.width ?? "",
            flexBasis: style.flexBasis ?? "",
        },
        closest() {
            return null;
        },
        getBoundingClientRect() {
            return { width };
        },
        hasAttribute(name) {
            return name === "style" && styleAttribute !== null;
        },
        getAttribute(name) {
            return name === "style" ? styleAttribute : null;
        },
        setAttribute(name, value) {
            if (name === "style") styleAttribute = value;
        },
        removeAttribute(name) {
            if (name === "style") styleAttribute = null;
        },
    };
}

describe("Doctor sidebar layout lifecycle", () => {
    afterEach(() => {
        vi.restoreAllMocks();
        vi.unstubAllGlobals();
    });

    test("enforces actual three-layer geometry and restores every captured value", () => {
        const panel = createElement({
            style: { minWidth: "233px", width: "300px", flexBasis: "17px" },
            width: 300,
        });
        const content = createElement({
            style: { minWidth: "211px", width: "300px", flexBasis: "13px" },
            width: 300,
        });
        const mount = createElement({
            className: "host-slot",
            style: { minWidth: "19px", width: "29px", flexBasis: "31px" },
            width: 29,
        });
        mount.closest = (selector) => ({
            ".side-bar-panel": panel,
            ".p-splitterpanel": panel,
            ".sidebar-content-container": content,
        }[selector] ?? null);

        const pendingFrames = new Map();
        vi.stubGlobal("requestAnimationFrame", vi.fn((callback) => {
            pendingFrames.set(1, callback);
            return 1;
        }));
        vi.stubGlobal("cancelAnimationFrame", vi.fn((id) => pendingFrames.delete(id)));

        const restore = enforceDoctorSidebarMinWidth(mount);

        expect(DOCTOR_SIDEBAR_MIN_WIDTH_PX).toBe(560);
        expect([panel.style.minWidth, panel.style.width, panel.style.flexBasis]).toEqual([
            "560px", "560px", "560px",
        ]);
        expect([content.style.minWidth, content.style.width, content.style.flexBasis]).toEqual([
            "560px", "560px", "13px",
        ]);
        expect([mount.style.minWidth, mount.style.width, mount.style.flexBasis]).toEqual([
            "560px", "29px", "31px",
        ]);

        restore();
        restore();

        expect(pendingFrames.size).toBe(0);
        expect([panel.style.minWidth, panel.style.width, panel.style.flexBasis]).toEqual([
            "233px", "300px", "17px",
        ]);
        expect([content.style.minWidth, content.style.width, content.style.flexBasis]).toEqual([
            "211px", "300px", "13px",
        ]);
        expect([mount.style.minWidth, mount.style.width, mount.style.flexBasis]).toEqual([
            "19px", "29px", "31px",
        ]);
    });

    test("preserves sufficient actual widths and restores the exact mount layout", () => {
        const panel = createElement({
            style: { minWidth: "233px", width: "700px", flexBasis: "42%" },
            width: 700,
        });
        const content = createElement({
            style: { minWidth: "211px", width: "700px", flexBasis: "13px" },
            width: 700,
        });
        const mount = createElement({
            className: "other-extension host-slot",
            style: { minWidth: "19px", width: "29px", flexBasis: "31px" },
            width: 700,
        });
        mount.closest = (selector) => ({
            ".side-bar-panel": panel,
            ".p-splitterpanel": panel,
            ".sidebar-content-container": content,
        }[selector] ?? null);
        vi.stubGlobal("requestAnimationFrame", vi.fn(() => 1));
        vi.stubGlobal("cancelAnimationFrame", vi.fn());

        const restoreLayout = enforceDoctorSidebarMinWidth(mount);

        expect(panel.style.width).toBe("700px");
        expect(panel.style.flexBasis).toBe("42%");
        expect(content.style.width).toBe("700px");

        restoreLayout();
        restoreLayout();

        expect(mount.className).toBe("other-extension host-slot");
        expect([mount.style.minWidth, mount.style.width, mount.style.flexBasis]).toEqual([
            "19px", "29px", "31px",
        ]);
    });

    test("rolls back synchronous geometry when deferred scheduling fails", () => {
        const panel = createElement({
            style: { minWidth: "233px", width: "300px", flexBasis: "17px" },
            width: 300,
        });
        const content = createElement({
            style: { minWidth: "211px", width: "300px", flexBasis: "13px" },
            width: 300,
        });
        const mount = createElement({
            style: { minWidth: "19px", width: "29px", flexBasis: "31px" },
            width: 29,
        });
        mount.closest = (selector) => ({
            ".side-bar-panel": panel,
            ".p-splitterpanel": panel,
            ".sidebar-content-container": content,
        }[selector] ?? null);
        vi.stubGlobal("requestAnimationFrame", vi.fn(() => {
            throw new Error("synthetic scheduling failure");
        }));

        expect(() => enforceDoctorSidebarMinWidth(mount)).toThrow("synthetic scheduling failure");
        expect([panel.style.minWidth, panel.style.width, panel.style.flexBasis]).toEqual([
            "233px", "300px", "17px",
        ]);
        expect([content.style.minWidth, content.style.width, content.style.flexBasis]).toEqual([
            "211px", "300px", "13px",
        ]);
        expect([mount.style.minWidth, mount.style.width, mount.style.flexBasis]).toEqual([
            "19px", "29px", "31px",
        ]);
    });

    test("preserves incoming layout ownership during host mount takeover", () => {
        const panel = createElement({
            style: { minWidth: "233px", width: "300px", flexBasis: "17px" },
            width: 300,
        });
        const content = createElement({
            style: { minWidth: "211px", width: "300px", flexBasis: "13px" },
            width: 300,
        });
        const mount = createElement({
            style: { minWidth: "19px", width: "29px", flexBasis: "31px" },
            width: 29,
        });
        mount.closest = (selector) => ({
            ".side-bar-panel": panel,
            ".p-splitterpanel": panel,
            ".sidebar-content-container": content,
        }[selector] ?? null);
        vi.stubGlobal("requestAnimationFrame", vi.fn(() => 1));
        vi.stubGlobal("cancelAnimationFrame", vi.fn());

        const restore = enforceDoctorSidebarMinWidth(mount);
        panel.style.minWidth = "704px";
        panel.style.width = "704px";
        panel.style.flexBasis = "704px";
        content.style.minWidth = "704px";
        content.style.width = "704px";
        content.style.flexBasis = "704px";
        mount.style.minWidth = "704px";
        mount.style.width = "704px";
        mount.style.flexBasis = "704px";

        restore({ preserveExternalChanges: true });

        expect([panel.style.minWidth, panel.style.width, panel.style.flexBasis]).toEqual([
            "704px", "704px", "704px",
        ]);
        expect([content.style.minWidth, content.style.width, content.style.flexBasis]).toEqual([
            "704px", "704px", "704px",
        ]);
        expect([mount.style.minWidth, mount.style.width, mount.style.flexBasis]).toEqual([
            "704px", "704px", "704px",
        ]);
    });
});
