export const DOCTOR_SIDEBAR_MIN_WIDTH_PX = 560;

const LAYOUT_PROPERTIES = ["minWidth", "width", "flexBasis"];

function isStylableElement(value) {
    return Boolean(value?.style);
}

export function enforceDoctorSidebarMinWidth(container) {
    if (!isStylableElement(container)) return () => {};

    const styleSnapshots = new Map();
    const lastDoctorWrites = new Map();
    const observedElements = new Set();
    const externallyChangedElements = new Set();
    let disposed = false;
    let scheduledKind = "";
    let scheduledHandle = null;
    let styleObserver = null;

    const recordExternalChanges = (records) => {
        for (const record of records) {
            if (record.type === "attributes" && record.attributeName === "style") {
                externallyChangedElements.add(record.target);
            }
        }
    };

    const collectPendingExternalChanges = () => {
        if (styleObserver) recordExternalChanges(styleObserver.takeRecords());
    };

    const disconnectStyleObserver = () => {
        collectPendingExternalChanges();
        styleObserver?.disconnect();
    };

    const observeCapturedElements = () => {
        if (!styleObserver || disposed) return;
        for (const element of observedElements) {
            styleObserver.observe(element, {
                attributes: true,
                attributeFilter: ["style"],
            });
        }
    };

    const captureLayout = (element) => {
        if (!isStylableElement(element) || styleSnapshots.has(element)) return;
        styleSnapshots.set(
            element,
            Object.fromEntries(
                LAYOUT_PROPERTIES.map((property) => [property, element.style[property]]),
            ),
        );
        lastDoctorWrites.set(element, {});
        observedElements.add(element);
    };

    const writeLayout = (element, property, value) => {
        captureLayout(element);
        element.style[property] = value;
        lastDoctorWrites.get(element)[property] = element.style[property];
    };

    const measuredWidthIsBelowMinimum = (element) => {
        const width = element.getBoundingClientRect?.().width;
        return Number.isFinite(width) && width < DOCTOR_SIDEBAR_MIN_WIDTH_PX;
    };

    const applyMinimum = () => {
        scheduledHandle = null;
        scheduledKind = "";
        if (disposed) return;

        // CRITICAL: PrimeVue SplitterPanel owns actual sidebar geometry. Measure before
        // writing min-width: measuring afterward can already report 560px and leave a stale
        // narrow flex-basis. Inner-only minimums clip, unconditional width writes corrupt
        // saved host layout, and every captured value must be restored during teardown.
        disconnectStyleObserver();
        const sidePanel = container.closest?.(".side-bar-panel");
        const fallbackPanel = container.closest?.(".p-splitterpanel");
        const splitterPanel = isStylableElement(sidePanel) ? sidePanel : fallbackPanel;
        if (isStylableElement(splitterPanel)) {
            const wasBelowMinimum = measuredWidthIsBelowMinimum(splitterPanel);
            writeLayout(splitterPanel, "minWidth", `${DOCTOR_SIDEBAR_MIN_WIDTH_PX}px`);
            if (wasBelowMinimum) {
                writeLayout(splitterPanel, "width", `${DOCTOR_SIDEBAR_MIN_WIDTH_PX}px`);
                writeLayout(splitterPanel, "flexBasis", `${DOCTOR_SIDEBAR_MIN_WIDTH_PX}px`);
            }
        }

        const sidebarContent = container.closest?.(".sidebar-content-container");
        if (isStylableElement(sidebarContent)) {
            const wasBelowMinimum = measuredWidthIsBelowMinimum(sidebarContent);
            writeLayout(sidebarContent, "minWidth", `${DOCTOR_SIDEBAR_MIN_WIDTH_PX}px`);
            if (wasBelowMinimum) {
                writeLayout(sidebarContent, "width", `${DOCTOR_SIDEBAR_MIN_WIDTH_PX}px`);
            }
        }

        writeLayout(container, "minWidth", `${DOCTOR_SIDEBAR_MIN_WIDTH_PX}px`);
        observeCapturedElements();
    };

    const cancelScheduledApply = () => {
        if (
            scheduledHandle !== null
            && scheduledKind === "animation-frame"
            && typeof cancelAnimationFrame === "function"
        ) {
            cancelAnimationFrame(scheduledHandle);
        } else if (scheduledHandle !== null && scheduledKind === "timeout") {
            clearTimeout(scheduledHandle);
        }
        scheduledHandle = null;
        scheduledKind = "";
    };

    const restoreCapturedLayout = ({ preserveExternalChanges = false } = {}) => {
        disconnectStyleObserver();
        for (const [element, snapshot] of styleSnapshots) {
            const doctorWrites = lastDoctorWrites.get(element) ?? {};
            if (preserveExternalChanges && externallyChangedElements.has(element)) continue;
            for (const [property, value] of Object.entries(snapshot)) {
                // CRITICAL: takeover cleanup may restore only properties Doctor actually
                // wrote and that still equal its last write. Reversing this ownership test
                // overwrites incoming width/flexBasis values that Doctor never owned.
                if (
                    !preserveExternalChanges
                    || (
                        property in doctorWrites
                        && element.style[property] === doctorWrites[property]
                    )
                ) {
                    element.style[property] = value;
                }
            }
        }
        styleSnapshots.clear();
        lastDoctorWrites.clear();
        observedElements.clear();
        externallyChangedElements.clear();
    };

    try {
        applyMinimum();
        if (typeof MutationObserver === "function") {
            styleObserver = new MutationObserver(recordExternalChanges);
            observeCapturedElements();
        }
        if (typeof requestAnimationFrame === "function") {
            scheduledKind = "animation-frame";
            scheduledHandle = requestAnimationFrame(applyMinimum);
        } else {
            scheduledKind = "timeout";
            scheduledHandle = setTimeout(applyMinimum, 0);
        }
    } catch (error) {
        // CRITICAL: this function may throw before its disposer reaches the caller.
        // Roll back every captured host style here or an early scheduling/style fault
        // leaves PrimeVue geometry poisoned with no cleanup handle to restore it.
        disposed = true;
        cancelScheduledApply();
        restoreCapturedLayout();
        throw error;
    }

    return (options = {}) => {
        if (disposed) return;
        disposed = true;
        cancelScheduledApply();
        restoreCapturedLayout(options);
    };
}
