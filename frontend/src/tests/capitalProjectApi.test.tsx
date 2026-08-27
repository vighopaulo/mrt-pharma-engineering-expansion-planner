import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { DEMO_PROJECT } from '../lib/demoProject'
import type { AnalyzeResponseBody, CyclotronModelSummary, ProjectDescriptor } from '../lib/api'

const PROJECT_DESCRIPTOR: ProjectDescriptor = {
    project_id: DEMO_PROJECT.id,
    project_type: 'RETROFIT',
    current_patients_per_day: 60,
    default_target_patients_per_day: 120,
    default_maximum_project_budget_usd: 8_000_000,
    geometry_basis: 'Conceptual geometry (flat engineering inputs; no BIM import connected)',
    provenance: 'CONTROLLED_DEMO_INPUT -- synthetic project input, not an engineering result',
}

const CYCLOTRON_MODELS: CyclotronModelSummary[] = [
    { catalog_model_id: 'GE_PETTRACE_840', manufacturer: 'GE HealthCare', model: 'PETtrace 840', commercial_status: 'current' },
]

const ANALYZE_RESPONSE: AnalyzeResponseBody = {
    project_id: DEMO_PROJECT.id,
    constraint_mode: 'CAPACITY',
    budget_source: 'conventional_target_cost_anchor',
    common_budget_usd: 18_675_000,
    cyclotron_catalog_model_id: null,
    cyclotron_warnings: [],
    provenance: 'equal_budget.run_equal_budget_multibatch_optimization (existing MRT Pharma engine, unmodified)',
    configurations: [
        {
            label: 'Conventional',
            feasible: true,
            patient_capacity_per_day: 125.5,
            project_capex_usd: 18_625_000,
            budget_usd: 18_675_000,
            budget_used_usd: 18_625_000,
            budget_headroom_usd: 50_000,
            annual_revenue_usd: 10_800_000,
            annual_opex_usd: 1_300_000,
            npv_usd: 39_748_388,
            roi_pct: 410.1,
            payback_years: 1.96,
            additional_scanners: 3,
            binding_constraint: 'production_after_decay',
            reserve_capacity_per_day: 5.5,
            cyclotron_utilization_pct: 0,
            cyclotron_capacity_status: 'not_calibrated',
        },
        {
            label: 'MRT',
            feasible: true,
            patient_capacity_per_day: 78.7,
            project_capex_usd: 17_730_000,
            budget_usd: 18_675_000,
            budget_used_usd: 17_730_000,
            budget_headroom_usd: 945_000,
            annual_revenue_usd: 7_081_714,
            annual_opex_usd: 1_440_000,
            npv_usd: 16_935_892,
            roi_pct: 218.2,
            payback_years: 3.14,
            additional_scanners: 1,
            binding_constraint: 'scanner',
            reserve_capacity_per_day: 0,
            cyclotron_utilization_pct: 0,
            cyclotron_capacity_status: 'not_calibrated',
        },
    ],
}

function jsonResponse(body: unknown, status = 200): Response {
    return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

function mockFetchRoutes(overrides: Partial<Record<string, () => Response>> = {}) {
    return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === 'string' ? input : input.toString()
        if (url.includes('/api/health')) return overrides['health']?.() ?? jsonResponse({ status: 'ok', service: 'mrt-pharma-engine' })
        if (url.includes('/api/capital/project/')) return overrides['project']?.() ?? jsonResponse(PROJECT_DESCRIPTOR)
        if (url.includes('/api/catalog/cyclotrons')) return overrides['catalog']?.() ?? jsonResponse(CYCLOTRON_MODELS)
        if (url.includes('/api/capital/analyze') && init?.method === 'POST') return overrides['analyze']?.() ?? jsonResponse(ANALYZE_RESPONSE)
        throw new Error(`Unhandled fetch in test: ${url}`)
    })
}

function renderCapitalProject() {
    return render(
        <MemoryRouter initialEntries={[`/projects/${DEMO_PROJECT.id}/capital`]}>
            <App />
        </MemoryRouter>,
    )
}

describe('Capital Project real engine connection', () => {
    beforeEach(() => {
        vi.stubGlobal('fetch', mockFetchRoutes())
    })

    afterEach(() => {
        vi.unstubAllGlobals()
    })

    it('populates project basis inputs from the real /api/capital/project response', async () => {
        renderCapitalProject()
        await waitFor(() => expect(screen.getByText('Engine connected')).toBeInTheDocument())
        expect(screen.getByLabelText('Current Patient Capacity (patients/day)')).toHaveValue(60)
        expect(screen.getByLabelText('Target Patient Capacity (patients/day)')).toHaveValue(120)
        expect(screen.getByText(PROJECT_DESCRIPTOR.geometry_basis)).toBeInTheDocument()
    })

    it('shows the real catalog cyclotron models, never a hardcoded fictitious list', async () => {
        renderCapitalProject()
        await waitFor(() => expect(screen.getByText('PETtrace 840')).toBeInTheDocument())
    })

    it('running analysis calls the API and displays the real returned configuration, never fabricated numbers', async () => {
        renderCapitalProject()
        await waitFor(() => expect(screen.getByRole('button', { name: 'Run Analysis' })).not.toBeDisabled())
        fireEvent.click(screen.getByRole('button', { name: 'Run Analysis' }))
        await waitFor(() => expect(screen.getByText('$18,625,000')).toBeInTheDocument())
        expect(screen.getAllByText('125.5 /day').length).toBeGreaterThan(0)
        expect(screen.getByText('$39,748,388')).toBeInTheDocument()
    })

    it('switching the candidate configuration shows the OTHER real configuration, not a re-fabricated one', async () => {
        renderCapitalProject()
        await waitFor(() => expect(screen.getByRole('button', { name: 'Run Analysis' })).not.toBeDisabled())
        fireEvent.click(screen.getByRole('button', { name: 'Run Analysis' }))
        await waitFor(() => expect(screen.getByText('$18,625,000')).toBeInTheDocument())

        const configSwitcher = screen.getByRole('radiogroup', { name: 'Configuration' })
        fireEvent.click(within(configSwitcher).getByRole('radio', { name: 'MRT' }))

        await waitFor(() => expect(screen.getByText('$17,730,000')).toBeInTheDocument())
        expect(screen.getAllByText('78.7 /day').length).toBeGreaterThan(0)
    })

    it('budget mode requires a budget value before Run Analysis is enabled', async () => {
        renderCapitalProject()
        await waitFor(() => expect(screen.getByRole('button', { name: 'Run Analysis' })).not.toBeDisabled())
        fireEvent.click(screen.getByRole('radio', { name: 'Budget' }))
        fireEvent.change(screen.getByLabelText(/Maximum Project Budget/), { target: { value: '0' } })
        expect(screen.getByRole('button', { name: 'Run Analysis' })).toBeDisabled()
    })

    it('shows the real engine error detail on failure, never a generic "something went wrong" message', async () => {
        vi.stubGlobal(
            'fetch',
            mockFetchRoutes({
                analyze: () => jsonResponse({ detail: 'NO_FEASIBLE_CONFIGURATION: No feasible conventional configuration found under the common budget.' }, 422),
            }),
        )
        renderCapitalProject()
        await waitFor(() => expect(screen.getByRole('button', { name: 'Run Analysis' })).not.toBeDisabled())
        fireEvent.click(screen.getByRole('button', { name: 'Run Analysis' }))
        await waitFor(() => expect(screen.getByText(/NO_FEASIBLE_CONFIGURATION/)).toBeInTheDocument())
    })

    it('shows an honest unreachable state when the engine cannot be reached', async () => {
        vi.stubGlobal(
            'fetch',
            vi.fn(async () => {
                throw new Error('network down')
            }),
        )
        renderCapitalProject()
        await waitFor(() => expect(screen.getByText('Engine unreachable')).toBeInTheDocument())
    })

    it('What-If remains unconnected and explicitly requires analysis first', async () => {
        renderCapitalProject()
        await waitFor(() => expect(screen.getByText('Analysis required before What-If')).toBeInTheDocument())
    })
})
