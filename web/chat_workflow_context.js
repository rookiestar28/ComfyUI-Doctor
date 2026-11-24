/**
 * Opt-in workflow context for chat requests.
 *
 * The backend narrows a workflow to the failed node's neighborhood (and sanitizes it like every other
 * outbound text), but the graph carries prompts, file names and custom-node settings. It therefore
 * travels with a chat question only when the user turned "Send the workflow with chat questions" on;
 * the setting defaults to off and a request built while it is off is the stored error context itself.
 */

import { app } from "../../../scripts/app.js";
import { getComfyRootGraph, getDoctorRuntimeSettings } from "./comfyui_frontend_compat.js";

// Longest serialized graph that is sent. The backend keeps only a couple of thousand characters of it,
// so a larger graph is not worth uploading; it is left out whole rather than cut (partial JSON is
// unparseable and would only look like a corrupt workflow to the backend).
export const MAX_CHAT_WORKFLOW_CHARS = 256000;

/**
 * Serialize the root graph for a chat request, or return null when it is unavailable or too large.
 * Never throws: a host graph that cannot be serialized must not block the chat.
 */
export function captureWorkflowForChat(appInstance = app, maxChars = MAX_CHAT_WORKFLOW_CHARS) {
    try {
        const graph = getComfyRootGraph(appInstance);
        if (typeof graph?.serialize !== "function") return null;
        // IMPORTANT: serialize the root graph so subgraph-expanded workflows keep their full execution
        // topology for the backend's truncation.
        const workflow = graph.serialize();
        if (!workflow) return null;
        const text = JSON.stringify(workflow);
        if (typeof text !== "string" || text.length > maxChars) return null;
        return text;
    } catch (error) {
        console.warn("[ComfyUI-Doctor] Failed to capture workflow:", error);
        return null;
    }
}

/**
 * The `error_context` of a chat request.
 *
 * Setting off (the default) or no usable graph: the stored error context, unchanged (an empty object
 * when there is none). Setting on: a copy of it that also carries the serialized graph as `workflow`.
 * The stored context is never mutated, so switching the setting off again stops sending the graph.
 */
export function buildChatErrorContext(storedContext, appInstance = app) {
    const base = storedContext || {};
    let includeWorkflow = false;
    try {
        includeWorkflow = getDoctorRuntimeSettings(appInstance).includeWorkflowContext === true;
    } catch (error) {
        console.warn("[ComfyUI-Doctor] Could not read the workflow-context setting; not sending the workflow:", error);
    }
    if (!includeWorkflow) return base;
    const workflow = captureWorkflowForChat(appInstance);
    return workflow === null ? base : { ...base, workflow };
}
