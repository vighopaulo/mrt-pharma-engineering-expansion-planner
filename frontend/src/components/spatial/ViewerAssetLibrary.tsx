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
import type { AssetLibraryEntry, SpatialAssetSnapshot, SpatialAssociationResult } from '../../domain/assets'
import { formatAssociationSlotLabel } from '../../domain/assets'
import {
    beginPlacementForLibraryEntry,
    cancelPlacement,
    getAssetLibrary,
    inspectPlacedAsset,
    spatialAssetStore,
    subscribeSpatialAssets,
} from './spatialAssetOverlay'
import {
    beginMoveForAsset,
    cancelMove,
    deleteAsset,
    ensureDirectManipulationReady,
    getAssociationForInstance,
    isSemanticsLoaded,
    refreshModelSemantics,
    rotateAssetYaw,
    selectAsset,
} from './spatialAssetOverlay'
import { resolveMoveStatus, resolvePlacementStatus } from './placementStatus'

/**
 * Render a floor/room association slot. Delegates to the SINGLE shared domain
 * formatter (formatAssociationSlotLabel) so the Placed Assets UI and the DEV
 * inspector can never disagree about the same result. Never prints bare
 * "ASSIGNED" — the domain invariant guarantees a reference when ASSIGNED.
 */
function formatAssociationSlot(assoc: SpatialAssociationResult | undefined, slot: 'floor' | 'room'): string {
    if (!assoc) return '—'
    return formatAssociationSlotLabel(assoc, slot)
}

function useSpatialSnapshot(): SpatialAssetSnapshot {
    return useSyncExternalStore(subscribeSpatialAssets, () => spatialAssetStore.getSnapshot())
}

export function ViewerAssetLibrary() {
    const snapshot = useSpatialSnapshot()
    const library = useMemo(() => getAssetLibrary(), [])
    const [selectedEntry, setSelectedEntry] = useState<AssetLibraryEntry | null>(null)
    // `enterError` only surfaces a failure to ENTER placement/move mode (e.g.
    // no viewport, or another interaction active); the normal
    // Placing/Placed/Cancelled and Moving/Moved/Cancelled statuses are DERIVED
    // from store transitions so they can never go stale after a tool exits.
    const [enterError, setEnterError] = useState<string | null>(null)
    // A bounded local status for the immediate rotate action (no Bentley tool).
    const [rotateStatus, setRotateStatus] = useState<string>('')

    const placementActive = snapshot.placementModeActive
    const activeIntent = snapshot.placementIntent
    const moveActive = snapshot.moveModeActive
    const moveIntent = snapshot.moveIntent
    const interaction = snapshot.interaction
    const dragActive = snapshot.dragActive

    // Product-placed instances = anything the user placed (USER_PLACED) plus any
    // fixtures currently present; the panel derives entirely from the store.
    const placed = snapshot.instances
    // Selection is store-owned; the panel resolves the AssetInstance from it.
    const selectedPlacedId = snapshot.selectedAssetInstanceId
    const selectedIdSet = useMemo(() => new Set(snapshot.selectedAssetInstanceIds), [snapshot.selectedAssetInstanceIds])
    const selectedInstance = selectedPlacedId ? placed.find((i) => i.assetInstanceId === selectedPlacedId) : undefined

    // Derived BIM spatial association for the selected asset (observational —
    // never mutates position/identity). Recomputed from the COMMITTED position
    // only: skipped while a drag/rotation preview is active so authoritative
    // floor/room never changes per preview frame. Semantics are loaded once.
    const [association, setAssociation] = useState<SpatialAssociationResult | undefined>(undefined)
    const committedPos = selectedInstance
        ? `${selectedInstance.transform.position.x},${selectedInstance.transform.position.y},${selectedInstance.transform.position.z}`
        : ''
    useEffect(() => {
        let cancelled = false
        if (!selectedPlacedId) { setAssociation(undefined); return }
        // Do not recompute authoritative association mid-preview.
        if (dragActive || snapshot.rotationActive) return
        void (async () => {
            // Ensure semantics are loaded before computing so the UI never renders
            // an association against empty semantics (which would disagree with the
            // DEV inspector after its own refresh). Both consumers thus compute from
            // the SAME shared cache + generation via the SAME getAssociationForInstance seam.
            if (!isSemanticsLoaded()) await refreshModelSemantics()
            if (cancelled) return
            setAssociation(getAssociationForInstance(selectedPlacedId))
        })()
        return () => { cancelled = true }
        // committedPos is included so a committed drag/move re-associates.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedPlacedId, committedPos, dragActive, snapshot.rotationActive])

    // Track the previous snapshot to derive success/cancel transitions for BOTH
    // placement and move. The stale "Placing:"/"Moving:" text bug is avoided by
    // deriving status from state transitions rather than a manually-set string.
    const prevRef = useRef({
        placementActive,
        count: placed.length,
        placementLabel: activeIntent?.displayLabel,
        moveActive,
        moveLabel: moveIntent?.displayLabel,
        moveTargetId: moveIntent?.assetInstanceId,
        movePrevPos: moveIntent?.previousPosition,
    })
    const [derivedStatus, setDerivedStatus] = useState<string>('')

    useEffect(() => {
        const prev = prevRef.current
        // Placement status.
        const lastPlaced = placed[placed.length - 1]?.assetInstanceId
        const pStatus = resolvePlacementStatus({
            active: placementActive,
            wasActive: prev.placementActive,
            count: placed.length,
            prevCount: prev.count,
            displayLabel: activeIntent?.displayLabel ?? prev.placementLabel,
            lastPlacedInstanceId: lastPlaced,
        })
        if (pStatus.phase !== 'IDLE') setDerivedStatus(pStatus.text)

        // Move status. On a move-mode end transition, decide success vs cancel by
        // whether the bound instance's position actually changed.
        if (prev.moveActive && !moveActive) {
            const targetId = prev.moveTargetId
            const target = targetId ? placed.find((i) => i.assetInstanceId === targetId) : undefined
            const prevPos = prev.movePrevPos
            const positionChanged = !!(target && prevPos && (
                target.transform.position.x !== prevPos.x ||
                target.transform.position.y !== prevPos.y ||
                target.transform.position.z !== prevPos.z
            ))
            const mStatus = resolveMoveStatus({
                active: false,
                wasActive: true,
                displayLabel: prev.moveLabel,
                assetInstanceId: targetId,
                positionChanged,
            })
            if (mStatus.phase !== 'IDLE') setDerivedStatus(mStatus.text)
        } else if (moveActive) {
            const mStatus = resolveMoveStatus({ active: true, wasActive: prev.moveActive, displayLabel: moveIntent?.displayLabel })
            setDerivedStatus(mStatus.text)
        }

        prevRef.current = {
            placementActive,
            count: placed.length,
            placementLabel: activeIntent?.displayLabel ?? prev.placementLabel,
            moveActive,
            moveLabel: moveIntent?.displayLabel ?? prev.moveLabel,
            moveTargetId: moveIntent?.assetInstanceId ?? prev.moveTargetId,
            movePrevPos: moveIntent?.previousPosition ?? prev.movePrevPos,
        }
    }, [placementActive, placed, activeIntent, moveActive, moveIntent])

    const status = enterError || rotateStatus || derivedStatus

    // Arm the bounded direct-manipulation tool (click scanner to select, drag to
    // move) whenever there are placed assets and no other interaction owns the
    // viewport. Idempotent; re-arms when the interaction returns to IDLE (e.g.
    // after a command MOVE/placement completes).
    useEffect(() => {
        if (placed.length > 0 && interaction === 'IDLE') {
            void ensureDirectManipulationReady()
        }
    }, [placed.length, interaction])

    const handleSelectEntry = useCallback((entry: AssetLibraryEntry) => {
        // Selecting an entry creates NO instance and does NOT enter placement mode.
        setSelectedEntry(entry)
        setEnterError(null)
    }, [])

    const handlePlace = useCallback(async () => {
        if (!selectedEntry) return
        setEnterError(null)
        setRotateStatus('')
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

    const handleSelectPlaced = useCallback((assetInstanceId: string) => {
        selectAsset(assetInstanceId)
        setRotateStatus('')
        setEnterError(null)
    }, [])

    const handleMove = useCallback(async () => {
        if (!selectedPlacedId) return
        setEnterError(null)
        setRotateStatus('')
        const r = await beginMoveForAsset(selectedPlacedId)
        // On success the derived "Moving…" status takes over via the transition.
        setEnterError(r.ok ? null : `Move failed: ${r.reason}`)
    }, [selectedPlacedId])

    const handleCancelMove = useCallback(async () => {
        setEnterError(null)
        await cancelMove()
        // Derived status resolves to "Move cancelled" from the transition.
    }, [])

    const handleRotate = useCallback((deltaDegrees: number) => {
        if (!selectedPlacedId) return
        setEnterError(null)
        const r = rotateAssetYaw(selectedPlacedId, deltaDegrees)
        setRotateStatus(r.ok ? `Rotated: ${r.assetInstanceId} → ${r.yaw}°` : `Rotate failed: ${r.reason}`)
    }, [selectedPlacedId])

    const handleDelete = useCallback(() => {
        if (!selectedInstance) return
        setEnterError(null)
        // Explicit deliberate confirmation before destructive delete.
        const label = `${selectedInstance.displayLabel} (${selectedInstance.assetInstanceId})`
        const confirmed = typeof window !== 'undefined' && typeof window.confirm === 'function'
            ? window.confirm(`Delete ${selectedInstance.displayLabel}?\n${selectedInstance.assetInstanceId}`)
            : false
        if (!confirmed) {
            setRotateStatus(`Delete cancelled: ${label}`)
            return
        }
        const r = deleteAsset(selectedInstance.assetInstanceId)
        setRotateStatus(r.ok ? `Deleted: ${r.removedInstanceId}` : `Delete failed: ${r.reason}`)
    }, [selectedInstance])

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

            {moveActive && moveIntent && (
                <div className="mrt-placement-status" role="status">
                    <strong>Moving: {moveIntent.displayLabel}</strong>
                    <div>Click a new location in the model.</div>
                    <div className="mrt-placement-hint">Right-click or Esc to cancel.</div>
                </div>
            )}

            {status && <p className="mrt-lib-status">{status}</p>}

            <h3>Placed Assets ({placed.length})</h3>
            {selectedIdSet.size > 1 && (
                <p className="mrt-selection-status" role="status">{selectedIdSet.size} assets selected</p>
            )}
            {placed.length === 0 ? (
                <p className="mrt-lib-empty">No assets placed yet. Select equipment and PLACE IN MODEL.</p>
            ) : (
                <ul className="mrt-placed-list">
                    {placed.map((inst) => {
                        const inMulti = selectedIdSet.has(inst.assetInstanceId)
                        const isSole = selectedPlacedId === inst.assetInstanceId
                        const cls = isSole ? 'mrt-placed-item selected'
                            : inMulti ? 'mrt-placed-item multi-selected'
                                : 'mrt-placed-item'
                        return (
                            <li key={inst.assetInstanceId}>
                                <button
                                    type="button"
                                    className={cls}
                                    aria-pressed={inMulti}
                                    onClick={() => handleSelectPlaced(inst.assetInstanceId)}
                                >
                                    <span className="mrt-placed-label">{inst.displayLabel}</span>
                                    <span className="mrt-placed-meta">{inst.assetInstanceId} · {inst.roomAssignment.state} · {inst.installationState}</span>
                                </button>
                            </li>
                        )
                    })}
                </ul>
            )}

            {selectedInstance && (
                <div className="mrt-placed-detail">
                    <p className="mrt-manip-hint">
                        {dragActive
                            ? 'Dragging — release to place, right-click / Esc to cancel'
                            : 'Selected. Drag the scanner in the model to move it, or use the controls below.'}
                    </p>
                    {/* Controlled manipulation for the selected asset. Identity is
                        immutable; only the transform changes. Command MOVE/ROTATE
                        remain as the deterministic fallback alongside fluid drag. */}
                    <div className="mrt-manip-controls">
                        {!moveActive ? (
                            <button
                                type="button"
                                className="mrt-manip-move"
                                disabled={interaction !== 'IDLE'}
                                onClick={() => void handleMove()}
                            >
                                MOVE
                            </button>
                        ) : (
                            <button type="button" className="mrt-manip-cancel" onClick={() => void handleCancelMove()}>CANCEL MOVE</button>
                        )}
                        <button
                            type="button"
                            className="mrt-manip-rot"
                            disabled={interaction !== 'IDLE'}
                            onClick={() => handleRotate(-90)}
                        >
                            ROTATE LEFT 90°
                        </button>
                        <button
                            type="button"
                            className="mrt-manip-rot"
                            disabled={interaction !== 'IDLE'}
                            onClick={() => handleRotate(90)}
                        >
                            ROTATE RIGHT 90°
                        </button>
                        {/* Controlled delete of the selected USER_PLACED asset.
                            Explicit confirmation; disabled while manipulating. */}
                        {selectedInstance.spatialSource === 'USER_PLACED' && (
                            <button
                                type="button"
                                className="mrt-manip-delete"
                                disabled={interaction !== 'IDLE'}
                                onClick={() => handleDelete()}
                            >
                                DELETE
                            </button>
                        )}
                    </div>
                    {/* BIM spatial association (observational; from committed
                        position). Distinguishes honest statuses — a missing room
                        because the BIM lacks room semantics is NOT the same as a
                        room that simply doesn't contain the point. */}
                    <div className="mrt-spatial-assoc">
                        <div className="mrt-lib-detail-row"><span>Floor</span><span>{formatAssociationSlot(association, 'floor')}</span></div>
                        <div className="mrt-lib-detail-row"><span>Room</span><span>{formatAssociationSlot(association, 'room')}</span></div>
                        <div className="mrt-lib-detail-row"><span>Source</span><span>{association ? association.provenance.source : '—'}</span></div>
                        <div className="mrt-lib-detail-row"><span>Method</span><span>{association ? association.provenance.method : '—'}</span></div>
                    </div>
                    <pre className="mrt-placed-inspect">{inspectPlacedAsset(selectedInstance.assetInstanceId)}</pre>
                </div>
            )}
        </div>
    )
}
