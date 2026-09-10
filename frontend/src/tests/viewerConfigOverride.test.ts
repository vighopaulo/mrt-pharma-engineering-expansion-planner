/**
 * Offline tests for the temporary, non-destructive demo-iModel selection guard.
 * Ensures a malformed ?imodel= value cannot be accepted (falls back to fixture).
 */
import { describe, expect, it } from 'vitest'
import { isPlausibleBentleyId } from '../lib/viewerConfig'

describe('isPlausibleBentleyId (demo-model override guard)', () => {
    it('accepts conservative Bentley-style ids', () => {
        expect(isPlausibleBentleyId('abcdef01-2345-6789-abcd-ef0123456789')).toBe(true)
        expect(isPlausibleBentleyId('bdf29ecd-b4a4-404d-861a-ac3061c7b12f')).toBe(true)
        expect(isPlausibleBentleyId('AbC123_-def456')).toBe(true)
    })
    it('rejects empty, too-short, too-long, or injection-shaped values', () => {
        expect(isPlausibleBentleyId('')).toBe(false)
        expect(isPlausibleBentleyId('short')).toBe(false)
        expect(isPlausibleBentleyId('a'.repeat(65))).toBe(false)
        expect(isPlausibleBentleyId('../../etc/passwd')).toBe(false)
        expect(isPlausibleBentleyId('id with spaces')).toBe(false)
        expect(isPlausibleBentleyId('id;DROP TABLE')).toBe(false)
        expect(isPlausibleBentleyId('<script>')).toBe(false)
    })
})
