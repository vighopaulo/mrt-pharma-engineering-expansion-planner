/**
 * ViewerSelectedEquipmentControl — EVI-MA-02D compact floating control for the
 * CURRENTLY SELECTED equipment. It guarantees Fit / Hide-Show / Lock-Unlock /
 * Delete are ALWAYS reachable the moment an equipment instance is selected —
 * WITHOUT scrolling the Clinical Program panel and WITHOUT depending on the
 * right-click context menu. It is not a second lifecycle: it derives entirely
 * from the authoritative `selectedEquipmentId` and dispatches to the SAME
 * overlay functions the card / right-click menu / keyboard use.
 */
import { useSyncExternalStore } from 'react'
import {
    createRadiopharmacyVestibuleForCyclotron,
    deleteEquipment,
    fitViewToEquipment,
    fitViewToVestibule,
    getEquipmentInstances,
    getRadiopharmacyVestibuleForRoom,
    getSelectedEquipmentId,
    selectVestibule,
    lockEquipment,
    setEquipmentVisibility,
    subscribeClinicalProgram,
    unlockEquipment,
} from './spatialAssetOverlay'
import { canonicalEquipmentById } from './canonicalEquipmentCatalog'

/**
 * EVI-MA-05A — CREATE RADIOPHARMACY VESTIBULE from the selected cyclotron. Runs
 * the whole live pipeline in the overlay (resolve cyclotron → parent room → wall
 * → seed → validate → create ONE instance → persist → select → Fit). Duplicate
 * (VESTIBULE_ALREADY_EXISTS) selects + Fits the existing one. Honest failures
 * (NO_DEFENSIBLE_WALL / collision) surface without creating anything.
 */
async function onCreateRadiopharmacyVestibule(cyclotronId: string): Promise<void> {
    const res = await createRadiopharmacyVestibuleForCyclotron(cyclotronId)
    if (res.ok) {
        await fitViewToVestibule(res.vestibuleInstanceId)
    } else if (res.reason === 'VESTIBULE_ALREADY_EXISTS' && res.existingVestibuleId) {
        // One active radiopharmacy vestibule per production context — focus it.
        await fitViewToVestibule(res.existingVestibuleId)
    }
    // Other reasons (NO_DEFENSIBLE_WALL / VESTIBULE_COLLISION / ROOM_TOO_SHORT)
    // create nothing; the button remains available to retry after adjustment.
}

/**
 * EVI-MA-02E — composite snapshot so the control re-renders on ANY relevant
 * change to the SELECTED instance, not just when the selected id changes.
 *
 * ROOT CAUSE (fixed): subscribing with `getSelectedEquipmentId` alone bailed out
 * of re-render after Hide because the id is unchanged — so `inst.hidden` read
 * below stayed stale and the button kept saying "Hide". The snapshot now folds
 * in the selected instance's `hidden` + `lifecycleState`, so useSyncExternalStore
 * detects the change and re-renders. Still derives from the ONE authoritative
 * selectedEquipmentId + current equipment collection (no second visibility state).
 */
function selectedEquipmentSnapshot(): string {
    const id = getSelectedEquipmentId()
    if (!id) return ''
    const inst = getEquipmentInstances().find((e) => e.id === id)
    if (!inst) return `${id}|missing`
    return `${id}|${inst.hidden ? 'hidden' : 'visible'}|${inst.lifecycleState}`
}

export function ViewerSelectedEquipmentControl() {
    // The composite snapshot changes whenever selection, hidden, or lock state
    // of the selected instance changes -> the control always re-renders.
    useSyncExternalStore(subscribeClinicalProgram, selectedEquipmentSnapshot)

    const selectedId = getSelectedEquipmentId()
    if (!selectedId) return null
    // Resolve the CURRENT authoritative instance every render (never a stale ref).
    const inst = getEquipmentInstances().find((e) => e.id === selectedId)
    if (!inst) return null

    const canonical = canonicalEquipmentById(inst.canonicalEquipmentId)
    const title = canonical ? `${canonical.manufacturer} ${canonical.model}` : inst.displayLabel
    const isLocked = inst.lifecycleState === 'LOCKED'
    const isHidden = inst.hidden ?? false
    // EVI-MA-05A — the logistics action is offered only for a CYCLOTRON (the
    // Radiopharmacy production context), directly on this control (no scrolling).
    const isCyclotron = inst.canonicalClass === 'CYCLOTRON'
    // EVI-MA-07 §19 — no duplicate CTA: if a Radiopharmacy vestibule already
    // exists in this cyclotron's room, offer "Select" (+ Fit) instead of "Create".
    const existingVestibuleId = isCyclotron ? getRadiopharmacyVestibuleForRoom(inst.parentBimSpaceId) : undefined

    return (
        <div className="mrt-selected-equipment" role="region" aria-label="Selected equipment">
            <div className="mrt-selected-equipment-title">
                {title}{isHidden ? ' · Hidden' : ''}
            </div>
            <div className="mrt-selected-equipment-actions">
                <button type="button" onClick={() => void fitViewToEquipment(selectedId)}>Fit</button>
                {/* hidden===false -> "Hide" -> setVisibility(false); hidden===true
                    -> "Show" -> setVisibility(true). One authoritative field. Lock
                    does NOT gate Show (user must never be trapped with hidden eqpt). */}
                <button type="button" onClick={() => setEquipmentVisibility(selectedId, isHidden)}>{isHidden ? 'Show' : 'Hide'}</button>
                <button type="button" onClick={() => (isLocked ? unlockEquipment(selectedId) : void lockEquipment(selectedId))}>{isLocked ? 'Unlock' : 'Lock'}</button>
                <button
                    type="button"
                    className="mrt-selected-equipment-delete"
                    disabled={isLocked}
                    title={isLocked ? 'Unlock before deleting' : 'Delete this equipment (BIM room kept)'}
                    onClick={() => { deleteEquipment(selectedId) }}
                >
                    Delete
                </button>
            </div>
            {isCyclotron && (
                <div className="mrt-selected-equipment-logistics">
                    {existingVestibuleId ? (
                        <button
                            type="button"
                            className="mrt-create-vestibule"
                            title="Select and fit the existing Radiopharmacy Logistics Vestibule for this room"
                            onClick={() => { selectVestibule(existingVestibuleId); void fitViewToVestibule(existingVestibuleId) }}
                        >
                            Select Radiopharmacy Vestibule
                        </button>
                    ) : (
                        <button
                            type="button"
                            className="mrt-create-vestibule"
                            title="Place a wall-integrated Radiopharmacy Logistics Vestibule in this cyclotron's room"
                            onClick={() => { void onCreateRadiopharmacyVestibule(selectedId) }}
                        >
                            Create Radiopharmacy Vestibule
                        </button>
                    )}
                </div>
            )}
        </div>
    )
}
