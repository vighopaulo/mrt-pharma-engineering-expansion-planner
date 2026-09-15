/**
 * placementDarkeningDiagnostic — EVI-MA-07A.1.
 *
 * DEVELOPER-ONLY, READ-ONLY live root-cause diagnostic for the reported
 * "viewport stays dark after placement is cancelled" failure. It captures, at a
 * requested moment (NORMAL / PLACEMENT_ACTIVE / AFTER_CANCEL_DARK), the evidence
 * the correction spec (EVI-MA-07A.1 §2–§11) demands, WITHOUT changing any state:
 *
 *   - placement/application state (read from the store, not inferred visually);
 *   - the real Bentley viewport host + canvas element identity + rect + center;
 *   - document.elementsFromPoint() stack at the viewport center, with the
 *     darkening-relevant computed styles for every element in the stack;
 *   - all FULL-VIEWPORT / FULL-WINDOW elements (any name — not just backdrop/
 *     overlay/modal), with the same styles;
 *   - the common-ancestor chains of the 3D viewport, the 2D floor plan, and the
 *     inspection panel (to catch a shared opacity/filter/background above all);
 *   - the Bentley view state (viewFlags, render mode, feature-override provider
 *     count, emphasis/always/never-drawn, selection, canvas CSS opacity/filter);
 *   - the pointer receiver at the viewport center (elementFromPoint).
 *
 * NO mutation. NO secrets/tokens. NO per-frame logging — one snapshot per call.
 *
 * The heavy Bentley read is injected (bentleyViewState) so this module and its
 * pure formatter stay unit-testable without importing @itwin.
 */

export type PlacementDiagnosticMoment = 'NORMAL' | 'PLACEMENT_ACTIVE' | 'AFTER_CANCEL_DARK' | 'AD_HOC'

/** The darkening-relevant computed style of a single DOM element. */
export interface ElementStyleSnapshot {
    tagName: string
    id: string
    className: string
    rect: { x: number; y: number; width: number; height: number }
    zIndex: string
    position: string
    pointerEvents: string
    background: string
    backgroundColor: string
    opacity: string
    filter: string
    backdropFilter: string
    visibility: string
    display: string
    /** True when this element's rect covers >= COVER_FRACTION of the viewport rect. */
    coversViewport: boolean
    /** Relationship to the Bentley canvas, if known. */
    canvasRelation?: 'IS_CANVAS' | 'CONTAINS_CANVAS' | 'ABOVE_CANVAS' | 'UNRELATED'
}

/** Application/placement state captured at the moment (read, never inferred). */
export interface PlacementStateSnapshot {
    placementModeActive: boolean
    intentPresent: boolean
    intentSummary: string | undefined
    interactionState: string
    openPanel: string | null
    selectedCatalogAssetId: string | undefined
    pendingPlacementAssetId: string | undefined
    placementCandidatePresent: boolean
    placementToolActive: boolean
    activeBentleyToolId: string | undefined
    selectedAppObject: string | undefined
}

/** Bentley view-state (injected; read-only). */
export interface BentleyViewStateSnapshot {
    hasViewport: boolean
    renderMode?: string
    viewFlagsTransparency?: boolean
    viewFlagsLighting?: boolean
    featureOverrideProviderCount?: number
    alwaysDrawnCount?: number
    neverDrawnCount?: number
    selectionActive?: boolean
    displayStyleName?: string
    backgroundColorTbgr?: number
    canvasCssOpacity?: string
    canvasCssFilter?: string
    note?: string
}

export interface PlacementDarkeningSnapshot {
    moment: PlacementDiagnosticMoment
    capturedAt: string
    placementState: PlacementStateSnapshot
    viewport: {
        found: boolean
        hostTag?: string
        hostId?: string
        hostClass?: string
        canvasFound: boolean
        rect?: { x: number; y: number; width: number; height: number }
        centerX?: number
        centerY?: number
    }
    elementsFromPointStack: ElementStyleSnapshot[]
    pointerReceiver: ElementStyleSnapshot | undefined
    fullViewportElements: ElementStyleSnapshot[]
    commonAncestors: { subject: string; chain: ElementStyleSnapshot[] }[]
    bentleyViewState: BentleyViewStateSnapshot
}

/** Fraction of the viewport an element rect must cover to count as "full". */
const COVER_FRACTION = 0.6

function rectOf(el: Element): { x: number; y: number; width: number; height: number } {
    const r = el.getBoundingClientRect()
    return { x: Math.round(r.x), y: Math.round(r.y), width: Math.round(r.width), height: Math.round(r.height) }
}

function coversViewportRect(
    elRect: { x: number; y: number; width: number; height: number },
    vpRect: { x: number; y: number; width: number; height: number } | undefined,
): boolean {
    if (!vpRect || vpRect.width <= 0 || vpRect.height <= 0) return false
    // Intersection area vs viewport area.
    const ix = Math.max(elRect.x, vpRect.x)
    const iy = Math.max(elRect.y, vpRect.y)
    const ix2 = Math.min(elRect.x + elRect.width, vpRect.x + vpRect.width)
    const iy2 = Math.min(elRect.y + elRect.height, vpRect.y + vpRect.height)
    const iw = Math.max(0, ix2 - ix)
    const ih = Math.max(0, iy2 - iy)
    const inter = iw * ih
    return inter >= COVER_FRACTION * (vpRect.width * vpRect.height)
}

/** Read the darkening-relevant computed style of one element. */
export function snapshotElement(
    el: Element,
    vpRect: { x: number; y: number; width: number; height: number } | undefined,
    canvas: Element | undefined,
): ElementStyleSnapshot {
    const cs = typeof getComputedStyle === 'function' ? getComputedStyle(el) : ({} as CSSStyleDeclaration)
    const rect = rectOf(el)
    let canvasRelation: ElementStyleSnapshot['canvasRelation'] = 'UNRELATED'
    if (canvas) {
        if (el === canvas) canvasRelation = 'IS_CANVAS'
        else if (el.contains(canvas)) canvasRelation = 'CONTAINS_CANVAS'
        else {
            // Above the canvas if it comes later in document order and is not an ancestor.
            const pos = el.compareDocumentPosition(canvas)
            // eslint-disable-next-line no-bitwise
            const canvasPrecedesEl = (pos & Node.DOCUMENT_POSITION_PRECEDING) !== 0
            canvasRelation = canvasPrecedesEl ? 'ABOVE_CANVAS' : 'UNRELATED'
        }
    }
    return {
        tagName: el.tagName,
        id: (el as HTMLElement).id ?? '',
        className: typeof (el as HTMLElement).className === 'string' ? (el as HTMLElement).className : String((el as HTMLElement).className ?? ''),
        rect,
        zIndex: cs.zIndex ?? '',
        position: cs.position ?? '',
        pointerEvents: cs.pointerEvents ?? '',
        background: cs.background ?? '',
        backgroundColor: cs.backgroundColor ?? '',
        opacity: cs.opacity ?? '',
        filter: cs.filter ?? '',
        backdropFilter: (cs as unknown as { backdropFilter?: string }).backdropFilter ?? (cs as unknown as { webkitBackdropFilter?: string }).webkitBackdropFilter ?? '',
        visibility: cs.visibility ?? '',
        display: cs.display ?? '',
        coversViewport: coversViewportRect(rect, vpRect),
        canvasRelation,
    }
}

/** Whether a style snapshot indicates a *darkening* contribution. */
export function isDarkeningContributor(s: ElementStyleSnapshot): boolean {
    const op = parseFloat(s.opacity)
    if (Number.isFinite(op) && op < 1) return true
    if (s.filter && s.filter !== 'none') return true
    if (s.backdropFilter && s.backdropFilter !== 'none') return true
    const bg = (s.backgroundColor || '').replace(/\s/g, '')
    // rgba with a non-zero alpha that is < 1 => a translucent (dimming) fill.
    const m = bg.match(/rgba?\((\d+),(\d+),(\d+)(?:,([\d.]+))?\)/i)
    if (m) {
        const a = m[4] !== undefined ? parseFloat(m[4]) : 1
        if (a > 0 && a < 1) return true
    }
    return false
}

/**
 * Classify the proven root cause from a captured (dark) snapshot. Pure — decides
 * only from evidence in the snapshot, mirroring the spec's classification set.
 */
export type DarkeningRootCause =
    | 'ORPHANED_DOM_OVERLAY'
    | 'COMMON_ANCESTOR_OPACITY'
    | 'COMMON_ANCESTOR_FILTER'
    | 'POINTER_INTERCEPTION_LAYER'
    | 'PLACEMENT_STATE_NOT_IDLE'
    | 'BENTLEY_DISPLAY_STATE_NOT_RESTORED'
    | 'NO_DARKENING_EVIDENCE'

export function classifyDarkening(snap: PlacementDarkeningSnapshot): DarkeningRootCause[] {
    const causes: DarkeningRootCause[] = []

    // 1. A foreign DOM element above the canvas that covers the viewport and dims.
    const orphan = snap.elementsFromPointStack.find(
        (s) => s.canvasRelation === 'ABOVE_CANVAS' && s.coversViewport && isDarkeningContributor(s),
    )
    if (orphan) causes.push('ORPHANED_DOM_OVERLAY')

    // 2/3. A common ancestor (shared by viewport + 2D + inspector) that dims.
    for (const chain of snap.commonAncestors) {
        for (const a of chain.chain) {
            const op = parseFloat(a.opacity)
            if (Number.isFinite(op) && op < 1) { causes.push('COMMON_ANCESTOR_OPACITY'); break }
            if (a.filter && a.filter !== 'none') { causes.push('COMMON_ANCESTOR_FILTER'); break }
        }
    }

    // 4. A full-viewport element intercepting pointer events (auto) above the canvas.
    if (snap.pointerReceiver && snap.pointerReceiver.canvasRelation === 'ABOVE_CANVAS' &&
        snap.pointerReceiver.coversViewport && snap.pointerReceiver.pointerEvents !== 'none') {
        causes.push('POINTER_INTERCEPTION_LAYER')
    }

    // 5. Placement never returned to IDLE.
    if (snap.moment === 'AFTER_CANCEL_DARK' && snap.placementState.placementModeActive) {
        causes.push('PLACEMENT_STATE_NOT_IDLE')
    }

    // 6. Bentley scene state itself is dark (no foreign DOM layer explains it).
    if (causes.length === 0 && snap.bentleyViewState.hasViewport) {
        const b = snap.bentleyViewState
        const canvasDim = (b.canvasCssOpacity !== undefined && parseFloat(b.canvasCssOpacity) < 1) ||
            (b.canvasCssFilter !== undefined && b.canvasCssFilter !== 'none' && b.canvasCssFilter !== '')
        if (canvasDim || (b.featureOverrideProviderCount ?? 0) > 0 || (b.neverDrawnCount ?? 0) > 0) {
            causes.push('BENTLEY_DISPLAY_STATE_NOT_RESTORED')
        }
    }

    if (causes.length === 0) causes.push('NO_DARKENING_EVIDENCE')
    // De-dupe while preserving order.
    return Array.from(new Set(causes))
}

/** Ancestor chain (element -> ... -> body) as style snapshots. */
function ancestorChain(
    start: Element | null,
    vpRect: { x: number; y: number; width: number; height: number } | undefined,
    canvas: Element | undefined,
): ElementStyleSnapshot[] {
    const out: ElementStyleSnapshot[] = []
    let cur: Element | null = start
    let guard = 0
    while (cur && guard < 40) {
        out.push(snapshotElement(cur, vpRect, canvas))
        cur = cur.parentElement
        guard += 1
    }
    return out
}

/** Inputs a caller provides so this module never imports the store/Bentley directly. */
export interface CaptureDeps {
    moment: PlacementDiagnosticMoment
    placementState: PlacementStateSnapshot
    bentleyViewState: BentleyViewStateSnapshot
    /** Selectors for the three subjects; defaults match the /viewer shell. */
    viewportHostSelector?: string
    plan2dSelector?: string
    inspectorSelector?: string
}

/**
 * Capture a full darkening diagnostic snapshot from the LIVE DOM at this moment.
 * Read-only; performs no mutation.
 */
export function capturePlacementDarkeningSnapshot(deps: CaptureDeps): PlacementDarkeningSnapshot {
    const doc = typeof document !== 'undefined' ? document : undefined
    const hostSel = deps.viewportHostSelector ?? '.viewer-stage'
    const planSel = deps.plan2dSelector ?? '.bim2d-plan'
    const inspSel = deps.inspectorSelector ?? '.viewer-inspector'

    const host = doc?.querySelector(hostSel) ?? undefined
    const canvas = (host?.querySelector('canvas') ?? doc?.querySelector('.viewer-stage canvas')) ?? undefined
    const vpRect = host ? rectOf(host) : undefined
    const centerX = vpRect ? Math.round(vpRect.x + vpRect.width / 2) : undefined
    const centerY = vpRect ? Math.round(vpRect.y + vpRect.height / 2) : undefined

    // elementsFromPoint stack at viewport center.
    let stack: Element[] = []
    let pointerReceiverEl: Element | undefined
    if (doc && centerX !== undefined && centerY !== undefined && typeof doc.elementsFromPoint === 'function') {
        stack = doc.elementsFromPoint(centerX, centerY)
        pointerReceiverEl = typeof doc.elementFromPoint === 'function' ? (doc.elementFromPoint(centerX, centerY) ?? undefined) : stack[0]
    }
    const elementsFromPointStack = stack.map((el) => snapshotElement(el, vpRect, canvas))
    const pointerReceiver = pointerReceiverEl ? snapshotElement(pointerReceiverEl, vpRect, canvas) : undefined

    // All full-viewport elements anywhere in the document (any name).
    const fullViewportElements: ElementStyleSnapshot[] = []
    if (doc) {
        const all = doc.querySelectorAll('*')
        for (const el of Array.from(all)) {
            const s = snapshotElement(el, vpRect, canvas)
            if (s.coversViewport && (s.position === 'fixed' || s.position === 'absolute')) {
                fullViewportElements.push(s)
            }
        }
    }

    // Common-ancestor chains of the three darkened subjects.
    const plan = doc?.querySelector(planSel) ?? undefined
    const insp = doc?.querySelector(inspSel) ?? undefined
    const commonAncestors = [
        { subject: '3D_VIEWPORT', chain: ancestorChain(host ?? null, vpRect, canvas) },
        { subject: '2D_FLOOR_PLAN', chain: ancestorChain(plan ?? null, vpRect, canvas) },
        { subject: 'INSPECTION_PANEL', chain: ancestorChain(insp ?? null, vpRect, canvas) },
    ]

    return {
        moment: deps.moment,
        capturedAt: new Date().toISOString(),
        placementState: deps.placementState,
        viewport: {
            found: !!host,
            hostTag: host?.tagName,
            hostId: (host as HTMLElement | undefined)?.id,
            hostClass: typeof (host as HTMLElement | undefined)?.className === 'string' ? (host as HTMLElement).className : undefined,
            canvasFound: !!canvas,
            rect: vpRect,
            centerX,
            centerY,
        },
        elementsFromPointStack,
        pointerReceiver,
        fullViewportElements,
        commonAncestors,
        bentleyViewState: deps.bentleyViewState,
    }
}

/** Human-readable report for the Developer Inspector (bounded, no secrets). */
export function formatDarkeningSnapshot(snap: PlacementDarkeningSnapshot): string {
    const L: string[] = []
    L.push(`=== PLACEMENT DARKENING DIAGNOSTIC — ${snap.moment} @ ${snap.capturedAt} ===`)
    const p = snap.placementState
    L.push('[PLACEMENT STATE]')
    L.push(`  placementModeActive=${p.placementModeActive} intentPresent=${p.intentPresent} interaction=${p.interactionState}`)
    L.push(`  openPanel=${p.openPanel ?? 'null'} placementToolActive=${p.placementToolActive} activeBentleyTool=${p.activeBentleyToolId ?? 'none'}`)
    L.push(`  selectedCatalogAsset=${p.selectedCatalogAssetId ?? 'none'} pendingAsset=${p.pendingPlacementAssetId ?? 'none'} candidate=${p.placementCandidatePresent} selectedAppObject=${p.selectedAppObject ?? 'none'}`)

    const v = snap.viewport
    L.push('[VIEWPORT]')
    L.push(`  found=${v.found} host=<${v.hostTag}> class="${v.hostClass ?? ''}" canvasFound=${v.canvasFound} center=(${v.centerX},${v.centerY})`)

    L.push('[ELEMENTS-FROM-POINT @ center] (top -> bottom)')
    for (const s of snap.elementsFromPointStack) L.push('  ' + fmtEl(s))
    L.push(`[POINTER RECEIVER] ${snap.pointerReceiver ? fmtEl(snap.pointerReceiver) : 'none'}`)

    L.push('[FULL-VIEWPORT ELEMENTS]')
    if (snap.fullViewportElements.length === 0) L.push('  (none)')
    for (const s of snap.fullViewportElements) L.push('  ' + fmtEl(s) + (isDarkeningContributor(s) ? '  <<< DARKENS' : ''))

    L.push('[COMMON ANCESTOR DIMMERS]')
    for (const chain of snap.commonAncestors) {
        const dimmers = chain.chain.filter((a) => {
            const op = parseFloat(a.opacity)
            return (Number.isFinite(op) && op < 1) || (a.filter && a.filter !== 'none')
        })
        L.push(`  ${chain.subject}: ${dimmers.length === 0 ? 'no dimming ancestor' : dimmers.map((d) => `<${d.tagName}.${d.className}> opacity=${d.opacity} filter=${d.filter}`).join(' | ')}`)
    }

    const b = snap.bentleyViewState
    L.push('[BENTLEY VIEW STATE]')
    if (!b.hasViewport) L.push(`  no viewport${b.note ? ' (' + b.note + ')' : ''}`)
    else L.push(`  renderMode=${b.renderMode} vf.transparency=${b.viewFlagsTransparency} vf.lighting=${b.viewFlagsLighting} providers=${b.featureOverrideProviderCount} alwaysDrawn=${b.alwaysDrawnCount} neverDrawn=${b.neverDrawnCount} selection=${b.selectionActive} bg.tbgr=${b.backgroundColorTbgr} canvas.opacity=${b.canvasCssOpacity} canvas.filter=${b.canvasCssFilter}`)

    L.push('[ROOT-CAUSE CLASSIFICATION]')
    L.push('  ' + classifyDarkening(snap).join(', '))
    return L.join('\n')
}

function fmtEl(s: ElementStyleSnapshot): string {
    return `<${s.tagName}> id="${s.id}" class="${s.className}" [${s.canvasRelation}] cover=${s.coversViewport} z=${s.zIndex} pos=${s.position} pe=${s.pointerEvents} op=${s.opacity} filter=${s.filter} bdf=${s.backdropFilter} bg=${s.backgroundColor} vis=${s.visibility} disp=${s.display}`
}
