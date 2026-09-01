/**
 * ViewerAssetLibrary — minimal PRODUCT UI for the MRT Pharma spatial planning
 * workflow: browse the PET/CT Asset Library, PLACE (enter click-to-place mode),
 * and inspect Placed Assets.
 *
 * Data flow (Sec 31/38): this component reads the ONE application-owned
 * SpatialAssetStore via subscription (useSyncExternalStore — event-driven, no
 * polling) and drives placement ONLY through the spatialAssetOverlay product
 * API. It never touches ScreenViewport / GraphicBuilder / Decorator / IModelApp
 * directly, and it never calls the DEV fixture paths (showCatalogPetCt).
 *
 * All Bentley/spatial modules are imported lazily by the overlay layer; this
 * file itself is Bentley-free except for the store type it observes.
 */
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react'
import type { AssetLibraryEntry, SpatialAssetSnapshot } from '../../domain/assets'
import {
    beginPlacementForLibraryEntry,
    cancelPlacement,
    getAssetLibrary,
    inspectPlacedAsset,
    spatialAssetStore,
    subscribeSpatialAssets,
} from './spatialAssetOverlay'
import { resolvePlacementStatus } from './placementStatus'

function useSpatialSnapshot(): SpatialAssetSnapshot {
    return useSyncExternalStore(subscribeSpatialAssets, () => spatialAssetStore.getSnapshot())
}

export function ViewerAssetLibrary() {
    const snapshot = useSpatialSnapshot()
    const library = useMemo(() => getAssetLibrary(), [])
    const [selectedEntry, setSelectedEntry] = useState<AssetLibraryEntry | null>(null)
    // `enterError` only surfaces a failure to ENTER placement mode (e.g. no
    // viewport); the normal Placing/Placed/Cancelled status is DERIVED from
    // store transitions so it can never go stale after the tool exits.
    const [enterError, setEnterError] = useState<string | null>(null)
    const [selectedPlacedId, setSelectedPlacedId] = useState<string | null>(null)

    const placementActive = snapshot.placementModeActive
    const activeIntent = snapshot.placementIntent

    // Product-placed instances = anything the user placed (USER_PLACED) plus any
    // fixtures currently present; the panel derives entirely from the store.
    const placed = snapshot.instances

    // Track the previous snapshot to derive success/cancel transitions. The
    // stale "Placing:" text bug was caused by a manually-set status string that
    // was never cleared when the Bentley placement tool exited; deriving status
    // from state transitions fixes it at the presentation seam only.
    const prevRef = useRef({ active: placementActive, count: placed.length, label: activeIntent?.displayLabel })
    const [derivedStatus, setDerivedStatus] = useState<string>('')

    useEffect(() => {
        const prev = prevRef.current
        const lastPlaced = placed[placed.length - 1]?.assetInstanceId
        const status = resolvePlacementStatus({
            active: placementActive,
            wasActive: prev.active,
            count: placed.length,
            prevCount: prev.count,
            displayLabel: activeIntent?.displayLabel ?? prev.label,
            lastPlacedInstanceId: lastPlaced,
        })
        // IDLE with no transition keeps the last resolved text (e.g. "Placed: …")
        // rather than blanking it; only meaningful transitions update it.
        if (status.phase !== 'IDLE') setDerivedStatus(status.text)
        prevRef.current = { active: placementActive, count: placed.length, label: activeIntent?.displayLabel ?? prev.label }
    }, [placementActive, placed, activeIntent])

    const status = enterError ?? derivedStatus

    const handleSelectEntry = useCallback((entry: AssetLibraryEntry) => {
        // Selecting an entry creates NO instance and does NOT enter placement mode.
        setSelectedEntry(entry)
        setEnterError(null)
    }, [])

    const handlePlace = useCallback(async () => {
        if (!selectedEntry) return
        setEnterError(null)
        const r = await beginPlacementForLibraryEntry(selectedEntry)
        // On success the derived status ("Placing…") takes over via the store
        // transition; only record a failure-to-enter here.
        setEnterError(r.ok ? null : `Placement failed: ${r.reason}`)
    }, [selectedEntry])

    const handleCancel = useCallback(async () => {
        setEnterError(null)
        await cancelPlacement()
        // Derived status resolves to "Placement cancelled" from the transition.
    }, [])

    return (
        <div className="mrt-asset-library" aria-label="MRT Pharma Asset Library">
            <h3>Asset Library</h3>
            <ul className="mrt-lib-tree">
                <li>
                    <span className="mrt-lib-group">Imaging</span>
                    <ul>
                        <li>
                            <span className="mrt-lib-group">PET/CT</span>
                            <ul>
                                {library.map((entry) => (
                                    <li key={entry.catalogRecordId}>
                                        <button
                                            type="button"
                                            className={selectedEntry?.catalogRecordId === entry.catalogRecordId ? 'mrt-lib-entry selected' : 'mrt-lib-entry'}
                                            aria-pressed={selectedEntry?.catalogRecordId === entry.catalogRecordId}
                                            onClick={() => handleSelectEntry(entry)}
                                        >
                                            <span className="mrt-lib-label">{entry.displayLabel}</span>
                                            <span className={`mrt-lib-geo ${entry.geometryAvailability === 'GEOMETRY_AVAILABLE' ? 'ok' : 'na'}`}>
                                                {entry.geometryAvailability === 'GEOMETRY_AVAILABLE'
                                                    ? (entry.geometryIsGeneric ? 'Generic representation available' : 'Manufacturer representation available')
                                                    : 'No representation'}
                                            </span>
                                        </button>
                                    </li>
                                ))}
                            </ul>
                        </li>
                    </ul>
                </li>
            </ul>

            {selectedEntry && (
                <div className="mrt-lib-detail">
                    <div className="mrt-lib-detail-row"><span>Equipment</span><strong>{selectedEntry.displayLabel}</strong></div>
                    <div className="mrt-lib-detail-row"><span>Catalog record</span><code>{selectedEntry.catalogRecordId}</code></div>
                    <div className="mrt-lib-detail-row"><span>Geometry</span><span>{selectedEntry.geometryStatusNote}</span></div>
                    <div className="mrt-lib-detail-row"><span>Catalog dimensions</span><span>{selectedEntry.dimensionStatus === 'NOT_CALIBRATED' ? 'Not calibrated' : 'Calibrated'}</span></div>
                    {!placementActive ? (
                        <button
                            type="button"
                            className="mrt-lib-place"
                            disabled={selectedEntry.geometryAvailability !== 'GEOMETRY_AVAILABLE'}
                            onClick={() => void handlePlace()}
                        >
                            PLACE IN MODEL
                        </button>
                    ) : (
                        <button type="button" className="mrt-lib-cancel" onClick={() => void handleCancel()}>CANCEL PLACEMENT</button>
                    )}
                </div>
            )}

            {placementActive && activeIntent && (
                <div className="mrt-placement-status" role="status">
                    <strong>Placing: {activeIntent.displayLabel}</strong>
                    <div>Click a location in the model to place.</div>
                    <div className="mrt-placement-hint">Right-click or Esc to cancel.</div>
                </div>
            )}

            {status && <p className="mrt-lib-status">{status}</p>}

            <h3>Placed Assets ({placed.length})</h3>
            {placed.length === 0 ? (
                <p className="mrt-lib-empty">No assets placed yet. Select equipment and PLACE IN MODEL.</p>
            ) : (
                <ul className="mrt-placed-list">
                    {placed.map((inst) => (
                        <li key={inst.assetInstanceId}>
                            <button
                                type="button"
                                className={selectedPlacedId === inst.assetInstanceId ? 'mrt-placed-item selected' : 'mrt-placed-item'}
                                onClick={() => setSelectedPlacedId(inst.assetInstanceId)}
                            >
                                <span className="mrt-placed-label">{inst.displayLabel}</span>
                                <span className="mrt-placed-meta">{inst.assetInstanceId} · {inst.roomAssignment.state} · {inst.installationState}</span>
                            </button>
                        </li>
                    ))}
                </ul>
            )}

            {selectedPlacedId && (
                <pre className="mrt-placed-inspect">{inspectPlacedAsset(selectedPlacedId)}</pre>
            )}
        </div>
    )
}
