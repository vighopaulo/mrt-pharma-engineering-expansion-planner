/**
 * ViewerSelectedVestibuleControl — EVI-MA-05A compact floating control for the
 * CURRENTLY SELECTED clinical logistics vestibule. Mirrors
 * ViewerSelectedEquipmentControl: it is NOT a second lifecycle — it derives
 * entirely from the authoritative `selectedVestibuleId` and dispatches to the
 * SAME overlay functions the 3D pick / (future) menu use. It guarantees Fit /
 * Hide-Show / Lock-Unlock / Delete are reachable the moment a vestibule is
 * selected, plus the required transport metadata (Service, Parent, MRT, PTS).
 */
import { useSyncExternalStore } from 'react'
import {
    deleteVestibule,
    fitViewToVestibule,
    getVestibuleInstances,
    getSelectedVestibuleId,
    lockVestibule,
    setVestibuleVisibility,
    subscribeClinicalProgram,
    unlockVestibule,
} from './spatialAssetOverlay'
import { serviceClassLabel } from './clinicalLogisticsVestibule'

/**
 * EVI-MA-02E composite-snapshot doctrine: fold the selected vestibule's hidden +
 * lifecycle into the snapshot so the control re-renders on Hide/Show/Lock, not
 * only when the selected id changes.
 */
function selectedVestibuleSnapshot(): string {
    const id = getSelectedVestibuleId()
    if (!id) return ''
    const v = getVestibuleInstances().find((x) => x.vestibuleInstanceId === id)
    if (!v) return `${id}|missing`
    return `${id}|${v.hidden ? 'hidden' : 'visible'}|${v.lifecycleState}`
}

export function ViewerSelectedVestibuleControl() {
    useSyncExternalStore(subscribeClinicalProgram, selectedVestibuleSnapshot)

    const selectedId = getSelectedVestibuleId()
    if (!selectedId) return null
    const v = getVestibuleInstances().find((x) => x.vestibuleInstanceId === selectedId)
    if (!v) return null

    const isLocked = v.lifecycleState === 'LOCKED'
    const isHidden = v.hidden ?? false
    const title = `${serviceClassLabel(v.serviceClass)} Logistics Vestibule`

    // Transport-port metadata (both ports belong to this ONE vestibule).
    const mrt = v.transportPorts.find((p) => p.transportFamily === 'MRT')
    const pts = v.transportPorts.find((p) => p.transportFamily === 'PTS')
    const mrtText = mrt ? `${mrt.status === 'UNCONNECTED' ? 'Unconnected' : 'Future Network'}` : '—'
    const ptsText = pts
        ? `${pts.ptsQualification === 'RADIOPHARMACEUTICAL_QUALIFIED' ? 'Radiopharmaceutical Qualified' : 'Conventional Clinical'} · ${pts.status === 'UNCONNECTED' ? 'Unconnected' : 'Future Network'}`
        : '—'

    return (
        <div className="mrt-selected-equipment mrt-selected-vestibule" role="region" aria-label="Selected vestibule">
            <div className="mrt-selected-equipment-title">
                {title}{isHidden ? ' · Hidden' : ''}
            </div>
            <div className="mrt-selected-vestibule-meta">
                <div><span>Service</span>{serviceClassLabel(v.serviceClass)}</div>
                <div><span>Parent</span>{v.parentBimSpaceId}</div>
                <div><span>MRT</span>{mrtText}</div>
                <div><span>PTS</span>{ptsText}</div>
            </div>
            <div className="mrt-selected-equipment-actions">
                <button type="button" onClick={() => void fitViewToVestibule(selectedId)}>Fit</button>
                <button type="button" onClick={() => setVestibuleVisibility(selectedId, isHidden)}>{isHidden ? 'Show' : 'Hide'}</button>
                <button type="button" onClick={() => (isLocked ? unlockVestibule(selectedId) : lockVestibule(selectedId))}>{isLocked ? 'Unlock' : 'Lock'}</button>
                <button
                    type="button"
                    className="mrt-selected-equipment-delete"
                    disabled={isLocked}
                    title={isLocked ? 'Unlock before deleting' : 'Delete this vestibule (cyclotron + BIM wall kept)'}
                    onClick={() => { deleteVestibule(selectedId) }}
                >
                    Delete
                </button>
            </div>
        </div>
    )
}
