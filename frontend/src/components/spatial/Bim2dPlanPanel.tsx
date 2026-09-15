/**
 * Bim2dPlanPanel — TRUE 2D BIM FLOOR PLAN, shown SIMULTANEOUSLY with the 3D
 * Walkthrough (MRT Pharma Build 1B §B).
 *
 * This is an orthographic (top-down) SVG plan of the SAME authoritative BIM facts
 * the 3D scene uses. It is NOT a bird's-eye 3D camera reused as a plan
 * (BIRDS_EYE_USED_AS_2D_PLAN = NO): it renders the pure `projectBim2dPlan`
 * view-model, joined everywhere by `bimSpaceId`.
 *
 * SHARED IDENTITY + NO DUPLICATE STORES:
 *   - Rooms / assignments / equipment / candidate tiers come from the single
 *     overlay projection (`getBim2dPlanView`).
 *   - The walker marker consumes the single walkthrough read-model via
 *     `subscribeWalkthroughState` — there is NO second walker-position store.
 *
 * VIEW-ONLY INTERACTION:
 *   - Clicking a room SELECTS the same bimSpaceId (drives the existing program
 *     selection) — it NEVER moves the walker.
 *   - "Enter Walkthrough Here" reuses the safe clinical-room spawn
 *     (enterWalkthroughAtClinicalRoom); it never teleports via the plan.
 *
 * BUILD 1B UX CORRECTION:
 *   - LABEL DENSITY: the floor has ~200 BIM spaces. Only Clinical Program rooms
 *     (permanent, with a compact badge) and the SELECTED room are labelled; a
 *     HOVERED room is labelled transiently. Ordinary rooms render their polygon
 *     with identity available on hover/click — no mass labelling. Decided by the
 *     pure `resolvePlanRoomLabel` policy, not inline JSX.
 *   - NO PAN/ZOOM/FIT TOOLBAR: the plan auto-fits the active storey. There are no
 *     Fit / ＋ / － / arrow controls (MINI_PLAN_CONTROL_ROW_REMOVED = YES).
 *   - DISMISSIBLE: a proper × closes the plan to a compact "2D Plan" reopen chip.
 *     When closed there is NO viewport-blocking layer
 *     (MINI_PLAN_BLOCKS_VIEWPORT_WHEN_CLOSED = NO).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
    computePlanFitTransform,
    worldToScreen,
    screenToWorld,
    hitTestPlanRoom,
    hitTestPlanEquipment,
    hitTestPlanVestibule,
    resolvePlanRoomLabel,
    isProgramClinicalFunction,
    type Bim2dPlanView,
    type PlanFitTransform,
    type PlanVec2,
    type PlanWalkerInput,
    type PlanCandidateTier,
} from './bim2dPlanProjection'
import {
    emptyTrail,
    advanceTrail,
    trailSegmentsForStorey,
    type WalkthroughTrail,
} from './walkthroughTrail'

// Fill colors for assigned clinical functions (view-only cue; not authoritative).
const FUNCTION_FILL = 'rgba(64, 156, 255, 0.18)'
const SELECTED_STROKE = '#ffcc33'
const ROOM_STROKE = '#7f8ea3'
const EQUIPMENT_STROKE = '#ff9b42'
const WALKER_COLOR = '#39d98a'
// The travelled-path trail is drawn BEHIND the bright walker marker in a SUBDUED
// green so it reads as history without competing with the live position/heading
// (HEADING_EQUALS_TRAIL = NO). It never obscures the underlying BIM geometry.
const TRAIL_COLOR = 'rgba(57, 217, 138, 0.45)'
const TRAIL_START_COLOR = '#2fae6f'

// Candidate tier accent (matches the panel badge semantics).
const TIER_ACCENT: Record<PlanCandidateTier, string> = {
    RECOMMENDED: '#39d98a',
    SUITABLE: '#5bc0ff',
    NEEDS_REVIEW: '#ffd166',
    REJECTED: '#ff6b6b',
}

// Compact orthographic canvas. The panel auto-fits the active storey into this
// viewBox; CSS scales the rendered footprint responsively (no hard-coded size row).
const VIEW_W = 260
const VIEW_H = 200

interface Bim2dPlanPanelProps {
    /** Test seam: inject the overlay module (defaults to the real dynamic import). */
    loadOverlay?: () => Promise<typeof import('./spatialAssetOverlay')>
}

export function Bim2dPlanPanel({ loadOverlay }: Bim2dPlanPanelProps = {}) {
    const importOverlay = useMemo(
        () => loadOverlay ?? (() => import('./spatialAssetOverlay')),
        [loadOverlay],
    )

    const [cameraMode, setCameraMode] = useState<string>('PLANNING')
    // Dismissed => the plan is CLOSED to a compact reopen chip. There is no
    // pointer-blocking layer while closed.
    const [dismissed, setDismissed] = useState(false)
    const [view, setView] = useState<Bim2dPlanView | null>(null)
    const [note, setNote] = useState('')
    // Transient hover identity (renderer-driven; never persisted to any store).
    const [hoveredId, setHoveredId] = useState<string | undefined>(undefined)

    // App-owned WALKTHROUGH PROGRESSION TRAIL (Build 1B Defect 2). This is a
    // visualization-only history derived EXCLUSIVELY from the authoritative
    // walkthrough read-model — it is NEVER a second walker store and can NEVER
    // move the walker (WALKER_SINGLE_SOURCE_OF_TRUTH = walkthroughController).
    const [trail, setTrail] = useState<WalkthroughTrail>(() => emptyTrail())

    const svgRef = useRef<SVGSVGElement | null>(null)
    // The walker read-model is kept in a ref too so rebuild() always uses the latest
    // without needing walker in its dependency list (avoids a rebuild storm).
    const walkerRef = useRef<PlanWalkerInput | undefined>(undefined)
    // Guard so we hydrate rooms (Clinical-Program-independent) at most once per
    // empty-plan situation, never in a rebuild loop.
    const hydrateRequestedRef = useRef(false)

    // Rebuild the plan view-model from the single overlay projection.
    const rebuild = useCallback(() => {
        void importOverlay().then((o) => {
            setCameraMode(o.getActiveCameraMode())
            const next = o.getBim2dPlanView({ walker: walkerRef.current })
            setView(next)
            // Build 1B Defect 1: if the plan projected ZERO rooms, the discovered-
            // room registry has not been hydrated yet (e.g. Clinical Program = Off
            // during Walkthrough). Trigger the SAME idempotent semantics refresh —
            // WITHOUT enabling the Clinical Program — then rebuild once. Guarded so
            // this never loops when the model genuinely has no rooms (offline).
            if (next.rooms.length === 0 && !hydrateRequestedRef.current) {
                hydrateRequestedRef.current = true
                void o.ensureBim2dPlanRoomsHydrated().then((count) => {
                    if (count > 0) {
                        setView(o.getBim2dPlanView({ walker: walkerRef.current }))
                    }
                })
            } else if (next.rooms.length > 0) {
                // Rooms are present again — allow a fresh hydrate if they ever empty.
                hydrateRequestedRef.current = false
            }
        })
    }, [importOverlay])

    // Program changes (rooms / assignments / selection / camera mode) -> rebuild.
    useEffect(() => {
        let unsub = () => { }
        let cancelled = false
        void importOverlay().then((o) => {
            if (cancelled) return
            rebuild()
            unsub = o.subscribeClinicalProgram(() => rebuild())
        })
        return () => { cancelled = true; unsub() }
    }, [importOverlay, rebuild])

    // Walker state (single source) -> update the marker (no duplicate store).
    useEffect(() => {
        let unsub = () => { }
        let cancelled = false
        void importOverlay().then(async (o) => {
            if (cancelled) return
            unsub = await o.subscribeWalkthroughState((s) => {
                const w: PlanWalkerInput | undefined = s
                    ? { active: s.active, eye: s.eye, yaw: s.yaw, activeStoreyId: s.activeStoreyId, fovDeg: s.fovDeg }
                    : undefined
                walkerRef.current = w
                // Extend the app-owned progression trail from this authoritative
                // sample. advanceTrail is pure: it appends only on meaningful XY
                // translation (turn/pitch/FOV never extend it), starts a new segment
                // on storey change / teleport / new session, and keeps history when
                // the session ends. This NEVER moves the walker.
                setTrail((prev) => advanceTrail(prev, {
                    active: !!s?.active,
                    eye: s?.eye ?? { x: 0, y: 0, z: 0 },
                    storeyId: s?.activeStoreyId,
                }))
                // Only re-project (which re-places the marker) — never move the walker.
                rebuild()
            })
        })
        return () => { cancelled = true; unsub() }
    }, [importOverlay, rebuild])

    // Fit transform (world -> screen). ALWAYS auto-fit the active storey bounds into
    // the compact canvas — there is no user pan/zoom override any more.
    const transform: PlanFitTransform = useMemo(() => {
        return computePlanFitTransform(
            view?.bounds ?? { minX: 0, minY: 0, maxX: 0, maxY: 0, ok: false },
            VIEW_W,
            VIEW_H,
        )
    }, [view])

    const project = useCallback((p: PlanVec2) => worldToScreen(transform, p), [transform])

    const ringToPoints = useCallback((ring: readonly PlanVec2[]) => {
        return ring.map((p) => { const s = project(p); return `${s.x.toFixed(1)},${s.y.toFixed(1)}` }).join(' ')
    }, [project])

    // Map a DOM pointer event to the SVG's internal (world) coordinate system.
    const eventToWorld = useCallback((e: React.MouseEvent<SVGSVGElement>): PlanVec2 | undefined => {
        const rect = svgRef.current?.getBoundingClientRect()
        if (!rect || rect.width === 0 || rect.height === 0) return undefined
        const sx = ((e.clientX - rect.left) / rect.width) * VIEW_W
        const sy = ((e.clientY - rect.top) / rect.height) * VIEW_H
        return screenToWorld(transform, { x: sx, y: sy })
    }, [transform])

    // Click a room -> select the SAME bimSpaceId (view-only; never moves walker).
    const onSvgClick = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
        if (!view) return
        const world = eventToWorld(e)
        if (!world) return
        // EVI-MA-02 — equipment markers are hit-tested FIRST so a marker click
        // converges on the SAME `selectedEquipmentId` authority as 3D click /
        // right-click / equipment card (never a second selection). Falls through
        // to room selection when the click is not on an equipment marker.
        // EVI-MA-05A — a vestibule marker click converges on the SAME
        // selectedVestibuleId authority as the 3D pick / floating control.
        const vestibuleId = hitTestPlanVestibule(view, world)
        if (vestibuleId) {
            void importOverlay().then((o) => {
                o.selectVestibule(vestibuleId)
                void o.fitViewToVestibule(vestibuleId).catch(() => false)
            })
            return
        }
        const equipmentId = hitTestPlanEquipment(view, world)
        if (equipmentId) {
            void importOverlay().then((o) => {
                o.selectEquipment(equipmentId)
                void o.fitViewToEquipment(equipmentId).catch(() => false)
            })
            return
        }
        const hitId = hitTestPlanRoom(view, world)
        if (!hitId) return
        void importOverlay().then((o) => {
            o.setClinicalProgramSelectedSpace(hitId)
            // Fit the 3D view to the room too (existing behavior) but DO NOT enter
            // walkthrough / move the walker.
            void o.fitViewToClinicalRoom(hitId).catch(() => false)
        })
    }, [view, eventToWorld, importOverlay])

    // Hover -> transient identity for the room under the pointer (no store write).
    const onSvgMove = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
        if (!view) return
        const world = eventToWorld(e)
        if (!world) { setHoveredId(undefined); return }
        setHoveredId(hitTestPlanRoom(view, world))
    }, [view, eventToWorld])

    const onSvgLeave = useCallback(() => setHoveredId(undefined), [])

    const enterWalkthroughHere = useCallback(() => {
        const selected = view?.rooms.find((r) => r.selected)
        if (!selected) { setNote('Select a room on the plan first.'); return }
        void importOverlay().then(async (o) => {
            const r = await o.enterWalkthroughAtClinicalRoom({ bimSpaceId: selected.bimSpaceId })
            setNote(r.ok ? `Entered walkthrough in ${selected.label}.` : `Cannot enter here: ${r.reason}`)
        })
    }, [view, importOverlay])

    // Reopen the plan and refit the active storey (the walker returns immediately
    // because it is derived from the single walkthrough read-model on rebuild).
    const reopen = useCallback(() => {
        setDismissed(false)
        setNote('')
        rebuild()
    }, [rebuild])

    // The plan is shown SIMULTANEOUSLY with the 3D Walkthrough (its whole point).
    // It is also available in Planning as a live orthographic reference.
    const walkthroughActive = cameraMode === 'WALKTHROUGH'

    const rooms = view?.rooms ?? []
    const equipment = view?.equipment ?? []
    const vestibules = view?.vestibules ?? []
    const prov = view?.provenance

    // Trail segments to DRAW: only the active storey's history (storey-scoped;
    // CROSS_STOREY_FALSE_CONNECTOR = NO). The active storey follows the walker.
    const trailStoreyId = view?.walker?.activeStoreyId ?? view?.storeyId
    const drawnTrailSegments = useMemo(
        () => trailSegmentsForStorey(trail, trailStoreyId),
        [trail, trailStoreyId],
    )

    // CLOSED: render ONLY a compact reopen chip. No panel body, no SVG, and no
    // full-size wrapper — so nothing can block the 3D viewport behind it.
    if (dismissed) {
        return (
            <button
                type="button"
                className="bim2d-plan-reopen"
                aria-label="Open 2D floor plan"
                onClick={reopen}
            >
                2D Plan
            </button>
        )
    }

    return (
        <div className="bim2d-plan" aria-label="2D BIM floor plan">
            <div className="bim2d-plan-head">
                <span className="bim2d-plan-title">
                    2D Floor Plan{walkthroughActive ? ' · live with Walkthrough' : ''}
                </span>
                <button
                    type="button"
                    className="bim2d-plan-close"
                    aria-label="Close 2D plan"
                    title="Close"
                    onClick={() => setDismissed(true)}
                >×</button>
            </div>

            <svg
                ref={svgRef}
                className="bim2d-plan-svg"
                viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
                role="img"
                aria-label="Orthographic BIM floor plan"
                onClick={onSvgClick}
                onMouseMove={onSvgMove}
                onMouseLeave={onSvgLeave}
            >
                {/* Rooms (exact footprint preferred; approximate outlines dashed).
                    Labels follow the pure label-density policy: Clinical Program +
                    selected are permanent; the hovered room is transient; the rest
                    render their polygon without a label. */}
                {rooms.map((room) => {
                    if (room.ring.length < 3) return null
                    const approx = room.footprintSource === 'BIM_RANGE_APPROXIMATION'
                    const clinical = isProgramClinicalFunction(room.clinicalFunction)
                    const tierAccent = room.candidateTier ? TIER_ACCENT[room.candidateTier] : undefined
                    const stroke = room.selected ? SELECTED_STROKE : (tierAccent ?? ROOM_STROKE)
                    const fill = clinical ? FUNCTION_FILL : 'rgba(255,255,255,0.02)'
                    const label = resolvePlanRoomLabel(room, hoveredId)
                    const anchor = label.show && room.labelAnchor ? project(room.labelAnchor) : undefined
                    return (
                        <g key={room.bimSpaceId} data-bim-space-id={room.bimSpaceId} data-footprint-source={room.footprintSource}>
                            <polygon
                                points={ringToPoints(room.ring)}
                                fill={fill}
                                stroke={stroke}
                                strokeWidth={room.selected ? 2.4 : 1.2}
                                strokeDasharray={approx ? '4 3' : undefined}
                            />
                            {anchor && (
                                <text
                                    x={anchor.x}
                                    y={anchor.y}
                                    className={`bim2d-plan-room-label bim2d-plan-room-label--${label.kind.toLowerCase()}`}
                                    textAnchor="middle"
                                    data-label-kind={label.kind}
                                >
                                    {label.text}
                                </text>
                            )}
                        </g>
                    )
                })}

                {/* Equipment envelopes. */}
                {equipment.map((e) => (
                    e.ring.length >= 3 ? (
                        // EVI-MA-02E — hidden equipment keeps a SUBDUED / dashed
                        // marker (retains equipmentInstanceId, still selectable) so
                        // it stays recoverable and honestly shows it still occupies
                        // physical space. Not removed just because Hide was clicked.
                        <polygon
                            key={e.id}
                            data-equipment-id={e.id}
                            data-equipment-hidden={e.hidden ? 'true' : 'false'}
                            points={ringToPoints(e.ring)}
                            fill={e.hidden ? 'rgba(255,155,66,0.05)' : 'rgba(255,155,66,0.16)'}
                            stroke={EQUIPMENT_STROKE}
                            strokeOpacity={e.hidden ? 0.5 : 1}
                            strokeWidth={e.lifecycleState === 'LOCKED' ? 1.6 : 1}
                            strokeDasharray={e.hidden ? '2 3' : e.lifecycleState === 'LOCKED' ? undefined : '3 2'}
                        />
                    ) : null
                ))}

                {/* EVI-MA-05A — ONE vestibule marker each: room-side front-face
                    footprint (sage), the wall-penetration segment, and the MRT +
                    PTS stub directions behind the wall. Hidden = subdued/dashed but
                    recoverable (retains vestibuleInstanceId, still selectable). No
                    separate MRT/PTS markers. */}
                {vestibules.map((v) => {
                    if (v.ring.length < 3) return null
                    const pen = v.wallPenetration
                    const pFrom = project(pen.from)
                    const pTo = project(pen.to)
                    const mrt = v.mrtStub ? { a: project(v.mrtStub.from), b: project(v.mrtStub.to) } : undefined
                    const pts = v.ptsStub ? { a: project(v.ptsStub.from), b: project(v.ptsStub.to) } : undefined
                    return (
                        <g key={v.id} data-vestibule-id={v.id} data-vestibule-hidden={v.hidden ? 'true' : 'false'}>
                            <polygon
                                points={ringToPoints(v.ring)}
                                fill={v.hidden ? 'rgba(120,200,150,0.05)' : 'rgba(120,200,150,0.2)'}
                                stroke="#5ec78a"
                                strokeOpacity={v.hidden ? 0.5 : 1}
                                strokeWidth={v.lifecycleState === 'LOCKED' ? 1.6 : 1}
                                strokeDasharray={v.hidden ? '2 3' : undefined}
                            />
                            {/* Wall-penetration segment. */}
                            <line x1={pFrom.x} y1={pFrom.y} x2={pTo.x} y2={pTo.y} stroke="#9fd8b6" strokeWidth={1} strokeDasharray="1 2" />
                            {/* MRT stub direction (rectangular tract). */}
                            {mrt && <line x1={mrt.a.x} y1={mrt.a.y} x2={mrt.b.x} y2={mrt.b.y} stroke="#9db2c4" strokeWidth={2} />}
                            {/* PTS stub direction (circular tube) — thinner + dashed. */}
                            {pts && <line x1={pts.a.x} y1={pts.a.y} x2={pts.b.x} y2={pts.b.y} stroke="#b7c0c8" strokeWidth={1} strokeDasharray="2 2" />}
                        </g>
                    )
                })}

                {/* Walkthrough PROGRESSION TRAIL (Build 1B Defect 2): the route the
                    user has actually walked, START → travelled path → (current).
                    Drawn BEHIND the bright walker marker in subdued green as one
                    polyline per same-storey segment (no false cross-storey/teleport
                    connectors). The heading indicator stays separate on the marker. */}
                {drawnTrailSegments.map((seg) => {
                    if (seg.points.length === 0) return null
                    const pts = seg.points.map((tp) => {
                        const s = project({ x: tp.x, y: tp.y })
                        return `${s.x.toFixed(1)},${s.y.toFixed(1)}`
                    }).join(' ')
                    const start = project({ x: seg.points[0].x, y: seg.points[0].y })
                    return (
                        <g key={`trail-${seg.index}`} data-testid="plan-trail-segment" data-trail-points={seg.points.length}>
                            {seg.points.length >= 2 && (
                                <polyline
                                    points={pts}
                                    fill="none"
                                    stroke={TRAIL_COLOR}
                                    strokeWidth={2}
                                    strokeLinejoin="round"
                                    strokeLinecap="round"
                                />
                            )}
                            {/* START marker (where this segment began). */}
                            <circle cx={start.x} cy={start.y} r={2.6} fill={TRAIL_START_COLOR} opacity={0.85} />
                        </g>
                    )
                })}

                {/* Walker marker (single walkthrough read-model; heading arrow). */}
                {view?.walker && (() => {
                    const p = project(view.walker.position)
                    const hx = p.x + view.walker.heading.x * 16
                    const hy = p.y - view.walker.heading.y * 16
                    return (
                        <g data-testid="plan-walker">
                            <line x1={p.x} y1={p.y} x2={hx} y2={hy} stroke={WALKER_COLOR} strokeWidth={2.2} />
                            <circle cx={p.x} cy={p.y} r={5} fill={WALKER_COLOR} stroke="#0b1b12" strokeWidth={1} />
                        </g>
                    )
                })()}
            </svg>

            <div className="bim2d-plan-actions">
                <button
                    type="button"
                    className="bim2d-plan-enter"
                    onClick={enterWalkthroughHere}
                    disabled={!rooms.some((r) => r.selected)}
                >Enter Walkthrough Here</button>
            </div>

            {prov && (
                <div className="bim2d-plan-provenance">
                    {prov.totalRooms} rooms · {prov.exactFootprintRooms} exact · {prov.approximateFootprintRooms} approx (dashed)
                    {prov.equipmentCount > 0 ? ` · ${prov.equipmentCount} equipment` : ''}
                    {prov.walkerPresent ? ' · walker live' : ''}
                </div>
            )}
            {note && <div className="bim2d-plan-note">{note}</div>}
        </div>
    )
}
