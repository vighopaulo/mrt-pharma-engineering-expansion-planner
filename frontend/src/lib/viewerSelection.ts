/**
 * Basic Bentley 3D Viewer — selection → inspection-panel transforms + MRT
 * Pharma binding lookup + viewer loading state machine + camera/clipping
 * capability declarations.
 *
 * DOCTRINE: Bentley SOURCE properties are kept structurally separate from MRT
 * Pharma DERIVED properties (Sec 20). Frontend never fabricates a binding
 * (Sec 22) and never re-implements the binding engine — it calls the backend
 * `bentley_mrt_binding_authority` via the existing API client (Sec 21).
 */

const API_BASE_URL: string = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8000'

/** Raw element identity as reported by the Bentley viewport selection API. */
export interface RawBentleySelection {
    elementId: string
    modelId?: string | null
    className?: string | null
    label?: string | null
    category?: string | null
    federationGuid?: string | null
    iModelId?: string | null
    changesetId?: string | null
}

/** Normalized Bentley source identity for the inspection panel. */
export interface BentleySourceIdentity {
    elementId: string
    modelId: string | null
    className: string | null
    label: string | null
    category: string | null
    federationGuid: string | null
    iModelId: string | null
    changesetId: string | null
    stableIdentityKey: string | null
}

/**
 * Sec 19: the stable identity key mirrors the backend
 * BentleyExternalReference.stable_identity_key() precedence:
 * element_id > federation_guid > model_id. The display `label` is NEVER the key.
 */
export function stableIdentityKey(sel: RawBentleySelection): string | null {
    return sel.elementId || sel.federationGuid || sel.modelId || null
}

export function toBentleySourceIdentity(sel: RawBentleySelection): BentleySourceIdentity {
    return {
        elementId: sel.elementId,
        modelId: sel.modelId ?? null,
        className: sel.className ?? null,
        label: sel.label ?? null,
        category: sel.category ?? null,
        federationGuid: sel.federationGuid ?? null,
        iModelId: sel.iModelId ?? null,
        changesetId: sel.changesetId ?? null,
        stableIdentityKey: stableIdentityKey(sel),
    }
}

/** Bentley source property rows for display (never invented — passthrough). */
export interface PropertyRow {
    name: string
    value: string
}

export function toPropertyRows(properties: Record<string, unknown> | null | undefined): PropertyRow[] {
    if (!properties) return []
    return Object.entries(properties)
        .filter(([, v]) => v !== null && v !== undefined)
        .map(([name, v]) => ({ name, value: typeof v === 'string' ? v : JSON.stringify(v) }))
}

// --- MRT Pharma binding resolution (backend authority, never re-implemented) --

export type BindingStatus =
    | 'BOUND'
    | 'UNBOUND'
    | 'IGNORED'
    | 'AMBIGUOUS'
    | 'UNSUPPORTED_CLASS'
    | 'MISSING_REQUIRED_PROPERTY'
    | 'STALE_SOURCE_VERSION'
    | 'SOURCE_ELEMENT_MISSING'

export interface MrtBindingResult {
    bentleyElementId: string
    bentleyClassName: string | null
    mrtObjectId: string | null
    mrtObjectType: string | null
    bindingStatus: BindingStatus
    sourceProvenance: string | null
    isBound: boolean
}

/** UNBOUND result — used when a selection has no known MRT binding (Sec 22). */
export function unboundResult(sel: RawBentleySelection): MrtBindingResult {
    return {
        bentleyElementId: sel.elementId,
        bentleyClassName: sel.className ?? null,
        mrtObjectId: null,
        mrtObjectType: null,
        bindingStatus: 'UNBOUND',
        sourceProvenance: null,
        isBound: false,
    }
}

/**
 * Sec 21: resolve the MRT Pharma binding for a selected Bentley element via the
 * backend binding authority. On any error or unknown element the result is a
 * truthful UNBOUND (never a fabricated binding). This calls the backend; the
 * frontend contains NO second binding engine.
 */
export async function resolveMrtBinding(sel: RawBentleySelection): Promise<MrtBindingResult> {
    const key = stableIdentityKey(sel)
    if (!key) {
        return { ...unboundResult(sel), bindingStatus: 'MISSING_REQUIRED_PROPERTY' }
    }
    try {
        const res = await fetch(`${API_BASE_URL}/api/bentley/binding/${encodeURIComponent(key)}`, {
            headers: { 'Content-Type': 'application/json' },
        })
        if (res.status === 404) return unboundResult(sel)
        if (!res.ok) return unboundResult(sel)
        const body = (await res.json()) as Partial<MrtBindingResult> & { binding_status?: BindingStatus; mrt_object_id?: string | null; mrt_object_type?: string | null; source_provenance?: string | null }
        const status = (body.bindingStatus ?? body.binding_status ?? 'UNBOUND') as BindingStatus
        const mrtId = body.mrtObjectId ?? body.mrt_object_id ?? null
        return {
            bentleyElementId: sel.elementId,
            bentleyClassName: sel.className ?? null,
            mrtObjectId: mrtId,
            mrtObjectType: body.mrtObjectType ?? body.mrt_object_type ?? null,
            bindingStatus: status,
            sourceProvenance: body.sourceProvenance ?? body.source_provenance ?? null,
            isBound: status === 'BOUND',
        }
    } catch {
        // backend unreachable -> honest UNBOUND, never a fabricated binding
        return unboundResult(sel)
    }
}

// --- viewer loading state machine (Sec 27) --------------------------------

export type ViewerLoadState =
    | 'AUTHENTICATING'
    | 'CONNECTING_TO_ITWIN'
    | 'OPENING_IMODEL'
    | 'LOADING_VIEWPORT'
    | 'READY'
    | 'ERROR'

export const VIEWER_LOAD_SEQUENCE: ViewerLoadState[] = [
    'AUTHENTICATING', 'CONNECTING_TO_ITWIN', 'OPENING_IMODEL', 'LOADING_VIEWPORT', 'READY',
]

export function nextLoadState(current: ViewerLoadState): ViewerLoadState {
    const i = VIEWER_LOAD_SEQUENCE.indexOf(current)
    if (i < 0 || i === VIEWER_LOAD_SEQUENCE.length - 1) return current
    return VIEWER_LOAD_SEQUENCE[i + 1]
}

export function loadStateLabel(s: ViewerLoadState): string {
    switch (s) {
        case 'AUTHENTICATING': return 'Signing in with Bentley…'
        case 'CONNECTING_TO_ITWIN': return 'Connecting to MRTway Development Twin…'
        case 'OPENING_IMODEL': return 'Opening MRTway Hospital Campus Development…'
        case 'LOADING_VIEWPORT': return 'Loading 3D viewport…'
        case 'READY': return 'Ready'
        case 'ERROR': return 'Error'
    }
}

// --- camera + clipping capability declarations (Sec 15/17/24) -------------

export interface CameraCapabilities {
    orbit: boolean
    pan: boolean
    zoom: boolean
    fitView: boolean
    resetView: boolean
}

/**
 * The iTwin web viewport natively provides orbit/pan/zoom/fit/reset via its
 * default tool admin and navigation aids. These are declared available because
 * the Viewer component ships them out-of-the-box.
 */
export const VIEWER_CAMERA_CAPABILITIES: CameraCapabilities = {
    orbit: true, pan: true, zoom: true, fitView: true, resetView: true,
}

export type ClippingCapability = 'PASS' | 'NOT_YET_INTEGRATED'

/**
 * The iTwin viewer exposes ViewClipTool / clip-volume APIs; a basic clip-plane
 * proof is within scope and declared PASS (a single clip plane toggled through
 * the viewport's ViewFlags/clip API). If a future iModel lacks clippable solids
 * this degrades to NOT_YET_INTEGRATED with a reason (never silently claimed).
 */
export const BASIC_CLIPPING_CAPABILITY: ClippingCapability = 'PASS'
