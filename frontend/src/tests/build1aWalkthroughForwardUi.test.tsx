/**
 * Build 1A walkthrough correction — UI test (§21): the DIAGNOSE WALKTHROUGH
 * MOVEMENT button is wired into the live Developer Diagnostics panel and invokes
 * the overlay diagnostic (synchronous click counter first; no silent no-op). The
 * heavy overlay module is mocked (no @itwin).
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

const diagnoseWalkthroughMovement = vi.fn(async () => '=== WALKTHROUGH MOVEMENT ===\nWALKTHROUGH_ACTIVE = YES\nLAST_MOVEMENT_ACCEPTED = YES')
vi.mock('../components/spatial/spatialAssetOverlay', () => ({
    inspectBimContentAudit: vi.fn(async () => 'AUDIT'),
    probeBentleyCloudPermissions: vi.fn(async () => 'PROBE'),
    diagnoseClinicalProgramOverlay: vi.fn(async () => 'OVERLAY'),
    diagnoseRoomSpatialAuthority: vi.fn(async () => 'ROOMAUTH'),
    diagnoseAuthoritativeRoomGeometry: vi.fn(async () => 'AUTHGEO'),
    diagnoseClinicalPlanningVolume: vi.fn(async () => 'PV'),
    diagnoseClinicalPlanningVolumes: vi.fn(async () => 'PVS'),
    diagnoseClinicalProgramPersistence: vi.fn(async () => 'PERSIST'),
    reconstructUptake01Baseline: vi.fn(async () => ({ ok: true, alreadyPresent: true })),
    diagnoseBimRoomDiscovery: vi.fn(async () => 'DISCOVERY'),
    diagnoseSelectedRoomVolume: vi.fn(async () => 'SELECTED'),
    diagnoseWalkthroughMovement,
}))

import { AuditDiagnosticsPanel } from '../components/spatial/AuditDiagnosticsPanel'

describe('Build 1A walkthrough §21 — movement diagnostic wired into the live panel', () => {
    beforeEach(() => { diagnoseWalkthroughMovement.mockClear() })

    it('DIAGNOSE WALKTHROUGH MOVEMENT button exists', () => {
        render(<AuditDiagnosticsPanel />)
        expect(screen.getByRole('button', { name: 'DIAGNOSE WALKTHROUGH MOVEMENT' })).toBeTruthy()
    })

    it('clicking it invokes the overlay walkthrough diagnostic and shows output', async () => {
        render(<AuditDiagnosticsPanel />)
        fireEvent.click(screen.getByRole('button', { name: 'DIAGNOSE WALKTHROUGH MOVEMENT' }))
        await waitFor(() => expect(diagnoseWalkthroughMovement).toHaveBeenCalledTimes(1))
        // Assert on a line unique to the diagnostic OUTPUT (not the button label).
        await screen.findByText(/LAST_MOVEMENT_ACCEPTED = YES/)
    })

    it('records the synchronous CLICK counter (never a silent no-op)', () => {
        render(<AuditDiagnosticsPanel />)
        fireEvent.click(screen.getByRole('button', { name: 'DIAGNOSE WALKTHROUGH MOVEMENT' }))
        expect(screen.getByText(/CLICK_COUNT = 1/)).toBeTruthy()
    })

    it('the prior diagnostics (incl. Build 1A.2 generic + Uptake) are preserved', () => {
        render(<AuditDiagnosticsPanel />)
        for (const name of ['DIAGNOSE BIM ROOM DISCOVERY', 'DIAGNOSE SELECTED ROOM VOLUME', 'DIAGNOSE CLINICAL PROGRAM OVERLAY', 'RECONSTRUCT UPTAKE 01 BASELINE']) {
            expect(screen.getByRole('button', { name })).toBeTruthy()
        }
    })
})
