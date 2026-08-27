const API_BASE_URL: string = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8000'

export type ProjectType = 'GREENFIELD' | 'RETROFIT'
export type ConstraintMode = 'BUDGET' | 'CAPACITY'

export interface ProjectDescriptor {
    project_id: string
    project_type: ProjectType
    current_patients_per_day: number
    default_target_patients_per_day: number
    default_maximum_project_budget_usd: number
    geometry_basis: string
    provenance: string
}

export interface CyclotronModelSummary {
    catalog_model_id: string
    manufacturer: string
    model: string
    commercial_status: string
}

export interface AnalyzeRequestBody {
    project_id: string
    project_type: ProjectType
    constraint_mode: ConstraintMode
    current_patients_per_day: number
    target_patients_per_day: number
    maximum_project_budget_usd?: number | null
    cyclotron_catalog_model_id?: string | null
}

export interface PathwayConfiguration {
    label: 'Conventional' | 'MRT'
    feasible: boolean
    patient_capacity_per_day: number
    project_capex_usd: number
    budget_usd: number
    budget_used_usd: number
    budget_headroom_usd: number
    annual_revenue_usd: number
    annual_opex_usd: number
    npv_usd: number
    roi_pct: number
    payback_years: number | null
    additional_scanners: number
    binding_constraint: string
    reserve_capacity_per_day: number
    cyclotron_utilization_pct: number
    cyclotron_capacity_status: string
}

export interface AnalyzeResponseBody {
    project_id: string
    constraint_mode: ConstraintMode
    budget_source: string
    common_budget_usd: number
    configurations: PathwayConfiguration[]
    cyclotron_catalog_model_id: string | null
    cyclotron_warnings: string[]
    provenance: string
}

export interface HealthResponse {
    status: string
    service: string
}

export type LockdownStatus = 'CURRENT' | 'SUPERSEDED'
export type WhatIfStatus = 'ACTIVE' | 'DISCARDED'

export interface CapitalLockdown {
    lockdown_id: string
    project_id: string
    parent_lockdown_id: string | null
    status: LockdownStatus
    created_at: string
    candidate_label: 'Conventional' | 'MRT'
    request: AnalyzeRequestBody
    result: PathwayConfiguration
    common_budget_usd: number
    budget_source: string
}

export interface CapitalWhatIf {
    what_if_id: string
    project_id: string
    parent_lockdown_id: string
    status: WhatIfStatus
    created_at: string
    candidate_label: 'Conventional' | 'MRT'
    request: AnalyzeRequestBody
    result: PathwayConfiguration
    common_budget_usd: number
    budget_source: string
}

export interface WhatIfResetResponse {
    project_id: string
    parent_lockdown_id: string
    baseline_request: AnalyzeRequestBody
}

/** Real HTTP/engine error -- carries the backend's own status text, never rewritten to a generic message. */
export class ApiError extends Error {
    status: number
    constructor(status: number, message: string) {
        super(message)
        this.status = status
    }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
    let response: Response
    try {
        response = await fetch(`${API_BASE_URL}${path}`, {
            ...init,
            headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
        })
    } catch {
        throw new ApiError(0, 'Engine service unreachable')
    }
    if (!response.ok) {
        let detail = response.statusText
        try {
            const body = (await response.json()) as { detail?: unknown }
            detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
        } catch {
            // no JSON body on this error response -- keep statusText
        }
        throw new ApiError(response.status, detail)
    }
    return (await response.json()) as T
}

export function getHealth(): Promise<HealthResponse> {
    return request('/api/health')
}

export function getProject(projectId: string): Promise<ProjectDescriptor> {
    return request(`/api/capital/project/${encodeURIComponent(projectId)}`)
}

export function listCyclotronModels(): Promise<CyclotronModelSummary[]> {
    return request('/api/catalog/cyclotrons')
}

export function analyzeCapitalProject(body: AnalyzeRequestBody): Promise<AnalyzeResponseBody> {
    return request('/api/capital/analyze', { method: 'POST', body: JSON.stringify(body) })
}

export function createLockdown(body: { project_id: string; candidate_label: 'Conventional' | 'MRT'; request: AnalyzeRequestBody }): Promise<CapitalLockdown> {
    return request('/api/capital/lockdown', { method: 'POST', body: JSON.stringify(body) })
}

export function createWhatIf(body: { project_id: string; request: AnalyzeRequestBody }): Promise<CapitalWhatIf> {
    return request('/api/capital/what-if', { method: 'POST', body: JSON.stringify(body) })
}

export function resetWhatIf(body: { project_id: string }): Promise<WhatIfResetResponse> {
    return request('/api/capital/what-if/reset', { method: 'POST', body: JSON.stringify(body) })
}
