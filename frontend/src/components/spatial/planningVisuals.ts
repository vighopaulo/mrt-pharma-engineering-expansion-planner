/**
 * planningVisuals — pure, Bentley-free visual-state decisions for the MRT Pharma
 * planning product. Separates PRESENTATION (mode, equipment/selection visual
 * state, developer-control visibility) from engineering/interaction authority.
 * None of these functions mutate AssetInstance identity, position, rotation, or
 * any domain state — they only decide how things are shown.
 */

/** Product viewer mode. Default is NORMAL_PLANNING; DEVELOPER is opt-in. */
export type ViewerMode = 'NORMAL_PLANNING' | 'DEVELOPER'

export const DEFAULT_VIEWER_MODE: ViewerMode = 'NORMAL_PLANNING'

/** Visibility decisions derived purely from the current viewer mode. */
export interface DeveloperVisibility {
    /** The block of DEV inspect/show/hide buttons (kept OUT of the viewport in normal mode). */
    devControlsVisible: boolean
    /** Raw engineering object dump (ids/definition/geometry ids) in the product panel. */
    rawEngineeringDumpVisible: boolean
    /** The Developer Inspector panel is available (it is only useful in DEVELOPER mode). */
    developerInspectorAvailable: boolean
}

/** Resolve what developer-only surfaces are visible for a given mode. */
export function resolveDeveloperVisibility(mode: ViewerMode): DeveloperVisibility {
    const dev = mode === 'DEVELOPER'
    return {
        devControlsVisible: dev,
        rawEngineeringDumpVisible: dev,
        developerInspectorAvailable: dev,
    }
}

/** Whether the large DEV button block should render over/near the viewport. */
export function devButtonBlockVisibleInMode(mode: ViewerMode): boolean {
    return mode === 'DEVELOPER'
}

// ---------------------------------------------------------------------------
// Equipment + selection visual state (restrained, clinical language)
// ---------------------------------------------------------------------------

/** Per-asset visual state, driven by selection/hover/rotation — NOT engineering. */
export type EquipmentVisualState =
    | 'DEFAULT' // unselected, idle
    | 'SELECTED' // sole selected
    | 'MULTI_SELECTED' // one of several selected
    | 'HOVERED' // pointer over (not selected)
    | 'ROTATING' // active object-attached rotation

/**
 * Resolve an asset's visual state from interaction inputs. Selection/rotation
 * take precedence over hover. Pure; never touches domain state.
 */
export function resolveEquipmentVisualState(p: {
    isSelected: boolean
    selectedCount: number
    isHovered: boolean
    isRotating: boolean
}): EquipmentVisualState {
    if (p.isRotating && p.isSelected) return 'ROTATING'
    if (p.isSelected) return p.selectedCount > 1 ? 'MULTI_SELECTED' : 'SELECTED'
    if (p.isHovered) return 'HOVERED'
    return 'DEFAULT'
}

/**
 * Restrained selection emphasis for a visual state: an outline weight only
 * (no bright rings, no opaque overlays). Weight 1 = default; heavier = selected.
 * Returns whether the asset should draw a selection outline and its line weight.
 */
export function resolveSelectionVisualState(state: EquipmentVisualState): { outline: boolean; lineWeight: number } {
    switch (state) {
        case 'SELECTED':
        case 'ROTATING':
            return { outline: true, lineWeight: 3 }
        case 'MULTI_SELECTED':
            return { outline: true, lineWeight: 2 }
        case 'HOVERED':
            return { outline: true, lineWeight: 2 }
        default:
            return { outline: false, lineWeight: 1 }
    }
}

// ---------------------------------------------------------------------------
// Room / spatial-volume visual policy (BuildingSpatial:Space etc.)
// ---------------------------------------------------------------------------

/**
 * How the room/space VOLUME semantics (BuildingSpatial:Space,
 * SpatialComposition composite volumes) should be presented. These elements are
 * planning DATA (room association + developer inspection), not the primary
 * architectural surfaces, so they must NOT dominate the normal product view as
 * overlapping translucent grey cuboids.
 *
 * - SUBDUED_OR_HIDDEN: normal planning mode — the volume geometry is suppressed
 *   (view-only, e.g. viewport never-drawn set) so the hospital reads cleanly.
 *   The underlying BIM elements + their semantics are preserved.
 * - FULL: developer mode — the raw spatial volumes are shown for inspection.
 */
export type RoomVisualPolicy = 'SUBDUED_OR_HIDDEN' | 'FULL'

/**
 * Resolve the room/space volume visual policy for a viewer mode. Pure; decides
 * presentation only. It does NOT delete, mutate, or reclassify any BIM element
 * and does NOT change spatial-association logic.
 */
export function resolveRoomVisualPolicy(mode: ViewerMode): RoomVisualPolicy {
    return mode === 'DEVELOPER' ? 'FULL' : 'SUBDUED_OR_HIDDEN'
}

/**
 * In NORMAL_PLANNING mode the room/space volumes must NOT be the dominant
 * translucent volume. Convenience predicate for the room-visual-policy test and
 * for asserting the corrected default product appearance.
 */
export function roomVolumesDominateInMode(mode: ViewerMode): boolean {
    return resolveRoomVisualPolicy(mode) === 'FULL'
}
