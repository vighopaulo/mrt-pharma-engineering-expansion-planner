/**
 * Build 1A.2 — UI tests: the generic diagnostics are wired into the live
 * Developer Diagnostics panel, and the generic selected-room diagnostic targets
 * the CURRENTLY selected room (never Uptake-substituted). The heavy overlay
 * module is mocked so vitest never imports the @itwin stack.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the overlay: record which generic diagnostics the panel invokes.
const diagnoseBimRoomDiscovery = vi.fn(async () => 'BIM_ROOM_DISCOVERY_DIAGNOSTIC_OK')
const diagnoseSelectedRoomVolume = vi.fn(async () => 'SELECTED_ROOM_VOLUME_DIAGNOSTIC_OK bimSpaceId=0x200000001f6')
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
    diagnoseBimRoomDiscovery,
    diagnoseSelectedRoomVolume,
}))

import { AuditDiagnosticsPanel } from '../components/spatial/AuditDiagnosticsPanel'

describe('Build 1A.2 §21 — generic diagnostics wired into the live panel', () => {
    beforeEach(() => { diagnoseBimRoomDiscovery.mockClear(); diagnoseSelectedRoomVolume.mockClear() })

    it('DIAGNOSE BIM ROOM DISCOVERY button exists', () => {
        render(<AuditDiagnosticsPanel />)
        expect(screen.getByRole('button', { name: 'DIAGNOSE BIM ROOM DISCOVERY' })).toBeTruthy()
    })

    it('DIAGNOSE SELECTED ROOM VOLUME button exists', () => {
        render(<AuditDiagnosticsPanel />)
        expect(screen.getByRole('button', { name: 'DIAGNOSE SELECTED ROOM VOLUME' })).toBeTruthy()
    })

    it('the Uptake regression diagnostics are preserved (not removed)', () => {
        render(<AuditDiagnosticsPanel />)
        for (const name of [
            'DIAGNOSE CLINICAL PROGRAM OVERLAY',
            'DIAGNOSE UPTAKE 01 SPATIAL AUTHORITY',
            'DIAGNOSE UPTAKE 01 AUTHORITATIVE GEOMETRY',
            'DIAGNOSE UPTAKE 01 PLANNING VOLUME',
            'DIAGNOSE CLINICAL PLANNING VOLUMES',
            'DIAGNOSE CLINICAL PROGRAM PERSISTENCE',
            'RECONSTRUCT UPTAKE 01 BASELINE',
        ]) {
            expect(screen.getByRole('button', { name })).toBeTruthy()
        }
    })

    it('clicking DIAGNOSE SELECTED ROOM VOLUME invokes the GENERIC selected-room diagnostic (no room id argument forced → overlay uses the selected room)', async () => {
        render(<AuditDiagnosticsPanel />)
        fireEvent.click(screen.getByRole('button', { name: 'DIAGNOSE SELECTED ROOM VOLUME' }))
        await waitFor(() => expect(diagnoseSelectedRoomVolume).toHaveBeenCalledTimes(1))
        // The panel does NOT pass an Uptake id; the overlay resolves the selected room.
        expect(diagnoseSelectedRoomVolume).toHaveBeenCalledWith()
        await screen.findByText(/SELECTED_ROOM_VOLUME_DIAGNOSTIC_OK/)
    })

    it('clicking DIAGNOSE BIM ROOM DISCOVERY invokes the generic discovery diagnostic', async () => {
        render(<AuditDiagnosticsPanel />)
        fireEvent.click(screen.getByRole('button', { name: 'DIAGNOSE BIM ROOM DISCOVERY' }))
        await waitFor(() => expect(diagnoseBimRoomDiscovery).toHaveBeenCalledTimes(1))
        await screen.findByText(/BIM_ROOM_DISCOVERY_DIAGNOSTIC_OK/)
    })

    it('a physical click records the synchronous CLICK counter (never a silent no-op)', () => {
        render(<AuditDiagnosticsPanel />)
        fireEvent.click(screen.getByRole('button', { name: 'DIAGNOSE BIM ROOM DISCOVERY' }))
        expect(screen.getByText(/CLICK_COUNT = 1/)).toBeTruthy()
    })
})
