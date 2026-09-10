/**
 * clinicalPersistenceDiagnostic — pure, Bentley-free classifier for the clinical
 * program / planning-volume PERSISTENCE regression.
 *
 * Given bounded evidence about what the current + legacy localStorage keys hold
 * and what the runtime currently has, it returns exactly ONE primary class so
 * recovery is evidence-based (never synthesized from remembered values).
 */

export type PersistenceRegressionClass =
    | 'NO_FAILURE'
    | 'CURRENT_STORAGE_HAS_DATA_LOADER_FAILED'
    | 'LEGACY_STORAGE_HAS_RECOVERABLE_DATA'
    | 'STORAGE_KEYS_CHANGED_DATA_ORPHANED'
    | 'ASSIGNMENT_PRESENT_VOLUME_MISSING'
    | 'VOLUME_PRESENT_ASSIGNMENT_MISSING'
    | 'CURRENT_STORAGE_EMPTY_OVERWRITE'
    | 'PERSISTED_STATE_GENUINELY_ABSENT'

export interface PersistenceEvidence {
    /** Records the CURRENT assignment key deserializes to (0 when key absent/empty). */
    currentAssignmentRecordCount: number
    /** Records the CURRENT volume key deserializes to. */
    currentVolumeRecordCount: number
    /** Records recoverable from any LEGACY assignment key/schema. */
    legacyAssignmentRecordCount: number
    /** Records recoverable from any LEGACY volume key/schema. */
    legacyVolumeRecordCount: number
    /** Runtime programState.assignments length. */
    runtimeAssignmentCount: number
    /** Runtime planningVolumes length. */
    runtimeVolumeCount: number
    /** A current-key value existed but failed JSON.parse / schema validation. */
    currentAssignmentParseFailed?: boolean
    currentVolumeParseFailed?: boolean
}

/**
 * Classify the single primary regression class. Precedence (strongest evidence
 * first):
 *   1. current key holds data but runtime is empty (or parse failed) => LOADER_FAILED
 *   2. current empty but legacy holds data => LEGACY_RECOVERABLE
 *   3. one side present, the other missing (current) => PARTIAL
 *   4. everything empty, runtime empty => GENUINELY_ABSENT
 *   5. current + runtime agree and non-empty => NO_FAILURE
 */
export function classifyClinicalPersistenceRegression(e: PersistenceEvidence): PersistenceRegressionClass {
    const currentHasData = e.currentAssignmentRecordCount > 0 || e.currentVolumeRecordCount > 0
    const legacyHasData = e.legacyAssignmentRecordCount > 0 || e.legacyVolumeRecordCount > 0
    const runtimeEmpty = e.runtimeAssignmentCount === 0 && e.runtimeVolumeCount === 0
    const parseFailed = !!e.currentAssignmentParseFailed || !!e.currentVolumeParseFailed

    // Parse failure with a present value is a loader failure regardless of counts.
    if (parseFailed) return 'CURRENT_STORAGE_HAS_DATA_LOADER_FAILED'

    // Current key holds data but runtime does not reflect it => loader failed.
    if (currentHasData && runtimeEmpty) return 'CURRENT_STORAGE_HAS_DATA_LOADER_FAILED'

    // Current empty, legacy holds data => recoverable via migration.
    if (!currentHasData && legacyHasData) return 'LEGACY_STORAGE_HAS_RECOVERABLE_DATA'

    // Partial current state (one side present, other absent).
    if (e.currentAssignmentRecordCount > 0 && e.currentVolumeRecordCount === 0) return 'ASSIGNMENT_PRESENT_VOLUME_MISSING'
    if (e.currentVolumeRecordCount > 0 && e.currentAssignmentRecordCount === 0) return 'VOLUME_PRESENT_ASSIGNMENT_MISSING'

    // Everything empty, runtime empty => genuinely absent.
    if (!currentHasData && !legacyHasData && runtimeEmpty) return 'PERSISTED_STATE_GENUINELY_ABSENT'

    return 'NO_FAILURE'
}

/** The recovery action implied by a class (advisory; recovery only when source exists). */
export type RecoveryAction =
    | 'NONE'
    | 'FIX_LOADER_NOT_DATA'
    | 'MIGRATE_LEGACY_SOURCE_RECORDS'
    | 'INVESTIGATE_PARTIAL_STATE'
    | 'RECONSTRUCTION_REQUIRED'

export function recoveryActionForClass(cls: PersistenceRegressionClass): RecoveryAction {
    switch (cls) {
        case 'CURRENT_STORAGE_HAS_DATA_LOADER_FAILED': return 'FIX_LOADER_NOT_DATA'
        case 'LEGACY_STORAGE_HAS_RECOVERABLE_DATA':
        case 'STORAGE_KEYS_CHANGED_DATA_ORPHANED': return 'MIGRATE_LEGACY_SOURCE_RECORDS'
        case 'ASSIGNMENT_PRESENT_VOLUME_MISSING':
        case 'VOLUME_PRESENT_ASSIGNMENT_MISSING': return 'INVESTIGATE_PARTIAL_STATE'
        case 'PERSISTED_STATE_GENUINELY_ABSENT': return 'RECONSTRUCTION_REQUIRED'
        default: return 'NONE'
    }
}
