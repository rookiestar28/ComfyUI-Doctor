import { describe, it, expect } from 'vitest';
import {
    shouldShowIntentBanner,
    getDominantIntents,
    hasNoMatchedIntent
} from '../../web/utils/intent_logic.js';

describe('Intent Logic', () => {
    it('shouldShowIntentBanner returns true if signature exists', () => {
        expect(shouldShowIntentBanner({ intent_signature: {} })).toBe(true);
        expect(shouldShowIntentBanner({})).toBe(false);
        expect(shouldShowIntentBanner(null)).toBe(false);
    });

    it('getDominantIntents returns top k items', () => {
        const report = {
            intent_signature: {
                top_intents: [
                    { id: '1', confidence: 0.9 },
                    { id: '2', confidence: 0.8 },
                    { id: '3', confidence: 0.7 },
                    { id: '4', confidence: 0.6 }
                ]
            }
        };
        // Default max=3
        expect(getDominantIntents(report)).toHaveLength(3);
        // Custom max
        expect(getDominantIntents(report, 2)).toHaveLength(2);
    });

    it('getDominantIntents handles empty/missing', () => {
        expect(getDominantIntents({})).toEqual([]);
        expect(getDominantIntents({ intent_signature: {} })).toEqual([]);
    });

    it('hasNoMatchedIntent detects fallback case', () => {
        // Signature exists, but top_intents empty -> True (Fallback)
        expect(hasNoMatchedIntent({
            intent_signature: { top_intents: [] }
        })).toBe(true);

        // Signature missing -> False (Not active)
        expect(hasNoMatchedIntent({})).toBe(undefined);

        // Signature has intents -> False (Normal)
        expect(hasNoMatchedIntent({
            intent_signature: { top_intents: [{}] }
        })).toBe(false);
    });
});
