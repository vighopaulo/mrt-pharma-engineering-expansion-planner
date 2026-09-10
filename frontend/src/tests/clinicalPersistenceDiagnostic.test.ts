import { describe, it, expect } from 'vitest'
import {
    classifyClinicalPersistenceRegression,
    recoveryActionForClass,
    type PersistenceEvidence,
} from '../components/spatial/clinicalPersistenceDiagnostic'

const E = (o: Partial<PersistenceEvidence> = {}): PersistenceEvidence => ({
    currentAssignmentRecordCount: 0, currentVolumeRecordCount: 0,
    legacyAssignmentRecordCount: 0, legacyVolumeRecordCount: 0,
    runtimeAssignmentCount: 0, runtimeVolumeCount: 0, ...o,
})

describe('§30 current data / loader failure', () => {
    it('current holds data, runtime empty => CURRENT_STORAGE_HAS_DATA_LOADER_FAILED', () => {
        expect(classifyClinicalPersistenceRegression(E({ currentAssignmentRecordCount: 1, currentVolumeRecordCount: 1 }))).toBe('CURRENT_STORAGE_HAS_DATA_LOADER_FAILED')
    })
    it('present value that failed to parse => loader failure', () => {
        expect(classifyClinicalPersistenceRegression(E({ currentAssignmentParseFailed: true }))).toBe('CURRENT_STORAGE_HAS_DATA_LOADER_FAILED')
    })
})

describe('§31 legacy recovery', () => {
    it('current empty, legacy holds data => LEGACY_STORAGE_HAS_RECOVERABLE_DATA', () => {
        expect(classifyClinicalPersistenceRegression(E({ legacyAssignmentRecordCount: 1, legacyVolumeRecordCount: 1 }))).toBe('LEGACY_STORAGE_HAS_RECOVERABLE_DATA')
    })
})

describe('§32 genuinely absent', () => {
    it('everything empty => PERSISTED_STATE_GENUINELY_ABSENT', () => {
        expect(classifyClinicalPersistenceRegression(E())).toBe('PERSISTED_STATE_GENUINELY_ABSENT')
        expect(recoveryActionForClass('PERSISTED_STATE_GENUINELY_ABSENT')).toBe('RECONSTRUCTION_REQUIRED')
    })
})

describe('§33 partial state', () => {
    it('assignment present, volume missing (both runtime + current reflect it)', () => {
        // current assignment present, current volume absent, runtime reflects assignment (not empty)
        expect(classifyClinicalPersistenceRegression(E({ currentAssignmentRecordCount: 1, runtimeAssignmentCount: 1 }))).toBe('ASSIGNMENT_PRESENT_VOLUME_MISSING')
    })
    it('volume present, assignment missing', () => {
        expect(classifyClinicalPersistenceRegression(E({ currentVolumeRecordCount: 1, runtimeVolumeCount: 1 }))).toBe('VOLUME_PRESENT_ASSIGNMENT_MISSING')
    })
})

describe('no failure', () => {
    it('current + runtime agree, non-empty => NO_FAILURE', () => {
        expect(classifyClinicalPersistenceRegression(E({ currentAssignmentRecordCount: 1, currentVolumeRecordCount: 1, runtimeAssignmentCount: 1, runtimeVolumeCount: 1 }))).toBe('NO_FAILURE')
    })
})

describe('recovery action mapping', () => {
    it('loader failure => fix loader, not data', () => {
        expect(recoveryActionForClass('CURRENT_STORAGE_HAS_DATA_LOADER_FAILED')).toBe('FIX_LOADER_NOT_DATA')
    })
    it('legacy recoverable => migrate source', () => {
        expect(recoveryActionForClass('LEGACY_STORAGE_HAS_RECOVERABLE_DATA')).toBe('MIGRATE_LEGACY_SOURCE_RECORDS')
    })
})
