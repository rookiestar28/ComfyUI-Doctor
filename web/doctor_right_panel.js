/**
 * Right-side latest diagnosis panel rendering for the Doctor extension.
 */

const DEFAULT_TEXT = {
    unknown_error: "Unknown Error",
    truncated: "... truncated ...",
    lines_omitted: "{0} lines omitted",
};

function getText(options, key) {
    const getUIText = options?.getUIText;
    if (typeof getUIText === "function") {
        return getUIText(key);
    }
    return DEFAULT_TEXT[key] || key;
}

export function extractErrorInfo(data = {}, options = {}) {
    const result = {
        errorSummary: null,
        fullError: null,
        suggestion: null,
        hasLongError: false,
    };

    if (data.suggestion) {
        let suggestion = data.suggestion.replace("\uD83D\uDCA1 SUGGESTION: ", "").trim();

        const sentences = suggestion.split(". ");
        if (sentences.length > 1) {
            suggestion = sentences[sentences.length - 1].trim();
            if (!suggestion.endsWith(".")) {
                suggestion += ".";
            }
        }

        result.suggestion = suggestion;
    }

    if (data.last_error) {
        const fullError = data.last_error.trim();
        result.fullError = fullError;
        const lines = fullError.split("\n");

        if (fullError.includes("Failed to validate prompt")) {
            const nodeErrorLine = lines.find((line) => line.trim().startsWith("* "));
            const detailLine = lines.find((line) => line.trim().startsWith("- "));

            if (nodeErrorLine && detailLine) {
                result.errorSummary = `${nodeErrorLine.trim()}\n${detailLine.trim()}`;
            } else if (nodeErrorLine) {
                result.errorSummary = nodeErrorLine.trim();
            } else {
                const errorCount = (fullError.match(/Failed to validate prompt for output/g) || []).length;
                result.errorSummary = `Validation failed for ${errorCount} output(s)`;
            }

            result.hasLongError = fullError.length > 500;
        } else if (lines.length > 0) {
            let errorLine = null;

            for (let i = lines.length - 1; i >= 0; i--) {
                const line = lines[i].trim();
                if (/^[A-Z][a-zA-Z0-9]*(?:Error|Exception|Warning|Interrupt):/.test(line)) {
                    errorLine = line;
                    break;
                }
            }

            if (!errorLine) {
                for (let i = lines.length - 1; i >= 0; i--) {
                    const line = lines[i].trim();
                    if (line && !line.startsWith("Prompt executed") && !line.startsWith("+-")) {
                        errorLine = line;
                        break;
                    }
                }
            }

            result.errorSummary = errorLine || lines[lines.length - 1];
            result.hasLongError = fullError.length > 500;
        }
    }

    if (!result.errorSummary) {
        result.errorSummary = getText(options, "unknown_error");
    }

    return result;
}

export function truncateError(text, options = {}, maxLength = 500) {
    if (text.length <= maxLength) {
        return { truncated: text, isTruncated: false };
    }

    const lines = text.split("\n");

    if (lines.length <= 10) {
        const halfLength = Math.floor(maxLength / 2);
        return {
            truncated: `${text.substring(0, halfLength)}\n\n${getText(options, "truncated")}\n\n${text.substring(text.length - halfLength)}`,
            isTruncated: true,
        };
    }

    const firstLines = lines.slice(0, 3).join("\n");
    const lastLines = lines.slice(-3).join("\n");
    const omittedCount = lines.length - 6;

    return {
        truncated: `${firstLines}\n\n... (${getText(options, "lines_omitted").replace("{0}", omittedCount)}) ...\n\n${lastLines}`,
        isTruncated: true,
    };
}

export function updateRightErrorPanel({
    container,
    data,
    lastErrorData,
    getUIText,
    escapeHtml,
    hasNodeId,
    getPreferredNodeId,
    locateNodeOnCanvas,
}) {
    if (!container) return;

    const currentData = data || lastErrorData;
    if (!currentData) return;

    const textOptions = { getUIText };
    const { errorSummary, fullError, suggestion, hasLongError } = extractErrorInfo(currentData, textOptions);

    let html = `
        <div class="doctor-card-title">${getUIText("latest_diagnosis_title")}</div>
        <div class="doctor-card-body">
    `;

    html += `
        <div style="margin-bottom:12px;">
            <div style="font-size:10px;color:#999;text-transform:uppercase;margin-bottom:4px;">${getUIText("error_label")}</div>
            <div style="font-weight:bold;color:#ff8888;font-size:12px;line-height:1.4;">${escapeHtml(errorSummary)}</div>
        </div>
    `;

    if (hasLongError && fullError) {
        const { isTruncated } = truncateError(fullError, textOptions);
        html += `
            <details style="margin-bottom:12px;">
                <summary style="cursor:pointer;color:#aaa;font-size:11px;user-select:none;">
                    ${isTruncated ? getUIText("show_full_error") : getUIText("show_error_details")}
                </summary>
                <pre style="background:#1a1a1a;padding:8px;border-radius:4px;font-size:10px;color:#ccc;overflow-x:auto;margin-top:6px;white-space:pre-wrap;word-wrap:break-word;">${escapeHtml(fullError)}</pre>
            </details>
        `;
    }

    if (suggestion) {
        html += `
            <div style="margin-bottom:12px;padding:8px;background:#1a3a1a;border-left:3px solid #4a4;border-radius:4px;">
                <div style="font-size:10px;color:#8f8;text-transform:uppercase;margin-bottom:4px;">${getUIText("suggestion_label")}</div>
                <div style="color:#afa;font-size:11px;line-height:1.5;">${escapeHtml(suggestion)}</div>
            </div>
        `;
    }

    html += `<div style="font-size:11px;color:#666;margin-bottom:8px;">${new Date(currentData.timestamp).toLocaleTimeString()}</div>`;

    if (hasNodeId(currentData.node_context)) {
        const preferredNodeId = getPreferredNodeId(currentData.node_context);
        const safeNodeId = escapeHtml(String(preferredNodeId));
        const safeNodeName = escapeHtml(currentData.node_context.node_name || "Unknown");
        html += `
            <div style="background:#222;padding:6px;border-radius:4px;margin-bottom:8px;font-family:monospace;font-size:11px;">
                ${getUIText("node_label")} #${safeNodeId}: ${safeNodeName}
            </div>
            <button class="doctor-action-btn" id="doctor-locate-btn" data-node="${safeNodeId}">
                \uD83D\uDD0D ${getUIText("locate_node_btn")}
            </button>
        `;
    }

    html += `
        <div style="margin-top:10px;font-size:11px;color:#888;text-align:center;font-style:italic;">
            \uD83D\uDCA1 ${getUIText("sidebar_hint")}
        </div>
    `;

    html += "</div>";

    container.innerHTML = html;
    container.classList.add("error");

    const btn = container.querySelector("#doctor-locate-btn");
    if (btn) {
        btn.onclick = () => {
            const nodeId = btn.getAttribute("data-node");
            locateNodeOnCanvas(nodeId);
        };
    }
}
