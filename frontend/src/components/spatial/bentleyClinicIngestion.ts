/**
 * bentleyClinicIngestion — browser-runtime, DEV-only, EXPLICITLY-GATED workflow
 * that ingests a user-selected architectural IFC into a SEPARATE Bentley iModel
 * (MRTway Medical Clinic Demo) via the supported iTwin Platform cloud path:
 *   create iModel -> iTwin Storage upload -> Synchronization storage connection
 *   -> run -> poll to terminal state.
 *
 * SAFETY CONTRACT:
 *  - Uses ONLY the existing runtime bearer token (IModelApp.authorizationClient).
 *    The token is never displayed, logged, or persisted.
 *  - NOTHING runs automatically. `preflight()` is read-only (GET-only, an
 *    existing-name check). Writes happen ONLY when `startIngestion()` is called
 *    explicitly after the user selected + verified the file and pressed START.
 *  - Targets a NEW iModel named exactly TARGET_DEMO_NAME. If an iModel with that
 *    name already exists it STOPS (no duplicate, no overwrite). It never touches
 *    MRTway Hospital Campus Development.
 *  - The IFC bytes come from a user-picked File (browser file input). The source
 *    file is never modified.
 */

const ITWIN_ID = 'bdf29ecd-b4a4-404d-861a-ac3061c7b12f' // MRTway Development Twin
const API = 'https://api.bentley.com'
const TARGET_DEMO_NAME = 'MRTway Medical Clinic Demo'
const ENGINEERING_FIXTURE_NAME = 'MRTway Hospital Campus Development'
const ACCEPT_V1 = 'application/vnd.bentley.itwin-platform.v1+json'
const ACCEPT_V2 = 'application/vnd.bentley.itwin-platform.v2+json'

async function token(): Promise<string> {
    const { IModelApp } = await import('@itwin/core-frontend')
    const t = (await IModelApp.authorizationClient?.getAccessToken?.()) ?? ''
    if (!t) throw new Error('NO_RUNTIME_TOKEN (sign in to the viewer first)')
    return t
}

interface Log { push: (line: string) => void }

/**
 * Extract ONLY sanitized Bentley error fields from a failed response body.
 * Bentley errors are shaped `{ error: { code, message, details?: [{code,message,target}] } }`.
 * Never returns tokens, Authorization, signed URLs, or arbitrary payload — only
 * the documented error code/message/target/details.
 */
async function sanitizedError(res: Response): Promise<string> {
    let code = ''
    let message = ''
    let details = ''
    try {
        const json = await res.json() as { error?: { code?: string; message?: string; details?: { code?: string; message?: string; target?: string }[] } }
        const e = json.error
        if (e) {
            code = e.code ?? ''
            message = e.message ?? ''
            if (Array.isArray(e.details) && e.details.length > 0) {
                details = e.details.slice(0, 5).map((d) => `${d.code ?? ''}:${d.message ?? ''}${d.target ? `(${d.target})` : ''}`).join('; ')
            }
        }
    } catch { /* non-JSON body; leave blank */ }
    return `HTTP ${res.status}${code ? ` code=${code}` : ''}${message ? ` message="${message}"` : ''}${details ? ` details=[${details}]` : ''}`
}

/**
 * READ-ONLY, name-FILTERED existence check (the reliable check: the iModels list
 * supports a `name` filter and iModel names are unique within an iTwin). Returns
 * the match id if present. GET-only.
 */
async function findDemoImodelByName(tk: string): Promise<{ status: 'NONE' | 'ALREADY_EXISTS' | 'UNKNOWN'; id?: string; raw?: string }> {
    try {
        const res = await fetch(`${API}/imodels?iTwinId=${ITWIN_ID}&name=${encodeURIComponent(TARGET_DEMO_NAME)}`, {
            headers: { Authorization: tk, Accept: ACCEPT_V2 },
        })
        if (!res.ok) return { status: 'UNKNOWN', raw: await sanitizedError(res) }
        const json = await res.json() as { iModels?: { id?: string; name?: string }[] }
        const list = json.iModels ?? []
        const match = list.find((m) => m.name === TARGET_DEMO_NAME) ?? list[0]
        return match?.id ? { status: 'ALREADY_EXISTS', id: match.id } : { status: 'NONE' }
    } catch (e) {
        return { status: 'UNKNOWN', raw: e instanceof Error ? e.message : String(e) }
    }
}

// ---------------------------------------------------------------------------
// Preflight — READ-ONLY. Confirms the file looks like the verified clinic IFC
// and that no iModel named MRTway Medical Clinic Demo already exists.
// ---------------------------------------------------------------------------

export interface PreflightResult {
    ok: boolean
    fileName: string
    fileSizeBytes: number
    schemaLooksIfc2x3: boolean
    headerCheck: 'ISO-10303-21_IFC2X3' | 'UNRECOGNIZED'
    existingDemoImodel: 'NONE' | 'ALREADY_EXISTS' | 'UNKNOWN'
    existingImodelId?: string
    fixtureUntouched: true
    canProceed: boolean
    message: string
}

/** Read the first bytes of the picked File to confirm STEP/IFC2X3 (no upload). */
async function readHeader(file: File): Promise<string> {
    const slice = file.slice(0, 4096)
    return await slice.text()
}

export async function preflight(file: File): Promise<PreflightResult> {
    const header = await readHeader(file).catch(() => '')
    const isStep = header.includes('ISO-10303-21')
    const isIfc2x3 = /FILE_SCHEMA\(\('IFC2X3'\)\)/.test(header) || header.includes('IFC2X3')
    const headerCheck = isStep && isIfc2x3 ? 'ISO-10303-21_IFC2X3' : 'UNRECOGNIZED'

    let existingDemoImodel: PreflightResult['existingDemoImodel'] = 'UNKNOWN'
    let existingId: string | undefined
    try {
        const t = await token()
        const found = await findDemoImodelByName(t) // name-FILTERED (reliable)
        existingDemoImodel = found.status
        existingId = found.id
    } catch { /* leave UNKNOWN */ }

    const canProceed = headerCheck === 'ISO-10303-21_IFC2X3' && existingDemoImodel === 'NONE'
    const message = !isStep || !isIfc2x3
        ? 'File does not look like an ISO-10303-21 / IFC2X3 STEP file — not proceeding.'
        : existingDemoImodel === 'ALREADY_EXISTS'
            ? `An iModel named "${TARGET_DEMO_NAME}" ALREADY EXISTS${existingId ? ` (id=${existingId})` : ''} — this is the HTTP 409 cause. Do NOT create another; open it via /viewer?imodel=${existingId ?? '<id>'} (after verifying its content).`
            : existingDemoImodel === 'UNKNOWN'
                ? 'Could not confirm existing iModels (token/permission?). Resolve before START.'
                : 'Preflight OK. Press START INGESTION to perform the cloud writes.'

    return {
        ok: true, fileName: file.name, fileSizeBytes: file.size,
        schemaLooksIfc2x3: isIfc2x3, headerCheck, existingDemoImodel, existingImodelId: existingId,
        fixtureUntouched: true, canProceed, message,
    }
}

// ---------------------------------------------------------------------------
// START INGESTION — WRITE workflow. Only called on explicit user action.
// ---------------------------------------------------------------------------

export interface IngestionResult {
    demoImodelCreated: boolean
    demoImodelId: string | 'NOT_CREATED'
    ifcUploaded: boolean
    storageFileId: string | 'NOT_UPLOADED'
    connectionCreated: boolean
    connectionId: string | 'NOT_CREATED'
    runStarted: boolean
    synchronizationStatus: 'SUCCEEDED' | 'FAILED' | 'NOT_STARTED'
    runState: string
    runResult: string
    log: string[]
    engineeringFixtureModified: false
}

async function jsonOrText(res: Response): Promise<unknown> {
    try { return await res.json() } catch { return {} }
}

/**
 * Perform the controlled write workflow. Re-verifies the target-name safety
 * (existing-name check) immediately before creating. Bails on the first failure
 * with a bounded error and NEVER touches the engineering fixture.
 */
export async function startIngestion(file: File, onLog?: (line: string) => void): Promise<IngestionResult> {
    const lines: string[] = []
    const log: Log = { push: (l) => { lines.push(l); onLog?.(l) } }
    const result: IngestionResult = {
        demoImodelCreated: false, demoImodelId: 'NOT_CREATED',
        ifcUploaded: false, storageFileId: 'NOT_UPLOADED',
        connectionCreated: false, connectionId: 'NOT_CREATED',
        runStarted: false, synchronizationStatus: 'NOT_STARTED', runState: '', runResult: '',
        log: lines, engineeringFixtureModified: false,
    }

    const t = await token()
    const auth = { Authorization: t }

    // Safety re-check: never create a duplicate; never touch the fixture.
    log.push('Re-checking existing iModels on the iTwin (safety)…')
    const listRes = await fetch(`${API}/imodels?iTwinId=${ITWIN_ID}&$top=100`, { headers: { ...auth, Accept: ACCEPT_V2 } })
    if (!listRes.ok) { log.push(`ABORT: cannot list iModels (HTTP ${listRes.status}).`); return result }
    void listRes // (listing kept for logging parity)
    const filtered = await findDemoImodelByName(t)
    if (filtered.status === 'ALREADY_EXISTS') { log.push(`ABORT: "${TARGET_DEMO_NAME}" already exists${filtered.id ? ` (id=${filtered.id})` : ''} — no duplicate created.`); return result }
    if (filtered.status === 'UNKNOWN') { log.push(`ABORT: could not confirm existing iModels (${filtered.raw ?? 'unknown'}).`); return result }
    log.push(`Confirmed: no existing "${TARGET_DEMO_NAME}"; fixture "${ENGINEERING_FIXTURE_NAME}" will not be touched.`)

    // 1. Create the separate empty iModel.
    log.push(`Creating iModel "${TARGET_DEMO_NAME}"…`)
    const createRes = await fetch(`${API}/imodels`, {
        method: 'POST',
        headers: { ...auth, Accept: ACCEPT_V2, 'Content-Type': 'application/json' },
        body: JSON.stringify({ iTwinId: ITWIN_ID, name: TARGET_DEMO_NAME, description: 'Architectural demo BIM (Clinic_Architectural.ifc, IFC2X3). Separate from the engineering regression fixture.' }),
    })
    if (!(createRes.status === 201 || createRes.ok)) { log.push(`ABORT: create iModel failed — ${await sanitizedError(createRes)}`); return result }
    const createJson = await jsonOrText(createRes) as { iModel?: { id?: string } }
    const imodelId = createJson.iModel?.id
    if (!imodelId) { log.push('ABORT: create iModel returned no id.'); return result }
    result.demoImodelCreated = true; result.demoImodelId = imodelId
    log.push(`Created demo iModel id=${imodelId}.`)

    // 2. Storage: root folder -> create file metadata -> upload bytes -> complete.
    log.push('Resolving iTwin Storage root folder…')
    const storageRes = await fetch(`${API}/storage?iTwinId=${ITWIN_ID}`, { headers: { ...auth, Accept: ACCEPT_V1 } })
    if (!storageRes.ok) { log.push(`ABORT: storage root GET failed (HTTP ${storageRes.status}).`); return result }
    const storageJson = await jsonOrText(storageRes) as { _links?: { folder?: { href?: string } } }
    const folderHref = storageJson._links?.folder?.href
    const folderId = folderHref?.split('/folders/')[1]
    if (!folderId) { log.push('ABORT: could not resolve storage root folder id.'); return result }

    log.push('Creating file metadata…')
    const fileMetaRes = await fetch(`${API}/storage/folders/${folderId}/files`, {
        method: 'POST', headers: { ...auth, Accept: ACCEPT_V1, 'Content-Type': 'application/json' },
        body: JSON.stringify({ displayName: 'Clinic_Architectural.ifc', description: 'Medical clinic architectural IFC (IFC2X3)' }),
    })
    if (!fileMetaRes.ok) { log.push(`ABORT: create file metadata failed (HTTP ${fileMetaRes.status}).`); return result }
    const fileMetaJson = await jsonOrText(fileMetaRes) as { _links?: { uploadUrl?: { href?: string }; completeUrl?: { href?: string } } }
    const uploadUrl = fileMetaJson._links?.uploadUrl?.href
    const completeUrl = fileMetaJson._links?.completeUrl?.href
    if (!uploadUrl || !completeUrl) { log.push('ABORT: file metadata missing upload/complete URLs.'); return result }

    log.push(`Uploading ${(file.size / 1048576).toFixed(1)} MiB to iTwin Storage (Azure blob)…`)
    const putRes = await fetch(uploadUrl, { method: 'PUT', headers: { 'x-ms-blob-type': 'BlockBlob' }, body: file })
    if (!(putRes.status === 201 || putRes.ok)) { log.push(`ABORT: blob upload failed (HTTP ${putRes.status}).`); return result }

    log.push('Confirming upload…')
    const completeRes = await fetch(completeUrl, { method: 'POST', headers: { ...auth, Accept: ACCEPT_V1 } })
    if (!completeRes.ok) { log.push(`ABORT: complete upload failed (HTTP ${completeRes.status}).`); return result }
    const completeJson = await jsonOrText(completeRes) as { file?: { id?: string } }
    const fileId = completeJson.file?.id
    if (!fileId) { log.push('ABORT: complete upload returned no file id.'); return result }
    result.ifcUploaded = true; result.storageFileId = fileId
    log.push(`Uploaded. storageFileId=${fileId}.`)

    // 3. Synchronization: create storage connection (IFC connector) + run.
    log.push('Creating Synchronization storage connection (connectorType=IFC)…')
    const connRes = await fetch(`${API}/synchronization/imodels/storageConnections`, {
        method: 'POST', headers: { ...auth, Accept: ACCEPT_V1, 'Content-Type': 'application/json' },
        body: JSON.stringify({ displayName: 'MedicalClinicArchitectural', iModelId: imodelId, sourceFiles: [{ storageFileId: fileId, connectorType: 'IFC' }] }),
    })
    if (!(connRes.status === 201 || connRes.ok)) { log.push(`ABORT: create connection failed (HTTP ${connRes.status}).`); return result }
    const connJson = await jsonOrText(connRes) as { connection?: { id?: string } }
    const connectionId = connJson.connection?.id
    if (!connectionId) { log.push('ABORT: create connection returned no id.'); return result }
    result.connectionCreated = true; result.connectionId = connectionId
    log.push(`Connection id=${connectionId}.`)

    log.push('Starting synchronization run…')
    const runRes = await fetch(`${API}/synchronization/imodels/storageConnections/${connectionId}/run`, {
        method: 'POST', headers: { ...auth, Accept: ACCEPT_V1, 'Content-Type': 'application/json' },
    })
    if (!(runRes.status === 202 || runRes.ok)) { log.push(`ABORT: run start failed (HTTP ${runRes.status}).`); return result }
    result.runStarted = true
    log.push('Run accepted (202). Polling for terminal state…')

    // 4. Poll runs until terminal. Bounded (~10 min at 10s intervals).
    const maxPolls = 60
    for (let i = 0; i < maxPolls; i++) {
        await new Promise((r) => setTimeout(r, 10000))
        const runsRes = await fetch(`${API}/synchronization/imodels/storageConnections/${connectionId}/runs?$top=1`, { headers: { ...auth, Accept: ACCEPT_V1 } })
        if (!runsRes.ok) { log.push(`poll ${i + 1}: runs GET HTTP ${runsRes.status}`); continue }
        const runsJson = await jsonOrText(runsRes) as { runs?: { state?: string; result?: string }[] }
        const run = runsJson.runs?.[0]
        const state = run?.state ?? 'Unknown'
        const res = run?.result ?? ''
        result.runState = state; result.runResult = res
        log.push(`poll ${i + 1}: state=${state} result=${res}`)
        if (state === 'Completed' || state === 'Failed' || state === 'Error') {
            result.synchronizationStatus = (state === 'Completed' && /success/i.test(res)) ? 'SUCCEEDED' : 'FAILED'
            log.push(`Terminal: IFC_SYNCHRONIZATION_STATUS = ${result.synchronizationStatus}`)
            return result
        }
    }
    log.push('Polling window elapsed without a terminal state (still running server-side).')
    result.synchronizationStatus = 'NOT_STARTED' // unknown terminal; report as not-confirmed
    result.runResult = result.runResult || 'TIMEOUT_WAITING_FOR_TERMINAL'
    return result
}

/**
 * READ-ONLY existing-name check: does an iModel named MRTway Medical Clinic Demo
 * already exist on the target iTwin? GET-only; no writes. Used both by preflight
 * and by the diagnostic RE-CHECK button (e.g. to see whether a prior click
 * nevertheless created it).
 */
export async function checkDemoImodelExists(): Promise<{ status: 'NONE' | 'ALREADY_EXISTS' | 'UNKNOWN'; id?: string; raw?: string }> {
    try {
        const t = await token()
        return await findDemoImodelByName(t) // name-FILTERED, sanitized-error-aware
    } catch (e) {
        return { status: 'UNKNOWN', raw: e instanceof Error ? e.message : String(e) }
    }
}

export { TARGET_DEMO_NAME, ITWIN_ID }
