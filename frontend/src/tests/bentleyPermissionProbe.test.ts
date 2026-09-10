/**
 * Offline tests for the pure Bentley permission-probe classifier. No network,
 * no Bentley runtime — only the READY/PARTIAL/BLOCKED decision logic.
 */
import { describe, expect, it } from 'vitest'
import {
    accessFromStatus,
    classifyBentleyPermissionProbe,
    type PermissionProbeInputs,
} from '../components/spatial/bentleyPermissionProbe'

const base: PermissionProbeInputs = {
    tokenPresent: true,
    imodelRead: 'YES',
    imodelCreate: 'YES',
    storageRead: 'YES',
    storageWrite: 'YES',
    syncAuthorization: 'AUTHORIZED',
    anyAuthScopeError: false,
}

describe('classifyBentleyPermissionProbe', () => {
    it('all permissions present + sync AUTHORIZED => READY', () => {
        const v = classifyBentleyPermissionProbe(base)
        expect(v.readiness).toBe('READY')
        expect(v.blockers).toEqual([])
    })
    it('imodels_manage missing (NO) => BLOCKED with the exact blocker', () => {
        const v = classifyBentleyPermissionProbe({ ...base, imodelCreate: 'NO' })
        expect(v.readiness).toBe('BLOCKED')
        expect(v.blockers.some((b) => b.includes('imodels_manage'))).toBe(true)
    })
    it('storage_write missing (NO) => BLOCKED', () => {
        const v = classifyBentleyPermissionProbe({ ...base, storageWrite: 'NO' })
        expect(v.readiness).toBe('BLOCKED')
        expect(v.blockers.some((b) => b.includes('storage_write'))).toBe(true)
    })
    it('sync FORBIDDEN => BLOCKED', () => {
        const v = classifyBentleyPermissionProbe({ ...base, syncAuthorization: 'FORBIDDEN' })
        expect(v.readiness).toBe('BLOCKED')
        expect(v.blockers).toContain('SYNCHRONIZATION_API_FORBIDDEN')
    })
    it('401 / auth-scope error => BLOCKED (auth scope blocker)', () => {
        const v = classifyBentleyPermissionProbe({ ...base, anyAuthScopeError: true })
        expect(v.readiness).toBe('BLOCKED')
        expect(v.blockers.some((b) => b.includes('AUTH_SCOPE_BLOCKER'))).toBe(true)
    })
    it('no runtime token => BLOCKED', () => {
        const v = classifyBentleyPermissionProbe({ ...base, tokenPresent: false })
        expect(v.readiness).toBe('BLOCKED')
    })
    it('unknown permission metadata (no hard denial) => PARTIAL with unverified blockers', () => {
        const v = classifyBentleyPermissionProbe({ ...base, imodelCreate: 'UNKNOWN', storageWrite: 'UNKNOWN', syncAuthorization: 'UNKNOWN' })
        expect(v.readiness).toBe('PARTIAL')
        expect(v.blockers).toContain('IMODEL_CREATE_PERMISSION_UNVERIFIED')
        expect(v.blockers).toContain('STORAGE_WRITE_PERMISSION_UNVERIFIED')
        expect(v.blockers).toContain('SYNCHRONIZATION_AUTHORIZATION_UNVERIFIED')
    })
    it('sync REQUIRES_ADDITIONAL_AUTHORIZATION (no other denial) => PARTIAL and records it', () => {
        const v = classifyBentleyPermissionProbe({ ...base, syncAuthorization: 'REQUIRES_ADDITIONAL_AUTHORIZATION' })
        expect(v.readiness).toBe('PARTIAL')
        expect(v.blockers).toContain('SYNCHRONIZATION_REQUIRES_ADDITIONAL_AUTHORIZATION')
    })
})

describe('accessFromStatus', () => {
    it('2xx => YES, 403 => NO, others => UNKNOWN', () => {
        expect(accessFromStatus(200)).toBe('YES')
        expect(accessFromStatus(204)).toBe('YES')
        expect(accessFromStatus(403)).toBe('NO')
        expect(accessFromStatus(401)).toBe('UNKNOWN')
        expect(accessFromStatus(404)).toBe('UNKNOWN')
        expect(accessFromStatus(429)).toBe('UNKNOWN')
    })
})
