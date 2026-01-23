import { describe, it, expect } from 'vitest';
import { t } from '../../web/utils/i18n_fallback.js';

describe('i18n Fallback', () => {
    const mockDict = {
        'hello': 'World',
        'nest.key': 'Nested'
    };

    it('should return translation if key exists', () => {
        expect(t(mockDict, 'hello', 'Fallback')).toBe('World');
    });

    it('should return fallback if key missing', () => {
        expect(t(mockDict, 'missing_key', 'Fallback Text')).toBe('Fallback Text');
    });

    it('should return fallback if uiText is null', () => {
        expect(t(null, 'hello', 'Fallback')).toBe('Fallback');
    });

    it('should handle empty strings as valid translations', () => {
        const dict = { 'empty': '' };
        expect(t(dict, 'empty', 'Fallback')).toBe('');
    });
});
