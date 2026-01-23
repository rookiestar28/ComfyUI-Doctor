/**
 * Pure functions for intent signature logic.
 */

export function shouldShowIntentBanner(report) {
    // Show banner if:
    // 1. report.intent_signature exists AND has top_intents > 0
    // OR
    // 2. report.intent_signature exists AND (top_intents is empty) -> this is the "fallback" case
    return !!(report?.intent_signature);
}

export function getDominantIntents(report, max = 3) {
    if (!report?.intent_signature?.top_intents) return [];
    return report.intent_signature.top_intents.slice(0, max);
}

export function hasNoMatchedIntent(report) {
    return (
        report?.intent_signature &&
        (!report.intent_signature.top_intents || report.intent_signature.top_intents.length === 0)
    );
}

export function formatIntentStage(stageId) {
    // This is just a helper for consistent ID formatting if needed
    // The actual display uses i18n which is a separate concern
    return stageId || 'unknown';
}
