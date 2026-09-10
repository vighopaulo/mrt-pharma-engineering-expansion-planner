/**
 * bentleyPermissionProbe — READ-ONLY diagnostic that converts UNKNOWN Bentley
 * cloud permissions into evidence-based verdicts, using the ALREADY-authenticated
 * browser runtime token to issue GET-only iTwin Platform API calls.
 *
 * HARD RULES (enforced here):
 *   - GET only. No POST/PUT/PATCH/DELETE. Nothing is created/uploaded/run.
 *   - The bearer token is read from IModelApp.authorizationClient at call time
 *     and used only in the Authorization header. It is NEVER logged, persisted,
 *     or returned. Responses are classified (status + shape), not dumped.
 *
 * The pure classifier (classifyBentleyPermissionProbe) is Bentley-free and unit
 * tested offline; the network layer is a thin GET wrapper around it.
 */

const ITWIN_ID = 'bdf29ecd-b4a4-404d-861a-ac3061c7b12f' // MRTway Development Twin (public id)
const API_BASE = 'https://api.bentley.com'

// ---------------------------------------------------------------------------
// Pure, Bentley-free classifier (offline-testable)
// ---------------------------------------------------------------------------

export type Access = 'YES' | 'NO' | 'UNKNOWN'
export type SyncAuth = 'AUTHORIZED' | 'REQUIRES_ADDITIONAL_AUTHORIZATION' | 'FORBIDDEN' | 'UNKNOWN'
export type Readiness = 'READY' | 'PARTIAL' | 'BLOCKED'

export interface PermissionProbeInputs {
    /** true if a valid bearer token was obtained from the runtime. */
    tokenPresent: boolean
    /** effective iModel-create permission (imodels_manage / org admin). */
    imodelCreate: Access
    /** iModel read (the viewer already proves this, but recorded). */
    imodelRead: Access
    storageRead: Access
    /** effective storage_write / org admin. */
    storageWrite: Access
    /** synchronization authorizationinformation result. */
    syncAuthorization: SyncAuth
    /** whether any GET returned 401 (auth/scope problem). */
    anyAuthScopeError: boolean
}

export interface PermissionProbeVerdict {
    readiness: Readiness
    blockers: string[]
}

/**
 * Classify overall cloud-ingestion readiness from the probe inputs.
 *   - READY: token present, create + storage_write available, sync AUTHORIZED.
 *   - BLOCKED: a required permission is definitively NO, sync FORBIDDEN, or an
 *     auth/scope (401) error.
 *   - PARTIAL: otherwise (some required signal still UNKNOWN, no hard denial).
 */
export function classifyBentleyPermissionProbe(p: PermissionProbeInputs): PermissionProbeVerdict {
    const blockers: string[] = []

    if (p.anyAuthScopeError || !p.tokenPresent) {
        blockers.push('AUTH_SCOPE_BLOCKER (401 / no runtime token)')
        return { readiness: 'BLOCKED', blockers }
    }
    if (p.imodelCreate === 'NO') blockers.push('NEEDS_imodels_manage (iModel create denied)')
    if (p.storageWrite === 'NO') blockers.push('NEEDS_storage_write (storage write denied)')
    if (p.syncAuthorization === 'FORBIDDEN') blockers.push('SYNCHRONIZATION_API_FORBIDDEN')
    if (p.syncAuthorization === 'REQUIRES_ADDITIONAL_AUTHORIZATION') blockers.push('SYNCHRONIZATION_REQUIRES_ADDITIONAL_AUTHORIZATION')

    const hardDenied = p.imodelCreate === 'NO' || p.storageWrite === 'NO' || p.syncAuthorization === 'FORBIDDEN'
    if (hardDenied) return { readiness: 'BLOCKED', blockers }

    const allReady =
        p.imodelCreate === 'YES' &&
        p.storageWrite === 'YES' &&
        p.syncAuthorization === 'AUTHORIZED'
    if (allReady) return { readiness: 'READY', blockers: [] }

    // No hard denial, but not all positive => PARTIAL. Record the unknowns.
    if (p.imodelCreate === 'UNKNOWN') blockers.push('IMODEL_CREATE_PERMISSION_UNVERIFIED')
    if (p.storageWrite === 'UNKNOWN') blockers.push('STORAGE_WRITE_PERMISSION_UNVERIFIED')
    if (p.syncAuthorization === 'UNKNOWN') blockers.push('SYNCHRONIZATION_AUTHORIZATION_UNVERIFIED')
    return { readiness: 'PARTIAL', blockers }
}

/** Classify an HTTP status into an access verdict for permission-style GETs. */
export function accessFromStatus(status: number): Access {
    if (status >= 200 && status < 300) return 'YES'
    if (status === 403) return 'NO'
    return 'UNKNOWN' // 401 handled separately as auth/scope; 404/429/other => unknown
}

// ---------------------------------------------------------------------------
// GET-only network layer (browser runtime)
// ---------------------------------------------------------------------------

interface GetResult {
    label: string
    status: number
    ok: boolean
}

/** A single GET. Token used only in the header; never logged or returned. */
async function safeGet(url: string, token: string, label: string, accept?: string): Promise<GetResult> {
    try {
        const res = await fetch(url, {
            method: 'GET',
            headers: {
                Authorization: token, // AccessToken already includes the scheme
                Accept: accept ?? 'application/vnd.bentley.itwin-platform.v1+json',
            },
        })
        return { label, status: res.status, ok: res.ok }
    } catch {
        return { label, status: 0, ok: false } // network/CORS failure
    }
}

export interface PermissionProbeReport {
    tokenPresent: boolean
    itwinPlatformScopeAvailable: Access
    imodelRead: Access
    imodelCreate: Access
    storageRead: Access
    storageWrite: Access
    syncApiReachable: boolean
    syncAuthorization: SyncAuth
    existingSyncConnectionsReadable: Access
    existingSyncConnectionCount: number | 'NOT_AVAILABLE'
    httpResults: { label: string; status: number }[]
    readiness: Readiness
    blockers: string[]
}

/**
 * Run the read-only probe against the target iTwin. GET-only. Returns a
 * sanitized, bounded report (statuses + verdicts, never payload secrets).
 */
export async function runBentleyPermissionProbe(): Promise<PermissionProbeReport> {
    // Acquire the token from the existing runtime auth client (no persistence).
    const { IModelApp } = await import('@itwin/core-frontend')
    let token = ''
    try {
        token = (await IModelApp.authorizationClient?.getAccessToken?.()) ?? ''
    } catch {
        token = ''
    }
    const tokenPresent = token.length > 0

    const httpResults: { label: string; status: number }[] = []
    const record = (r: GetResult) => { httpResults.push({ label: r.label, status: r.status }); return r }

    if (!tokenPresent) {
        const verdict = classifyBentleyPermissionProbe({
            tokenPresent: false, imodelCreate: 'UNKNOWN', imodelRead: 'UNKNOWN', storageRead: 'UNKNOWN',
            storageWrite: 'UNKNOWN', syncAuthorization: 'UNKNOWN', anyAuthScopeError: true,
        })
        return {
            tokenPresent: false, itwinPlatformScopeAvailable: 'UNKNOWN', imodelRead: 'UNKNOWN',
            imodelCreate: 'UNKNOWN', storageRead: 'UNKNOWN', storageWrite: 'UNKNOWN',
            syncApiReachable: false, syncAuthorization: 'UNKNOWN', existingSyncConnectionsReadable: 'UNKNOWN',
            existingSyncConnectionCount: 'NOT_AVAILABLE', httpResults, readiness: verdict.readiness, blockers: verdict.blockers,
        }
    }

    // 1. iModels list on the iTwin (read + implicit scope check).
    const imodelsList = record(await safeGet(`${API_BASE}/imodels?iTwinId=${ITWIN_ID}`, token, 'GET /imodels?iTwinId'))
    const imodelRead = accessFromStatus(imodelsList.status)

    // 2. Access Control — current user's permissions on the iTwin.
    const perms = record(await safeGet(`${API_BASE}/accesscontrol/itwins/${ITWIN_ID}/permissions`, token, 'GET /accesscontrol/.../permissions'))
    // We cannot read the payload permission list without risking large output;
    // classify create/storage-write from status + a bounded permissions fetch.
    let imodelCreate: Access = 'UNKNOWN'
    let storageWrite: Access = 'UNKNOWN'
    if (perms.status === 403) { imodelCreate = 'NO'; storageWrite = 'NO' }
    else if (perms.ok) {
        // Bounded read of the permissions array to check for the two grants.
        try {
            const res = await fetch(`${API_BASE}/accesscontrol/itwins/${ITWIN_ID}/permissions`, {
                method: 'GET', headers: { Authorization: token, Accept: 'application/vnd.bentley.itwin-platform.v1+json' },
            })
            const json = await res.json().catch(() => ({})) as { permissions?: string[] }
            const list = Array.isArray(json.permissions) ? json.permissions : []
            imodelCreate = list.includes('imodels_manage') ? 'YES' : 'NO'
            storageWrite = list.includes('storage_write') ? 'YES' : 'NO'
        } catch {
            imodelCreate = 'UNKNOWN'; storageWrite = 'UNKNOWN'
        }
    }

    // 3. Storage read (GET top-level folder for the iTwin).
    const storage = record(await safeGet(`${API_BASE}/storage?iTwinId=${ITWIN_ID}`, token, 'GET /storage?iTwinId'))
    const storageRead = accessFromStatus(storage.status)

    // 4. Synchronization authorization information.
    const sync = record(await safeGet(`${API_BASE}/synchronization/imodels/connections/authorizationinformation?redirectUrl=${encodeURIComponent('http://localhost:3000/viewer')}`, token, 'GET /synchronization/.../authorizationinformation'))
    const syncApiReachable = sync.status > 0
    let syncAuthorization: SyncAuth = 'UNKNOWN'
    if (sync.status === 403) syncAuthorization = 'FORBIDDEN'
    else if (sync.status === 401) syncAuthorization = 'UNKNOWN'
    else if (sync.ok) {
        // Response contains an isUserAuthorized flag; read it in a bounded way.
        try {
            const res = await fetch(`${API_BASE}/synchronization/imodels/connections/authorizationinformation?redirectUrl=${encodeURIComponent('http://localhost:3000/viewer')}`, {
                method: 'GET', headers: { Authorization: token, Accept: 'application/vnd.bentley.itwin-platform.v1+json' },
            })
            const json = await res.json().catch(() => ({})) as { authorizationInformation?: { isUserAuthorized?: boolean } }
            const authed = json.authorizationInformation?.isUserAuthorized
            syncAuthorization = authed === true ? 'AUTHORIZED' : authed === false ? 'REQUIRES_ADDITIONAL_AUTHORIZATION' : 'UNKNOWN'
        } catch {
            syncAuthorization = 'UNKNOWN'
        }
    }

    const anyAuthScopeError = httpResults.some((r) => r.status === 401)
    const itwinPlatformScopeAvailable: Access = anyAuthScopeError ? 'NO' : (imodelRead === 'YES' ? 'YES' : 'UNKNOWN')

    const verdict = classifyBentleyPermissionProbe({
        tokenPresent, imodelCreate, imodelRead, storageRead, storageWrite, syncAuthorization, anyAuthScopeError,
    })

    return {
        tokenPresent, itwinPlatformScopeAvailable, imodelRead, imodelCreate, storageRead, storageWrite,
        syncApiReachable, syncAuthorization, existingSyncConnectionsReadable: 'UNKNOWN',
        existingSyncConnectionCount: 'NOT_AVAILABLE', httpResults,
        readiness: verdict.readiness, blockers: verdict.blockers,
    }
}

/** Human-readable, sanitized report for the Developer Inspector. */
export function formatPermissionProbe(r: PermissionProbeReport): string {
    const http = r.httpResults.length ? r.httpResults.map((h) => `  ${h.label} -> ${h.status || 'network-error'}`).join('\n') : '  (none)'
    return [
        `CLOUD_IFC_INGESTION_READINESS = ${r.readiness}`,
        `blockers = ${r.blockers.length ? r.blockers.join('; ') : 'none'}`,
        '',
        `token present (runtime) = ${r.tokenPresent ? 'YES' : 'NO'}`,
        `itwin-platform scope = ${r.itwinPlatformScopeAvailable}`,
        `iModel READ = ${r.imodelRead}`,
        `iModel CREATE (imodels_manage) = ${r.imodelCreate}`,
        `Storage READ = ${r.storageRead}`,
        `Storage WRITE (storage_write) = ${r.storageWrite}`,
        `Synchronization API reachable = ${r.syncApiReachable ? 'YES' : 'NO'}`,
        `Synchronization authorization = ${r.syncAuthorization}`,
        `existing sync connections readable = ${r.existingSyncConnectionsReadable}`,
        `existing sync connection count = ${r.existingSyncConnectionCount}`,
        '',
        'HTTP results (GET-only):',
        http,
        '',
        '(no token/secret shown; GET-only; nothing created/uploaded/run)',
    ].join('\n')
}
