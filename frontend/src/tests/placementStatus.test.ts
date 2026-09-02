/**
 * Regression tests for the placement status seam. Proves the "Placing…"
 * instruction never lingers after a successful placement (the manual-acceptance
 * defect), and that success/cancel statuses are correct. Pure presentation
 * logic — no Bentley, no React render needed.
 */
import { describe, expect, it } from 'vitest'
import { resolveMoveStatus, resolvePlacementStatus } from '../components/spatial/placementStatus'

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

describe('resolveMoveStatus', () => {
    it('active move status contains "Moving"', () => {
        const s = resolveMoveStatus({ active: true, wasActive: false, displayLabel: 'GE HealthCare Discovery MI' })
        expect(s.phase).toBe('MOVE_ACTIVE')
        expect(s.text).toContain('Moving')
    })

    it('successful move does NOT contain "Moving" and names the moved instance', () => {
        const s = resolveMoveStatus({
            active: false, wasActive: true, displayLabel: 'GE HealthCare Discovery MI',
            assetInstanceId: 'PETCT-GE-DISCOVERY-MI-0001', positionChanged: true,
        })
        expect(s.phase).toBe('MOVE_SUCCEEDED')
        expect(s.text).not.toContain('Moving')
        expect(s.text).toContain('Moved')
        expect(s.text).toContain('PETCT-GE-DISCOVERY-MI-0001')
    })

    it('cancelled move (no position change) is "Move cancelled" with no "Moving"', () => {
        const s = resolveMoveStatus({
            active: false, wasActive: true, displayLabel: 'GE HealthCare Discovery MI',
            assetInstanceId: 'PETCT-GE-DISCOVERY-MI-0001', positionChanged: false,
        })
        expect(s.phase).toBe('MOVE_CANCELLED')
        expect(s.text).toBe('Move cancelled')
        expect(s.text).not.toContain('Moving')
    })

    it('idle move (no transition) yields IDLE empty text', () => {
        const s = resolveMoveStatus({ active: false, wasActive: false })
        expect(s.phase).toBe('IDLE')
        expect(s.text).toBe('')
    })
})
