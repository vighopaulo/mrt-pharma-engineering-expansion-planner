/**
 * projectBim — pure, Bentley-free project-BIM identity, registry, persistence,
 * and active-BIM resolution. Separates "which iModel the product opens" from
 * ingestion. No @itwin imports; fully unit-testable.
 *
 * SECURITY: persistence stores ONLY safe BIM identity/metadata (ids, names,
 * roles). It NEVER stores tokens, Authorization, refresh tokens, PKCE, or
 * secrets.
 */

export type ProjectBimRole = 'PRODUCT_DEMO_BIM' | 'ENGINEERING_REGRESSION_FIXTURE'

/** A first-class registered project BIM (an already-ingested Bentley iModel). */
export interface RegisteredBim {
    iModelId: string
    iTwinId: string
    displayName: string
    role: ProjectBimRole
    /** Optional, safe metadata. Never secrets. */
    sourceFileName?: string
    sourceType?: 'IFC' | 'SYNTHETIC' | 'OTHER'
    ingestionStatus?: 'READY' | 'INGESTING' | 'FAILED'
    classification?: string
    lastOpenedAt?: string
}

/** Persisted active-selection payload (safe subset only). */
export interface PersistedActiveBim {
    iModelId: string
    iTwinId: string
    displayName: string
    role: ProjectBimRole
    lastOpenedAt?: string
}

export type SelectionSource = 'URL_OVERRIDE' | 'PERSISTED_SELECTION' | 'PRODUCT_DEFAULT' | 'LEGACY_FALLBACK'

export interface ResolvedActiveBim {
    /** The chosen iModel id (always defined; falls back to legacy). */
    iModelId: string
    iTwinId: string
    /** The registered model if the id matches one; else undefined (URL override
     * to an unregistered id is allowed but has no registry metadata). */
    registered?: RegisteredBim
    source: SelectionSource
    displayName?: string
    role?: ProjectBimRole
}

// ---------------------------------------------------------------------------
// The MRT Pharma registry (Bentley-free identities). The engineering fixture id
// is injected from existing config (never guessed) so this module holds no
// duplicated secret/constant for it.
// ---------------------------------------------------------------------------

/** The product/demo clinic — a public iModel id. */
export const MEDICAL_CLINIC_DEMO: Omit<RegisteredBim, 'iTwinId'> = {
    iModelId: '36381ef4-b5f5-4d6d-b64b-2dbd69ba26a4',
    displayName: 'MRTway Medical Clinic Demo',
    role: 'PRODUCT_DEMO_BIM',
    sourceFileName: 'Clinic_Architectural.ifc',
    sourceType: 'IFC',
    ingestionStatus: 'READY',
    classification: 'DETAILED_ARCHITECTURAL_BIM',
}

/**
 * Build the registry from the runtime iTwin id + the existing (legacy) fixture
 * iModel id. Both come from config so nothing is duplicated/guessed here.
 */
export function buildProjectBimRegistry(input: { iTwinId: string; fixtureIModelId: string }): RegisteredBim[] {
    return [
        { ...MEDICAL_CLINIC_DEMO, iTwinId: input.iTwinId },
        {
            iModelId: input.fixtureIModelId,
            iTwinId: input.iTwinId,
            displayName: 'MRTway Hospital Campus Development',
            role: 'ENGINEERING_REGRESSION_FIXTURE',
            sourceType: 'SYNTHETIC',
            ingestionStatus: 'READY',
            classification: 'PARTIAL_ARCHITECTURAL_BIM',
        },
    ]
}

/** The product default = the first PRODUCT_DEMO_BIM in the registry, if any. */
export function productDefaultBim(registry: readonly RegisteredBim[]): RegisteredBim | undefined {
    return registry.find((b) => b.role === 'PRODUCT_DEMO_BIM')
}

// ---------------------------------------------------------------------------
// Pure active-BIM resolution (precedence + invalid-persisted guard)
// ---------------------------------------------------------------------------

function isPlausibleId(v: string | undefined): v is string {
    return typeof v === 'string' && /^[A-Za-z0-9\-_]{8,64}$/.test(v)
}

/**
 * Resolve the active project BIM deterministically:
 *   URL_OVERRIDE > PERSISTED_SELECTION > PRODUCT_DEFAULT > LEGACY_FALLBACK
 *
 * - URL override: any plausible id (may be unregistered — engineering override).
 * - Persisted: honored ONLY if it matches a registered model (invalid persisted
 *   id is ignored, never blindly opened).
 * - Product default: the registered PRODUCT_DEMO_BIM (the clinic).
 * - Legacy fallback: the configured fixture id.
 */
export function resolveActiveProjectBim(input: {
    urlOverrideIModelId?: string
    urlOverrideITwinId?: string
    persisted?: PersistedActiveBim | null
    registry: readonly RegisteredBim[]
    legacyFallback: { iModelId: string; iTwinId: string }
}): ResolvedActiveBim {
    const { urlOverrideIModelId, urlOverrideITwinId, persisted, registry, legacyFallback } = input

    // 1. URL override (developer/engineering). Does NOT persist by itself.
    if (isPlausibleId(urlOverrideIModelId)) {
        const reg = registry.find((b) => b.iModelId === urlOverrideIModelId)
        return {
            iModelId: urlOverrideIModelId,
            iTwinId: reg?.iTwinId ?? (isPlausibleId(urlOverrideITwinId) ? urlOverrideITwinId : legacyFallback.iTwinId),
            registered: reg,
            source: 'URL_OVERRIDE',
            displayName: reg?.displayName,
            role: reg?.role,
        }
    }

    // 2. Persisted selection — only if it matches a registered model.
    if (persisted && isPlausibleId(persisted.iModelId)) {
        const reg = registry.find((b) => b.iModelId === persisted.iModelId)
        if (reg) {
            return { iModelId: reg.iModelId, iTwinId: reg.iTwinId, registered: reg, source: 'PERSISTED_SELECTION', displayName: reg.displayName, role: reg.role }
        }
        // invalid persisted id (not in registry) => ignore, fall through
    }

    // 3. Product default (the clinic).
    const def = productDefaultBim(registry)
    if (def) {
        return { iModelId: def.iModelId, iTwinId: def.iTwinId, registered: def, source: 'PRODUCT_DEFAULT', displayName: def.displayName, role: def.role }
    }

    // 4. Legacy configured fixture fallback.
    const legacyReg = registry.find((b) => b.iModelId === legacyFallback.iModelId)
    return {
        iModelId: legacyFallback.iModelId,
        iTwinId: legacyFallback.iTwinId,
        registered: legacyReg,
        source: 'LEGACY_FALLBACK',
        displayName: legacyReg?.displayName,
        role: legacyReg?.role,
    }
}

// ---------------------------------------------------------------------------
// Persistence (localStorage; safe metadata only)
// ---------------------------------------------------------------------------

export const ACTIVE_BIM_STORAGE_KEY = 'mrtpharma.activeProjectBim.v1'

/** Sanitize to the safe persisted subset — strips anything unexpected. */
export function toPersistedActiveBim(b: { iModelId: string; iTwinId: string; displayName: string; role: ProjectBimRole }): PersistedActiveBim {
    return {
        iModelId: b.iModelId,
        iTwinId: b.iTwinId,
        displayName: b.displayName,
        role: b.role,
        lastOpenedAt: new Date().toISOString(),
    }
}

/** Whether a candidate persisted object contains ONLY safe fields (no secrets). */
export function isSafePersistedPayload(v: unknown): v is PersistedActiveBim {
    if (!v || typeof v !== 'object') return false
    const allowed = new Set(['iModelId', 'iTwinId', 'displayName', 'role', 'lastOpenedAt'])
    const forbidden = ['token', 'accessToken', 'access_token', 'refreshToken', 'refresh_token', 'authorization', 'Authorization', 'clientSecret', 'client_secret', 'pkce', 'verifier']
    const keys = Object.keys(v as Record<string, unknown>)
    if (keys.some((k) => forbidden.includes(k))) return false
    if (!keys.every((k) => allowed.has(k))) return false
    const o = v as Record<string, unknown>
    return typeof o.iModelId === 'string' && typeof o.iTwinId === 'string' && typeof o.displayName === 'string'
}

export function loadPersistedActiveBim(storage?: Pick<Storage, 'getItem'>): PersistedActiveBim | null {
    const s = storage ?? (typeof window !== 'undefined' ? window.localStorage : undefined)
    if (!s) return null
    try {
        const raw = s.getItem(ACTIVE_BIM_STORAGE_KEY)
        if (!raw) return null
        const parsed = JSON.parse(raw) as unknown
        return isSafePersistedPayload(parsed) ? parsed : null
    } catch {
        return null
    }
}

// ---------------------------------------------------------------------------
// Pure selector-row state (exactly one ACTIVE; identity-based, never name/role)
// ---------------------------------------------------------------------------

export type BimRowState = 'ACTIVE' | 'OPEN' | 'OPENING'

/**
 * Resolve one selector row's state from the RESOLVED active iModel id and the
 * pending-switch target. Uses iModel IDENTITY only (never role / displayName /
 * index / button state):
 *   - candidate is the pending switch target -> OPENING
 *   - candidate.iModelId === activeIModelId    -> ACTIVE
 *   - otherwise                                 -> OPEN
 */
export function resolveBimSelectorRowState(input: {
    candidateIModelId: string
    activeIModelId: string
    switchPendingIModelId?: string
}): BimRowState {
    if (input.switchPendingIModelId && input.candidateIModelId === input.switchPendingIModelId) return 'OPENING'
    if (input.candidateIModelId === input.activeIModelId) return 'ACTIVE'
    return 'OPEN'
}

export function savePersistedActiveBim(bim: { iModelId: string; iTwinId: string; displayName: string; role: ProjectBimRole }, storage?: Pick<Storage, 'setItem'>): PersistedActiveBim {
    const payload = toPersistedActiveBim(bim)
    const s = storage ?? (typeof window !== 'undefined' ? window.localStorage : undefined)
    try { s?.setItem(ACTIVE_BIM_STORAGE_KEY, JSON.stringify(payload)) } catch { /* storage unavailable */ }
    return payload
}
