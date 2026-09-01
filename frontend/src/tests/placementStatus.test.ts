/**
 * Regression tests for the placement status seam. Proves the "Placing…"
 * instruction never lingers after a successful placement (the manual-acceptance
 * defect), and that success/cancel statuses are correct. Pure presentation
 * logic — no Bentley, no React render needed.
 */
import { describe, expect, it } from 'vitest'
import { resolvePlacementStatus } from '../components/spatial/placementStatus'

describe('resolvePlacementStatus', () => {
    it('active placement status contains "Placing"', () => {
        const s = resolvePlacementStatus({
            active: true, wasActive: false, count: 0, prevCount: 0,
            displayLabel: 'GE HealthCare Discovery MI',
        })
        expect(s.phase).toBe('PLACEMENT_ACTIVE')
        expect(s.text).toContain('Placing')
        expect(s.text).toContain('GE HealthCare Discovery MI')
    })

    it('successful placement status does NOT contain "Placing" and identifies the placed asset', () => {
        const s = resolvePlacementStatus({
            active: false, wasActive: true, count: 1, prevCount: 0,
            displayLabel: 'GE HealthCare Discovery MI',
            lastPlacedInstanceId: 'PETCT-GE-DISCOVERY-MI-0001',
        })
        expect(s.phase).toBe('PLACEMENT_SUCCEEDED')
        expect(s.text).not.toContain('Placing')
        expect(s.text).toContain('Placed')
        expect(s.text).toContain('PETCT-GE-DISCOVERY-MI-0001')
    })

    it('cancelled placement status is "Placement cancelled" and has no "Placing"', () => {
        const s = resolvePlacementStatus({
            active: false, wasActive: true, count: 0, prevCount: 0,
            displayLabel: 'GE HealthCare Discovery MI',
        })
        expect(s.phase).toBe('PLACEMENT_CANCELLED')
        expect(s.text).toContain('Placement cancelled')
        expect(s.text).not.toContain('Placing')
    })

    it('idle (no transition) yields IDLE with empty text', () => {
        const s = resolvePlacementStatus({ active: false, wasActive: false, count: 1, prevCount: 1 })
        expect(s.phase).toBe('IDLE')
        expect(s.text).toBe('')
    })

    it('success prefers displayLabel when no instance id is available', () => {
        const s = resolvePlacementStatus({
            active: false, wasActive: true, count: 2, prevCount: 1,
            displayLabel: 'GE HealthCare Discovery MI',
        })
        expect(s.phase).toBe('PLACEMENT_SUCCEEDED')
        expect(s.text).toBe('Placed: GE HealthCare Discovery MI')
    })
})
